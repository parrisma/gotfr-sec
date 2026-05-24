# gofr-sec Detailed Phased Implementation Plan

This document is an execution plan for building `gofr-sec` from the current bootstrap scaffold into the platform security service described in [docs/gofr_sec_proposal.md](docs/gofr_sec_proposal.md). It is intentionally more operational than the proposal: it breaks the work into small steps, names the test slices to add as the code grows, and makes the `gofr-sec` versus `gofr-common` boundary explicit.

It is based on four concrete anchors:

- the target service boundary in [docs/gofr_sec_proposal.md](docs/gofr_sec_proposal.md)
- the current bootstrap app in [app/main_web.py](app/main_web.py) and [app/web_server/web_server.py](app/web_server/web_server.py)
- the shared runner capabilities in [lib/gofr-common/scripts/run_tests.sh](lib/gofr-common/scripts/run_tests.sh)
- the standard GOFR service shape proven in the remapped `gofr-plot` reference repo

## Peer Review Summary

The first draft was directionally right, but it had five execution risks that would slow implementation if left uncorrected.

1. It generalized into `gofr-common` too early, before `gofr-sec` had a concrete local package layout and storage contract.
2. It named test categories, but not the specific test files, fixture strategy, or runner commands needed to keep the work green as it lands.
3. It assumed a verified admin request path before spelling out the first-boot bootstrap path and the test fixtures that would represent trusted admin subjects.
4. It treated code as the main output and underweighted config, API schema, and operator-facing documentation changes that need to move in lockstep with the code.
5. It did not make the legacy issuer retirement path strict enough, which risks running two authorities in parallel for too long.

The revised plan below fixes those issues by making the local `gofr-sec` contract concrete first, then building the shared reusable pieces in `gofr-common`, then migrating consuming services only after runtime authorization is proven end to end.

## Decisions To Lock Now

These defaults should be treated as working decisions so implementation can proceed without reopening design questions every phase.

- Registration is explicit. Keep `POST /v1/me/register`; do not make registration implicit on first authenticated call.
- Default automated tests must not require a live Keycloak server. Use local signing keys, mocked discovery, and JWKS fixtures for the normal test path.
- Runtime GOFR JWTs must not carry `admin` as a usable runtime access group.
- The canonical token record stores metadata plus token hash. Raw JWT material is returned at mint time only by default.
- Self-service token reveal is optional and disabled by default until the mint, inspect, and revoke path is stable.
- Token associations stay in `gofr-sec` and Vault. Do not mirror them into Keycloak user attributes in v1.
- Vault is the only place where GOFR-managed secret material is stored outside Keycloak. Do not add filesystem, repo-local, or per-service secret-file fallbacks for signing or reveal material in Phase 6.
- Runtime authorization fails closed if `gofr-sec` is unavailable and no still-valid cached decision exists.
- The first pilot migration should use `gofr-plot`, because its repo structure and test runner pattern are already a known reference.
- By Phase 8 there is no migration flag. Services cut over one at a time, but each service cutover is a hard switch to the new path with the old auth path removed.

## Non-Negotiable Delivery Rules

- Each phase must land with automated tests in the same change set.
- The default repo-local command after each `gofr-sec` phase is `./scripts/run_tests.sh --unit`.
- Any phase that touches Vault-backed repositories or bootstrap must also leave `./scripts/run_tests.sh --integration` green.
- Any phase that changes shared reusable client, verifier, or cache behavior in `gofr-common` must leave `lib/gofr-common/scripts/run_tests.sh --unit` green.
- Do not put GOFR-specific group semantics, API path constants, or reserved-group rules into generic Keycloak or caching modules in `gofr-common`.
- Do not keep legacy and `gofr-sec` auth active side by side behind a runtime migration flag inside a single service.
- Remove the old issuer path from the migrating service as part of that service's cutover, and remove the shared legacy issuer from `gofr-common.auth` before Phase 8 is considered complete.
- Prefer narrow, PR-sized slices inside each phase. A phase is a planning boundary, not a single giant commit.

## Ownership Split

- `gofr-sec` owns GOFR-specific domain behavior: groups, reserved `admin` rules, user registration state keyed by Keycloak `sub`, token lifecycle, runtime authorization decisions, and audit logging.
- `gofr-common` owns reusable infrastructure code: Keycloak discovery, JWKS validation, public-key caching, `gofr-sec` client SDK, generic authorization-decision caching, and shared pytest fixtures.
- Vault and Keycloak server provisioning remain infrastructure concerns. Only their reusable client-side integration code belongs in `gofr-common`.
- The legacy issuer logic in `gofr-common.auth` should be frozen early, deprecated once the new path is proven, and deleted only after the pilot migration is complete.

## Target Package And Test Layout

Build `gofr-sec` with a clear internal shape before feature work spreads across the repo.

Recommended application layout:

- `app/api/routes/health.py`
- `app/api/routes/admin_groups.py`
- `app/api/routes/admin_tokens.py`
- `app/api/routes/me.py`
- `app/api/routes/runtime.py`
- `app/api/dependencies.py`
- `app/api/schemas/`
- `app/domain/models.py`
- `app/domain/errors.py`
- `app/domain/rules.py`
- `app/repositories/interfaces.py`
- `app/repositories/in_memory.py`
- `app/repositories/vault_users.py`
- `app/repositories/vault_groups.py`
- `app/repositories/vault_tokens.py`
- `app/services/bootstrap_service.py`
- `app/services/group_service.py`
- `app/services/user_service.py`
- `app/services/token_service.py`
- `app/services/runtime_service.py`
- `app/services/audit_service.py`

Recommended local test layout, matching the standard GOFR project style:

- `scripts/run_tests.sh`
- `test/conftest.py`
- `test/helpers/`
- `test/code_quality/`
- `test/config/`
- `test/domain/`
- `test/api/`
- `test/runtime/`
- `test/integration/`
- `test/security/`

Recommended `gofr-sec` service config surfaces to add progressively under `GOFRSEC_*`:

- `GOFRSEC_KEYCLOAK_ISSUER_URL`
- `GOFRSEC_KEYCLOAK_AUDIENCE`
- `GOFRSEC_BOOTSTRAP_ADMIN_SUBS`
- `GOFRSEC_SIGNING_KEY_PATH` or equivalent key-source setting
- `GOFRSEC_ENABLE_TOKEN_REVEAL`
- `GOFRSEC_AUDIT_LOG_LEVEL`

Recommended consuming-service config surfaces for `gofr-common`:

- `GOFR_SEC_BASE_URL` or `{PROJECT_PREFIX}_SEC_BASE_URL`
- `GOFR_SEC_REQUEST_TIMEOUT_S` or `{PROJECT_PREFIX}_SEC_REQUEST_TIMEOUT_S`
- `GOFR_SEC_AUTHZ_CACHE_TTL_S` or `{PROJECT_PREFIX}_SEC_AUTHZ_CACHE_TTL_S`
- `GOFR_SEC_PUBLIC_KEY_CACHE_TTL_S` or `{PROJECT_PREFIX}_SEC_PUBLIC_KEY_CACHE_TTL_S`

## Phase 0: Establish The Local Test Harness And Repo Skeleton

### Objective

Create the local runner and test tree so every later change has a stable automation entrypoint in the repo itself.

### Small-Step Sequence

1. Create `scripts/run_tests.sh` in `gofr-sec`.
2. Copy the standard GOFR runner shape from the reference service: code-quality-first execution, optional Docker execution, coverage flags, and cleanup support.
3. Borrow only the Vault test-container lifecycle logic from [lib/gofr-common/scripts/run_tests.sh](lib/gofr-common/scripts/run_tests.sh); do not copy unrelated shared-runner behavior wholesale.
4. Set `PROJECT_NAME`, `ENV_PREFIX`, `TEST_DIR`, and container name values for `gofr-sec`.
5. Update [pyproject.toml](pyproject.toml) with pytest configuration, coverage configuration, and initial markers such as `vault_integration` and `keycloak_contract`.
6. Create the local `test/` tree using the singular `test/` naming used by the standard GOFR services.
7. Add `test/conftest.py` that resets [app/settings.py](app/settings.py), constructs the FastAPI app, and exposes shared fixtures for `client`, `settings_env`, and temp data directories.
8. Add `test/code_quality/test_imports.py` to verify the app imports cleanly.
9. Add `test/config/test_settings.py` to exercise the current settings wrapper and defaults.
10. Add `test/api/test_status.py` to cover `GET /`, `GET /ping`, and `GET /v1/status`.
11. Update [README.md](README.md) with the local test command and the intended `test/` layout.
12. Validate the runner shell syntax before trying pytest.

### Tests To Add In This Phase

- `test/code_quality/test_imports.py`
- `test/config/test_settings.py`
- `test/api/test_status.py`

### Validation Commands

- `bash -n scripts/run_tests.sh`
- `./scripts/run_tests.sh --unit`

### Exit Gate

`gofr-sec` has a local, repeatable unit-test command and the bootstrap app is covered by smoke tests.

## Phase 1: Define The Local Contract Inside gofr-sec

### Objective

Create the package layout, config surfaces, and pure domain rules locally in `gofr-sec` before building shared abstractions in `gofr-common`.

### Small-Step Sequence

1. Split the existing route registration so health and status routes live in a dedicated `app/api/routes/health.py` module.
2. Introduce `app/api/schemas/` for request and response DTOs, even if early schemas are small.
3. Extend [app/settings.py](app/settings.py) so it can expose additional sections for Keycloak settings, bootstrap admin settings, signing settings, and cache settings without breaking the current bootstrap behavior.
4. Add pure domain models for `GroupDefinition`, `UserProfile`, `UserGroupMembership`, `IssuedTokenRecord`, `AuthorizationRequest`, `AuthorizationDecision`, and `AuditEvent`.
5. Add domain-specific error types such as `ReservedGroupError`, `LastAdminRemovalError`, `UnregisteredUserError`, and `TokenRevealNotAllowedError`.
6. Add pure rule functions for reserved `admin` behavior: must exist, cannot be renamed, cannot be deleted, and cannot be left with zero members.
7. Add a small bootstrap-config model that parses trusted Keycloak `sub` values from configuration.
8. Add in-memory repository implementations for users, groups, tokens, and audit events so domain and service tests can run before Vault code exists.
9. Add a `BootstrapPlan` or equivalent service object that describes the initial `admin` seeding behavior without yet talking to Vault.
10. Keep all logic in this phase pure and side-effect-free other than in-memory test doubles.
11. Update [README.md](README.md) and the new plan doc if the package layout changes materially while implementing this phase.

### Tests To Add In This Phase

- `test/domain/test_groups.py`
- `test/domain/test_bootstrap_rules.py`
- `test/domain/test_user_profiles.py`
- `test/config/test_phase1_settings.py`

### Validation Commands

- `./scripts/run_tests.sh --unit test/domain/ test/config/`
- `./scripts/run_tests.sh --unit`

### Exit Gate

The local `gofr-sec` contract exists as pure Python code with stable models, errors, and reserved-group invariants, and those rules are covered without external infrastructure.

## Phase 2: Add Vault Repositories And First-Boot Bootstrap

### Objective

Implement Vault-backed storage and the idempotent first-boot bootstrap path that creates `admin` and binds trusted initial admin subjects.

### Small-Step Sequence

1. Define exact Vault path constants that align with the proposal:
	`users/<sub>/profile`, `users/<sub>/groups`, `users/<sub>/tokens/<token-id>`, `groups/<group>/tokens/<token-id>`, and `tokens/<token-id>`.
2. Add repository interfaces for user profile, group membership, token metadata, and audit events.
3. Implement `VaultUserRepository`, `VaultGroupRepository`, and `VaultTokenRepository` using the shared Vault client from `gofr-common`.
4. Decide whether audit events are written to Vault, logs, or both in v1. Keep the audit interface abstract so the sink can change later.
5. Implement a `BootstrapService` that ensures the reserved `admin` group exists.
6. Extend the same service so it binds configured bootstrap admin subjects to `admin` on first boot.
7. Make bootstrap idempotent: repeated startup must not duplicate memberships, destroy existing state, or overwrite manual admin changes.
8. Wire the bootstrap service into app startup so it runs before admin routes are used.
9. Add integration fixtures in `test/conftest.py` for ephemeral Vault using the local runner.
10. Document the initial bootstrap environment variables and the expected Vault path layout.

### Tests To Add In This Phase

- `test/integration/test_vault_paths.py`
- `test/integration/test_vault_repositories.py`
- `test/integration/test_bootstrap_service.py`
- `test/domain/test_bootstrap_idempotency.py`

### Validation Commands

- `./scripts/run_tests.sh --integration test/integration/test_bootstrap_service.py`
- `./scripts/run_tests.sh --integration`

### Exit Gate

`gofr-sec` can start against ephemeral Vault, create the reserved `admin` group once, and bind configured bootstrap admin subjects safely and repeatedly.

## Phase 3: Build Shared Generic Identity And Client Primitives In gofr-common

### Objective

Add the reusable Keycloak, JWKS, verifier, and `gofr-sec` client code in `gofr-common`, but only after the local `gofr-sec` domain and storage contract is concrete.

### Small-Step Sequence

1. Add a reusable discovery client for Keycloak issuer metadata and JWKS endpoint resolution.
2. Add a reusable JWKS cache with refresh, expiry, and simple retry behavior.
3. Add a verified-identity model that captures `sub`, `iss`, `aud`, expiry, and raw claims that `gofr-sec` might still need.
4. Add a reusable access-token verifier that validates issuer, audience, expiry, and signature against JWKS.
5. Add generic config helpers in `gofr-common` so services can load Keycloak issuer, audience, `gofr-sec` base URL, request timeout, and decision-cache TTL from environment.
6. Add a small `gofr-sec` HTTP client skeleton that can call public-key and runtime authorization endpoints later.
7. Add a generic authorization decision cache with explicit fail-closed behavior when no valid cached decision exists.
8. Add shared pytest fixtures for local RSA keypairs, JWKS documents, mocked discovery responses, and signed test tokens.
9. Keep GOFR-specific group semantics and reserved-group rules out of these modules.
10. Update `gofr-common` docs so the new shared security primitives are discoverable by the other GOFR repos.

### Tests To Add In This Phase

- `lib/gofr-common/tests/test_keycloak_discovery.py`
- `lib/gofr-common/tests/test_jwks_cache.py`
- `lib/gofr-common/tests/test_identity_verifier.py`
- `lib/gofr-common/tests/test_sec_client.py`
- `lib/gofr-common/tests/test_authz_cache.py`

### Validation Commands

- `lib/gofr-common/scripts/run_tests.sh --unit tests/test_identity_verifier.py`
- `lib/gofr-common/scripts/run_tests.sh --unit`

### Exit Gate

`gofr-common` can verify Keycloak access tokens and contains the reusable plumbing that `gofr-sec` and the consuming services will both depend on.

## Phase 4: Deliver Admin Authentication And Group Management APIs

### Objective

Add authenticated admin APIs for managing groups and memberships, backed by the bootstrap and storage work already completed.

### Small-Step Sequence

1. Add a request dependency in `gofr-sec` that uses the new `gofr-common` verifier to turn a Keycloak access token into a verified identity.
2. Add an admin-authorization dependency that checks whether the verified `sub` belongs to the reserved `admin` group in the local repository.
3. Add API schemas for create-group, add-membership, and remove-membership operations.
4. Implement `POST /v1/groups` with validation for format, duplicate names, and reserved-name behavior.
5. Implement `POST /v1/users/{keycloakSub}/groups/{group}`.
6. Implement `DELETE /v1/users/{keycloakSub}/groups/{group}`.
7. Enforce the last-admin rule in the service layer, not just the route handler.
8. Emit audit events for success and failure of each admin mutation.
9. Add explicit HTTP mapping for common failure modes: invalid token, non-admin caller, duplicate group, unknown target user, last-admin removal attempt, and invalid group name.
10. Update the OpenAPI docs so the admin endpoints are visible and their auth requirement is clear.

### Tests To Add In This Phase

- `test/api/test_admin_groups.py`
- `test/api/test_admin_memberships.py`
- `test/security/test_admin_authz.py`
- `test/integration/test_admin_audit_events.py`

### Validation Commands

- `./scripts/run_tests.sh --unit test/api/test_admin_groups.py`
- `./scripts/run_tests.sh --integration test/integration/test_admin_audit_events.py`
- `./scripts/run_tests.sh --unit`
- `./scripts/run_tests.sh --integration`

### Exit Gate

An authenticated bootstrap admin can create groups and manage memberships through the API, and the reserved `admin` invariants remain intact.

## Phase 5: Add Registration And Me APIs

### Objective

Let normal users register their Keycloak identity with `gofr-sec` and read their GOFR profile without granting themselves access.

### Small-Step Sequence

1. Add the `POST /v1/me/register` route and schema.
2. Implement registration as an idempotent service call keyed by the verified caller `sub`.
3. Store or refresh the local GOFR user profile for that `sub`.
4. Add `GET /v1/me` to return the user's profile, registration status, and current GOFR group memberships.
5. Ensure registration never assigns groups, mints tokens, or alters admin state.
6. Add service-level validation that token minting for a target user requires prior registration.
7. Add audit events for registration and repeated re-registration attempts.
8. Make sure admin-only routes do not implicitly create missing users as a side effect.
9. Update API docs and README notes describing the new user-facing flow.

### Tests To Add In This Phase

- `test/api/test_me_register.py`
- `test/api/test_me_profile.py`
- `test/security/test_keycloak_token_validation.py`
- `test/domain/test_registration_rules.py`

### Validation Commands

- `./scripts/run_tests.sh --unit test/api/test_me_register.py`
- `./scripts/run_tests.sh --unit`

### Exit Gate

Normal users can register and inspect their local GOFR profile, but cannot grant themselves groups or tokens.

## Phase 6: Implement Token Mint, Inspect, Revoke, And User Token Metadata

### Objective

Make `gofr-sec` the token issuer and token registry while keeping token material handling aligned to the proposal.

### Small-Step Sequence

1. Use Vault as the only key source for signing. Keep the key-loader abstraction isolated, but do not add filesystem, repo-local, or injected-secret fallbacks for GOFR-managed signing material.
2. Add asymmetric token signing support, using RS256 or another asymmetric algorithm so services only need the public key.
3. Add public-key material handling in `gofr-sec` for later publication through a runtime endpoint.
4. Define the token claims clearly: `jti`, owner `sub`, `iss`, `iat`, `nbf`, `exp`, and only the minimum other metadata required.
5. Enforce that `admin` is never granted as a runtime authorization group inside a user-facing GOFR JWT.
6. Implement `POST /v1/users/{keycloakSub}/tokens` as an admin-only route.
7. In the service layer, validate target registration, validate requested groups, create token metadata, sign the JWT, and write the canonical and index records to Vault.
8. Store token hash plus metadata as the normal canonical record.
9. Return the raw JWT at mint time only.
10. Implement `GET /v1/tokens/{tokenId}` for admin metadata inspection.
11. Implement `POST /v1/tokens/{tokenId}/revoke` and make revocation visible to runtime authorization checks.
12. Implement `GET /v1/me/tokens` so a user can view metadata for tokens already associated with their `sub`.
13. If self-service reveal is required, add `POST /v1/me/tokens/{tokenId}/reveal` behind an explicit feature flag and store the pending reveal secret in Vault only, clearing it after first success.
14. Emit audit events for mint, inspect, list, reveal, revoke, and failed admin access.

### Tests To Add In This Phase

- `test/api/test_admin_tokens.py`
- `test/api/test_me_tokens.py`
- `test/domain/test_token_rules.py`
- `test/integration/test_token_storage_layout.py`
- `test/integration/test_token_revocation.py`
- `test/security/test_signing_keys.py`

### Validation Commands

- `./scripts/run_tests.sh --unit test/api/test_admin_tokens.py`
- `./scripts/run_tests.sh --integration test/integration/test_token_storage_layout.py`
- `./scripts/run_tests.sh --integration --coverage`

### Exit Gate

`gofr-sec` can mint, inspect, list, and revoke tokens with Vault-backed canonical records, Vault-managed signing material, and user and group indexes.

## Phase 7: Add Runtime Authorization And The gofr-common Consumer Path

### Objective

Deliver the runtime contract that lets services verify JWT signatures locally and then ask `gofr-sec` for a yes or no authorization decision.

### Small-Step Sequence

1. Add `GET /v1/runtime/keys/public` to publish the verification key used for local signature checks.
2. Add the `POST /v1/runtime/authorize` schema, keeping it deliberately narrow.
3. Implement runtime authorization logic that evaluates token status, ownership, expiry, and group or resource mapping from the server-side record.
4. Normalize deny behavior so revoked tokens, expired tokens, unknown resources, and missing entitlement all return the same outward shape.
5. Add a `gofr-common` runtime verifier that validates `gofr-sec` JWTs locally using the published verification key.
6. Extend the `gofr-common` `gofr-sec` client to call the runtime authorization endpoint after local verification succeeds.
7. Add short-lived authorization-decision caching in `gofr-common`, bounded by token expiry and conservative enough that revocation remains meaningful.
8. Add middleware or dependency helpers in `gofr-common` so consuming GOFR services can adopt the new flow without each reimplementing it.
9. Add end-to-end contract tests that exercise local verification plus remote allow or deny against a running `gofr-sec` test app.
10. Update docs for the runtime contract and the intended service-consumer call sequence.

### Tests To Add In This Phase

- `test/runtime/test_authorize_api.py`
- `test/runtime/test_public_key_endpoint.py`
- `test/security/test_denial_normalization.py`
- `lib/gofr-common/tests/test_runtime_verifier.py`
- `lib/gofr-common/tests/test_runtime_authorization_flow.py`

### Validation Commands

- `./scripts/run_tests.sh --integration test/runtime/`
- `lib/gofr-common/scripts/run_tests.sh --unit tests/test_runtime_authorization_flow.py`
- `lib/gofr-common/scripts/run_tests.sh --unit`
- `./scripts/run_tests.sh --integration`

### Exit Gate

The `gofr-sec` runtime contract is stable enough for a consuming GOFR service to adopt it without using the old shared-secret issuer path.

## Phase 7.5: Manual Verification Stack Before The Pilot Cutover

### Objective

Freeze a manual verification slice before Phase 8 so an operator can run Keycloak, Vault, and `gofr-sec` on the same dev Docker network and exercise the real identity, bootstrap, mint, storage, and runtime authorization path by hand.

### Small-Step Sequence

1. Verify which Docker network the active `gofr-sec` dev container is already attached to and treat that network as the only supported Phase 7.5 test network.
2. Add a dedicated dev compose file under `lib/gofr-common/docker/` that starts a disposable Keycloak and Vault stack on that same external network without changing the normal automated test runner.
3. Add a minimal Keycloak realm import that creates a repeatable realm and direct-grant client whose access tokens carry the audience value `gofr-sec` expects plus the subject claims `gofr-sec` uses for bootstrap and registration.
4. Keep the manual Phase 7.5 Vault service explicitly separate from the existing shared or production-like Vault compose so the hand-test path stays disposable and easy to reset.
5. Document how to provision one disposable runtime signing key secret in Vault before the mint step so the Phase 7 runtime signer reads real key material from Vault.
6. Document the exact `GOFRSEC_*` environment values needed to run `gofr-sec` against that Keycloak and Vault pair from inside the dev container, including the fully prefixed signing-key Vault path.
7. Document creation of two Keycloak users: one future GOFR admin subject and one normal user to receive a runtime token.
8. Document how to log in as the future GOFR admin, decode the Keycloak access token to recover its stable `sub`, and restart `gofr-sec` with `GOFRSEC_BOOTSTRAP_ADMIN_SUBS` set to that value.
9. Document self-registration for both users through `POST /v1/me/register` so the local GOFR registry and Keycloak subjects are linked before admin-only operations begin.
10. Document one minimal admin workflow: create one non-system GOFR group, add the normal user to that group, and mint exactly one runtime JWT for that user.
11. Document direct Vault inspection of the user profile, membership, canonical token record, group token index, user token index, and runtime signing-key material.
12. Document one small consumer-side probe, ideally using the new `gofr-common` runtime authorizer, that locally verifies the minted JWT and then asks `POST /v1/runtime/authorize` for both an allow case and a deny case.
13. Treat this phase as a pre-pilot operator checkpoint. Do not move to the first service cutover until the manual flow is repeatable end to end.

### Tests To Add In This Phase

- no new product tests; reuse the Phase 7 automated suites and add one written manual verification walkthrough
- `docs/phase_7_5_manual_verification.md`
- `lib/gofr-common/docker/system-compose.dev.yml`
- `lib/gofr-common/docker/keycloak/setup-dev-realm.sh`
- `lib/gofr-common/docker/vault/seed-dev-signing-key.sh`
- `lib/gofr-common/docker/start-system-dev.sh`
- `lib/gofr-common/docker/stop-system-dev.sh`

### Validation Commands

- `docker compose -f lib/gofr-common/docker/system-compose.dev.yml config`
- `lib/gofr-common/docker/start-system-dev.sh`
- `lib/gofr-common/docker/stop-system-dev.sh --volumes`
- `./scripts/run_tests.sh --integration test/runtime/`
- `lib/gofr-common/scripts/run_tests.sh --unit tests/test_runtime_authorization_flow.py`

### Exit Gate

An operator can create Keycloak users, provision Vault signing material, bootstrap one GOFR admin subject, register users, mint one runtime JWT, inspect the expected Vault artifacts, and observe both allow and deny runtime authorization decisions before the first pilot-service cutover starts.

## Phase 8: Pilot Migration, Script Retirement, And Hardening

### Objective

Prove the new path in one real GOFR service, then retire the old script-heavy flows and harden the platform behavior.

### Small-Step Sequence

1. Choose `gofr-plot` as the first pilot consumer unless another service has a materially simpler auth surface.
2. Update the pilot service config to point at `gofr-sec` and use the new shared verifier and client helpers.
3. Remove direct application-level token minting, local token-store assumptions, and legacy issuer wiring from the pilot service in the same cutover.
4. Add pilot-service integration tests that prove the new runtime flow works end to end.
5. Freeze the legacy auth management scripts and reduce them to explicit transitional wrappers only.
6. Add a thin CLI wrapper for `gofr-sec` admin and diagnostic operations so normal operator workflows stop depending on ad hoc shell scripts.
7. Add rate limiting for registration, reveal, and runtime authorization endpoints.
8. Add explicit break-glass recovery for restoring `admin` membership without reopening the old day-to-day trust model.
9. Add health and readiness checks for app health, Vault reachability, signing-key readiness, and Keycloak discovery readiness.
10. Add signing-key rotation support and rotation tests.
11. Migrate the remaining GOFR services one by one only after the pilot is green, with each service cutover removing the old auth path rather than toggling between two implementations.
12. Remove the remaining shared legacy issuer code and transitional wrappers before closing the phase.

### Tests To Add In This Phase

- pilot-service integration tests in the chosen consumer repo
- `test/security/test_rate_limits.py`
- `test/security/test_admin_recovery.py`
- `test/security/test_signing_key_rotation.py`
- regression tests proving a migrated service does not keep both old and new auth paths active after cutover

### Validation Commands

- the pilot repo's local `./scripts/run_tests.sh --integration`
- `./scripts/run_tests.sh --integration`
- `lib/gofr-common/scripts/run_tests.sh --unit`

### Exit Gate

One pilot service is green on the new path, there is no migration flag keeping both auth paths alive, and the platform has recovery, rotation, and rate-limit coverage before broader rollout.

## Suggested PR-Sized Slices Inside The Phases

To keep momentum high and risk low, do not treat a phase as a single merge unit. A practical slicing pattern is:

- Slice A: config and pure models
- Slice B: repository or client implementation
- Slice C: route layer and schemas
- Slice D: integration tests and docs

For example, Phase 6 should not land as one PR. It should land as:

- key-loading and signing helpers plus unit tests
- canonical token write path plus integration tests
- inspect and revoke endpoints plus API tests
- optional user token metadata and reveal behavior plus security tests

## Recommended Repo Order

1. Phase 0 and Phase 1 in `gofr-sec`
2. Phase 2 in `gofr-sec`
3. Phase 3 in `gofr-common`
4. Phase 4 through Phase 7 across both repos as needed, with the local `gofr-sec` contract always landing before the generic consumer abstraction that depends on it
5. Phase 7.5 manual verification in `gofr-sec` and `lib/gofr-common` Docker assets
6. Phase 8 only after the runtime contract is stable and manually verified before the first pilot service cutover

## Minimal Milestones

- Milestone A: local runner, smoke tests, and stable package layout
- Milestone B: Vault-backed bootstrap plus admin group APIs
- Milestone C: explicit registration plus admin-only token issuance
- Milestone D: runtime authorization plus `gofr-common` consumer helpers
- Milestone E: first pilot service migrated and legacy issuer frozen

This order keeps the work narrow, testable, and aligned to the proposal while avoiding a long period where the old and new trust models both keep expanding.