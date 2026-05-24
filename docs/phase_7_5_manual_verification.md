# Phase 7.5 Manual Verification Guide

This guide is the operator-facing checkpoint between Phase 7 and Phase 8. It uses a disposable Keycloak, Vault, and Seq system stack on the same Docker network as the running `gofr-sec` dev container so you can validate the real identity, bootstrap, mint, storage, and runtime-authorization path by hand.

## What This Verifies

- Keycloak is the user system and supplies stable `sub` values.
- `gofr-sec` validates Keycloak access tokens, stores GOFR state in Vault, and bootstraps the reserved `admin` group from a trusted Keycloak `sub`.
- `gofr-sec` mints GOFR runtime JWTs and stores canonical records plus indexes in Vault.
- A consuming service can locally verify the runtime JWT and then ask `gofr-sec` for a yes-or-no authorization decision.

## Files Used In This Manual Stack

- `lib/gofr-common/docker/system-compose.dev.yml`
- `lib/gofr-common/docker/keycloak/gofr-dev-realm.json`
- `lib/gofr-common/docker/keycloak/setup-dev-realm.sh`
- `lib/gofr-common/docker/vault/seed-dev-signing-key.sh`
- `lib/gofr-common/docker/start-system-dev.sh`

The compose file joins the existing external `gofr-net` network. The current `gofr-sec` dev container is already attached to that network, so service-to-service calls should use Docker hostnames rather than `localhost`. The system start script performs the compose sanity check, starts the stack, bootstraps the Keycloak realm and users, and seeds the Vault runtime signing key.

## 1. Start The System Stack

From the repo root:

```bash
cd lib/gofr-common/docker
docker compose -f system-compose.dev.yml config
./start-system-dev.sh
docker compose -f system-compose.dev.yml ps
```

Verify the system services respond from inside the dev container:

```bash
curl -fsS http://gofr-sec-keycloak:8080/realms/gofr-dev/.well-known/openid-configuration | python -m json.tool
docker exec gofr-sec-vault vault status
docker exec -e VAULT_ADDR=http://127.0.0.1:8200 -e VAULT_TOKEN=gofr-dev-root-token gofr-sec-vault vault secrets list
curl -fsS http://gofr-seq-dev:5341/health
```

Expected defaults in this manual stack:

- Keycloak admin user: `admin`
- Keycloak admin password: `admin`
- Keycloak realm: `gofr-dev`
- Keycloak direct-grant client: `gofr-sec-cli`
- GOFR admin user: `gofr_admin`
- GOFR admin password: `gofr-admin-pass`
- GOFR user: `gofr_user`
- GOFR user password: `gofr-user-pass`
- Vault root token: `gofr-dev-root-token`
- Keycloak hostname on `gofr-net`: `gofr-sec-keycloak`
- Vault hostname on `gofr-net`: `gofr-sec-vault`

## 2. Create A Normal User And A Future GOFR Admin User

Use the reusable Keycloak bootstrap script. It ensures the realm exists, creates the two dev users, sets their passwords, and writes a reusable environment file with their stable `sub` values:

```bash
cd lib/gofr-common/docker
./keycloak/setup-dev-realm.sh
source /tmp/gofr-sec-dev-keycloak.env
```

The script creates the following reusable dev users:

- `gofr_admin` becomes the future trusted GOFR bootstrap admin subject
- `gofr_user` is the normal user that receives one runtime token in the walkthrough

## 3. Log In Through Keycloak And Capture Stable Subjects

Define two tiny shell helpers in the current shell:

```bash
kc_password_login() {
  curl -sS http://gofr-sec-keycloak:8080/realms/gofr-dev/protocol/openid-connect/token \
    -H 'Content-Type: application/x-www-form-urlencoded' \
    -d "client_id=gofr-sec-cli" \
    -d "grant_type=password" \
    -d "username=$1" \
    -d "password=$2"
}

json_field() {
  python -c 'import json,sys; print(json.load(sys.stdin)[sys.argv[1]])' "$1"
}

decode_jwt_claim() {
  python - "$1" "$2" <<'PY'
import base64
import json
import sys

token = sys.argv[1]
claim = sys.argv[2]
payload = token.split('.')[1]
payload += '=' * (-len(payload) % 4)
print(json.loads(base64.urlsafe_b64decode(payload))[claim])
PY
}
```

Log in both users and extract their access tokens and stable `sub` values:

```bash
export ADMIN_LOGIN_JSON="$(kc_password_login "$GOFR_ADMIN_USERNAME" "$GOFR_ADMIN_PASSWORD")"
export ADMIN_ACCESS_TOKEN="$(printf '%s' "$ADMIN_LOGIN_JSON" | json_field access_token)"
export ADMIN_SUB="$(decode_jwt_claim "$ADMIN_ACCESS_TOKEN" sub)"

export ALICE_LOGIN_JSON="$(kc_password_login "$GOFR_USER_USERNAME" "$GOFR_USER_PASSWORD")"
export ALICE_ACCESS_TOKEN="$(printf '%s' "$ALICE_LOGIN_JSON" | json_field access_token)"
export ALICE_SUB="$(decode_jwt_claim "$ALICE_ACCESS_TOKEN" sub)"

printf 'ADMIN_SUB=%s\nALICE_SUB=%s\n' "$ADMIN_SUB" "$ALICE_SUB"
```

At this point you have proved Keycloak login works and you know the exact `sub` value that must become the trusted GOFR bootstrap admin subject.

## 4. Start Or Restart gofr-sec Against Keycloak And Vault

Before starting `gofr-sec`, provision one disposable runtime signing key in Vault. Phase 7 and Phase 7.5 intentionally require signing material to exist in Vault rather than auto-generating it at runtime.

```bash
cd lib/gofr-common/docker
./vault/seed-dev-signing-key.sh
```

From the repo root, export the manual Phase 7.5 settings and then start `gofr-sec`. If `gofr-sec` is already running, restart it after exporting the new variables.

```bash
export GOFRSEC_KEYCLOAK_ISSUER_URL=http://gofr-sec-keycloak:8080/realms/gofr-dev
export GOFRSEC_KEYCLOAK_AUDIENCE=gofr-sec-cli
export GOFRSEC_BOOTSTRAP_ADMIN_SUBS="$ADMIN_SUB"
export GOFRSEC_VAULT_URL=http://gofr-sec-vault:8200
export GOFRSEC_VAULT_TOKEN=gofr-dev-root-token
export GOFRSEC_VAULT_MOUNT=secret
export GOFRSEC_VAULT_PATH_PREFIX=gofr/sec
export GOFRSEC_VAULT_VERIFY_SSL=false
export GOFRSEC_SIGNING_VAULT_PATH=gofr/sec/signing/runtime
export GOFRSEC_TOKEN_ISSUER=gofr-sec
export GOFRSEC_WEB_PORT=8062

uv run python -m app.main_web --host 0.0.0.0 --port 8062
```

In a second shell, verify the service is up:

```bash
curl -fsS http://127.0.0.1:8062/v1/status | python -m json.tool
```

## 5. Register Both Users In gofr-sec

Register the future admin and the normal user using their Keycloak bearer tokens:

```bash
curl -fsS -X POST http://127.0.0.1:8062/v1/me/register \
  -H "Authorization: Bearer $ADMIN_ACCESS_TOKEN" | python -m json.tool

curl -fsS -X POST http://127.0.0.1:8062/v1/me/register \
  -H "Authorization: Bearer $ALICE_ACCESS_TOKEN" | python -m json.tool

curl -fsS http://127.0.0.1:8062/v1/me \
  -H "Authorization: Bearer $ADMIN_ACCESS_TOKEN" | python -m json.tool

curl -fsS http://127.0.0.1:8062/v1/me \
  -H "Authorization: Bearer $ALICE_ACCESS_TOKEN" | python -m json.tool
```

The admin profile should now show `admin` in its GOFR groups because the bootstrap phase trusts `ADMIN_SUB`.

## 6. Create One Group, Grant Membership, And Mint One Runtime JWT

Create a single non-system group, add the normal user to it, and mint one runtime JWT for that user:

```bash
curl -fsS -X POST http://127.0.0.1:8062/v1/groups \
  -H "Authorization: Bearer $ADMIN_ACCESS_TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"name":"mcp.read","description":"Manual Phase 7.5 access group"}' | python -m json.tool

curl -fsS -X POST "http://127.0.0.1:8062/v1/users/$ALICE_SUB/groups/mcp.read" \
  -H "Authorization: Bearer $ADMIN_ACCESS_TOKEN" | python -m json.tool

export MINT_RESPONSE="$(curl -fsS -X POST "http://127.0.0.1:8062/v1/users/$ALICE_SUB/tokens" \
  -H "Authorization: Bearer $ADMIN_ACCESS_TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"groups":["mcp.read"],"expires_in_seconds":3600}')"

printf '%s' "$MINT_RESPONSE" | python -m json.tool

export ALICE_RUNTIME_JWT="$(printf '%s' "$MINT_RESPONSE" | json_field issued_token)"
export ALICE_RUNTIME_TOKEN_ID="$(printf '%s' "$MINT_RESPONSE" | json_field token_id)"
```

This gives you both the raw GOFR runtime JWT and the canonical token id stored by `gofr-sec` in Vault.

## 7. Verify Vault Artifacts

Inspect the exact records produced by registration, membership grant, token minting, and runtime signing-key creation:

```bash
docker exec -e VAULT_ADDR=http://127.0.0.1:8200 -e VAULT_TOKEN=gofr-dev-root-token gofr-sec-vault \
  sh -lc "vault kv get secret/gofr/sec/users/${ALICE_SUB}/profile"

docker exec -e VAULT_ADDR=http://127.0.0.1:8200 -e VAULT_TOKEN=gofr-dev-root-token gofr-sec-vault \
  sh -lc "vault kv get secret/gofr/sec/users/${ALICE_SUB}/groups"

docker exec -e VAULT_ADDR=http://127.0.0.1:8200 -e VAULT_TOKEN=gofr-dev-root-token gofr-sec-vault \
  sh -lc "vault kv get secret/gofr/sec/users/${ALICE_SUB}/tokens/${ALICE_RUNTIME_TOKEN_ID}"

docker exec -e VAULT_ADDR=http://127.0.0.1:8200 -e VAULT_TOKEN=gofr-dev-root-token gofr-sec-vault \
  sh -lc "vault kv get secret/gofr/sec/groups/mcp.read/tokens/${ALICE_RUNTIME_TOKEN_ID}"

docker exec -e VAULT_ADDR=http://127.0.0.1:8200 -e VAULT_TOKEN=gofr-dev-root-token gofr-sec-vault \
  sh -lc "vault kv get secret/gofr/sec/tokens/${ALICE_RUNTIME_TOKEN_ID}"

docker exec -e VAULT_ADDR=http://127.0.0.1:8200 -e VAULT_TOKEN=gofr-dev-root-token gofr-sec-vault \
  sh -lc "vault kv get secret/gofr/sec/signing/runtime"
```

The important proof points are:

- the user profile exists under `users/<sub>/profile`
- the user group index includes `mcp.read`
- the canonical token record exists under `tokens/<token-id>`
- both the user-token index and the group-token index exist
- runtime signing material exists under `gofr/sec/signing/runtime`

## 8. Simulate A Consumer Verifying The JWT And Asking gofr-sec For Yes Or No

This probe uses the actual Phase 7 `gofr-common` runtime authorizer, so it performs the same local-verify plus remote-authorize flow a consuming service would use.

```bash
export GOFR_SEC_BASE_URL=http://127.0.0.1:8062
export GOFR_SEC_TOKEN_ISSUER=gofr-sec

uv run python - <<'PY'
import os

from gofr_common.auth import RuntimeAuthorizer

runtime_token = os.environ["ALICE_RUNTIME_JWT"]
authorizer = RuntimeAuthorizer.from_env("GOFR")

try:
    allow = authorizer.authorize(runtime_token, group="mcp.read")
    deny = authorizer.authorize(runtime_token, group="mcp.write")

    print({
        "verified_sub": allow.verified_token.owner_sub,
        "verified_token_id": allow.verified_token.token_id,
        "allow": allow.decision.allowed,
        "allow_from_cache": allow.from_cache,
    })
    print({
        "deny": deny.decision.allowed,
        "deny_from_cache": deny.from_cache,
    })
finally:
    authorizer.close()
PY
```

Expected result:

- the `mcp.read` request returns `True`
- the `mcp.write` request returns `False`

That demonstrates the intended pattern:

1. Keycloak authenticates the human user.
2. `gofr-sec` stores GOFR state and mints the runtime JWT.
3. The consuming side verifies the runtime JWT locally.
4. The consuming side asks `gofr-sec` for the final yes-or-no decision.

## 9. Optional Negative Checks

If you want one extra sanity check before Phase 8, revoke the token and rerun the probe.

```bash
curl -fsS -X POST "http://127.0.0.1:8062/v1/tokens/$ALICE_RUNTIME_TOKEN_ID/revoke" \
  -H "Authorization: Bearer $ADMIN_ACCESS_TOKEN" | python -m json.tool
```

After revocation, the same runtime-authorizer probe should return `False` for `mcp.read` as well.

## 10. Tear Down The Manual Stack

When you are done:

```bash
cd lib/gofr-common/docker
./stop-system-dev.sh --volumes
```

That clears the disposable Keycloak and Vault state so the walkthrough can be rerun from a clean slate.