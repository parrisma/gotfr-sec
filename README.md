# gofr-sec

`gofr-sec` is the bootstrap repository for the GOFR security service. This
initial scaffold gives the project a Python package, a minimal web entrypoint,
and the shared `gofr-common` dependency layout already used by the other GOFR
services.

## Current Scope

The repository currently contains:

- a development Docker scaffold in `docker/`
- the `gofr-common` git submodule in `lib/gofr-common`
- the working design proposal in `docs/gofr_sec_proposal.md`
- a minimal FastAPI service in `app/`

The service now exposes the first real auth-management surface: admin group and
membership APIs, explicit self-registration and profile reads, and Phase 6
token mint, inspect, revoke, and self metadata-list APIs.

## Run The Placeholder Service

From the repo root:

```bash
uv pip install -e lib/gofr-common
uv pip install -e ".[dev]"
python -m app.main_web
```

The default web port is `8062`, matching the current Docker scaffold.

## Run Tests

From the repo root:

```bash
./scripts/run_tests.sh --unit
```

Useful variants:

```bash
./scripts/run_tests.sh
./scripts/run_tests.sh --coverage
./scripts/run_tests.sh --integration
./scripts/run_tests.sh --docker --unit
```

The local test tree follows the standard GOFR service shape:

- `test/code_quality/`
- `test/config/`
- `test/api/`
- `test/domain/`
- `test/runtime/`
- `test/integration/`
- `test/security/`

## Vault Bootstrap For Phase 2

`gofr-sec` can now bootstrap its reserved `admin` group against Vault-backed
repositories when Vault configuration is present.

Useful environment values:

- `GOFRSEC_BOOTSTRAP_ADMIN_SUBS`
- `GOFRSEC_SIGNING_VAULT_PATH`
- `GOFRSEC_SIGNING_ALGORITHM`
- `GOFRSEC_TOKEN_ISSUER`
- `GOFRSEC_TOKEN_DEFAULT_LIFETIME_S`
- `GOFRSEC_VAULT_URL` or `GOFR_VAULT_URL`
- `GOFRSEC_VAULT_TOKEN` or `GOFR_VAULT_TOKEN`
- `GOFRSEC_VAULT_PATH_PREFIX`
- `GOFRSEC_VAULT_MOUNT`

Default Vault path layout under the configured prefix:

- `users/<keycloak-sub>/profile`
- `users/<keycloak-sub>/groups`
- `users/<keycloak-sub>/tokens/<token-id>`
- `groups/<group>/definition`
- `groups/<group>/tokens/<token-id>`
- `signing/runtime`
- `tokens/<token-id>`

## Environment

The scaffold reads `GOFRSEC_*` environment variables.

Useful values:

- `GOFRSEC_HOST`
- `GOFRSEC_KEYCLOAK_ISSUER_URL`
- `GOFRSEC_KEYCLOAK_AUDIENCE`
- `GOFRSEC_WEB_PORT`
- `GOFRSEC_MCP_PORT`
- `GOFRSEC_MCPO_PORT`
- `GOFRSEC_DATA_DIR`
- `GOFRSEC_LOG_LEVEL`

## Available Endpoints

- `POST /v1/groups`
- `POST /v1/users/{keycloakSub}/groups/{group}`
- `DELETE /v1/users/{keycloakSub}/groups/{group}`
- `POST /v1/users/{keycloakSub}/tokens`
- `GET /v1/tokens/{tokenId}`
- `POST /v1/tokens/{tokenId}/revoke`
- `POST /v1/me/register`
- `GET /v1/me`
- `GET /v1/me/tokens`
- `GET /v1/runtime/keys/public`
- `POST /v1/runtime/authorize`
- `GET /`
- `GET /ping`
- `GET /v1/status`
- `GET /docs`

## User Registration Flow

`gofr-sec` now supports the start of the user-facing Keycloak flow.

- `POST /v1/me/register` validates the caller's Keycloak bearer token and creates or refreshes the local GOFR user profile for that `sub`.
- `GET /v1/me` returns the caller's local registration state plus any GOFR groups already associated with that `sub`.
- Registration does not mint tokens, assign groups, or grant admin access.

## Next Implementation Layer

The current code now includes the first runtime contract layer:

- services can fetch runtime verification keys from `GET /v1/runtime/keys/public`
- services can locally verify runtime JWTs and ask `POST /v1/runtime/authorize` for a yes-or-no decision

The target behavior for that work is described in `docs/gofr_sec_proposal.md`.