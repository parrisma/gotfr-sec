# Copilot Instructions for gofr-sec

## GENERAL SECTION (ROOT, MACHINE)

ALL RULES ARE MANDATORY.

## A. COMMON PATTERNS, TRUTHS, AXIOMS, BEST PRACTICE

## A1. HARD RULES (MUST/NEVER)

RZ ZEROTH RULE: Be diligent and conscientious. Prefer simple, elegant solutions; never hack in changes that introduce technical debt or unnecessary complexity.
R0 SIMPLICITY: Be brief. Add complexity/verbosity ONLY when needed.
R1 CLARITY: If ambiguous and the repo/docs do not already answer it -> ASK. Never invent product policy or security semantics.
R2 COLLAB: Treat user as partner. Show enough command output for review; do not hide critical output; do not burn context on noise.
R3 LONG_FORM: If longer than a few sentences -> write `docs/*.md`, not chat.
R4 FORMAT: Technical chat answers are plain text. Markdown is for documents only.
R5 NETWORK: Use the address that matches the current execution context. Do not hardcode `localhost` or a Docker hostname blindly.
R5a DEV CONTAINER: Running inside a Docker dev container. For `gofr-sec` integration tests, prefer the repo runner to wire networking. Current ephemeral Vault is reached as `http://gofr-sec-vault-test:8200` inside containerized runs and via mapped host port only when running directly on the host.
R6 ASCII: ASCII only in code/output. No emoji/Unicode/box drawing.
R7 GIT: Never rewrite pushed history (no `--amend`, no `rebase -i`). Use follow-up commits.
R8 PYTHON: Use UV tooling (`uv run`, `uv add`, `uv sync`, `uv pip`). Do not introduce raw `pip` or ad-hoc venv workflows.
R9 LOGGING: Follow current repo conventions. Use shared `gofr_common` helpers when already present; otherwise stdlib `logging` is acceptable. Avoid new `print()` calls except CLI/startup banners or tests.
R10 GIT OPS: Never `git add`/`commit`/`push` unless explicitly asked.
R11 PATTERN DISCIPLINE: Select one clear naming/structure pattern, state it when useful, and follow it consistently. Mixed patterns create confusion, slow validation, and should be corrected at the source rather than explained around.

## A2. WORKFLOW (DECISION TREE)

IF change is trivial (few lines, obvious) -> implement directly.
ELSE -> Spec -> Plan -> Execute.

SPEC: `docs/<feature>_spec.md` (WHAT/WHY, constraints, assumptions, no code) -> user approval REQUIRED.
PLAN: `docs/<feature>_implementation_plan.md` (small verifiable steps, no code; update code/docs/tests; run full tests before/after) -> user approval REQUIRED.
EXECUTE: follow plan step-by-step; mark DONE; if uncovered problems appear -> STOP and discuss.

When behavior touches the intended security domain, anchor against `docs/gofr_sec_proposal.md` and any current implementation plan before inventing new semantics.

## A3. ISSUE RESOLUTION

IF bug is not an obvious one-line fix -> write `docs/<issue>_strategy.md` BEFORE code.
Strategy MUST include: symptom, hypothesised root cause, assumptions + validation, diagnostics order.
Stay on root cause. Side-issues are recorded, not chased. No root-cause claims without evidence + user validation.

## A4. PLATFORM GROUND TRUTHS

- Service: `gofr-sec` is the GOFR security service. Current runtime is a bootstrap FastAPI web surface, not a full MCP service.
- Config: settings are layered in `app/settings.py`. Service env prefix is `GOFRSEC_`; Vault settings may explicitly fall back to `GOFR_*` where the code supports it.
- Ports: `8062` web is active today. `8060` and `8061` are reserved by settings for MCP/MCPO parity but are not the primary runtime surface yet.
- Storage: default runtime storage is in-memory. Vault-backed repositories activate only when Vault settings are configured.
- Vault: default mount is `secret`, default path prefix is `gofr/sec`, and integration tests use an ephemeral Vault started by `./scripts/run_tests.sh`.
- Domain rule: reserved admin group is `admin`; bootstrap membership assignment must remain idempotent.
- Prefer `gofr_common` helpers for config, Vault/auth backends, and shared testing utilities.

## A5. TESTING

- Always use `./scripts/run_tests.sh` (env + Vault lifecycle + code-quality gate). Never raw `pytest` for normal repo work.
- Code-quality tests run first through the local runner. Keep them green before widening scope.
- Run targeted first, then `--unit`, then `--integration` when changing startup/bootstrap/Vault behavior.
- Test tree is repo-local `test/`, not `tests/`.
- Improve `run_tests.sh` if it lacks a needed capability.
- Fix failures in scope. If unrelated failures appear, surface them clearly instead of masking them.

## A6. ERRORS

- Surface root cause, not side effects.
- Include: cause, context/references, recovery options.
- New domain exceptions belong in `app/domain/errors.py` unless there is a stronger existing abstraction.

## A7. API / BOOTSTRAP PATTERN

`gofr-sec` currently follows a thin-route, explicit-bootstrap pattern.

1. FastAPI routes live in `app/api/routes/`.
2. Response/request schemas live in `app/api/schemas/`.
3. Domain rules and data models belong in `app/domain/`.
4. Business logic belongs in `app/services/`.
5. Repository protocols live in `app/repositories/interfaces.py`; implementations should stay aligned across in-memory and Vault-backed variants.
6. Application startup state is built in `app/bootstrap.py` and attached to FastAPI app state.
7. Route dependencies that read startup state belong in `app/api/dependencies.py`.

## A8. CODE QUALITY / HARDENING

Review all code as senior engineer + security SME:
- No secrets in code/logs; validate external inputs.
- No unbounded loops/memory; timeouts required; fail closed; least privilege.
- Keep Vault paths centralized in `app/repositories/vault_paths.py`.
- Maintain `test/code_quality/test_code_quality.py` and `test/code_quality/test_imports.py`.

## A9. PLATFORM SCRIPTS (paths relative to project root)

| Script | Purpose |
|--------|---------|
| `scripts/run_tests.sh` | Primary test entry point. Runs code-quality first, then unit/integration targets, and manages ephemeral Vault for integration runs. |
| `docker/run-dev.sh` | Start the gofr-sec dev container and bind mounts. |
| `docker/build-dev.sh` | Build the gofr-sec dev image. |
| `docker/entrypoint-dev.sh` | Dev container startup wiring. |
| `lib/gofr-common/scripts/manage_vault.sh` | Shared Vault lifecycle helper when working at the platform level. |
| `lib/gofr-common/scripts/bootstrap_vault.py` | Shared Vault bootstrap helper code. |

---

## PROJECT SECTION (gofr-sec)

PROJECT_PURPOSE: GOFR security service. Current implementation is a bootstrap FastAPI service that wires startup state, reserved admin-group bootstrap, and in-memory/Vault-backed repositories while broader auth, token, and group-management APIs are built out.
RUNTIME: Python 3.11, UV.
ENV: VS Code dev container on Ubuntu; use repo scripts for Docker and test orchestration instead of assuming a fixed external compose stack.
FRAMEWORK: FastAPI + Uvicorn.
CONFIG: all settings flow through `get_settings()` / `get_service_settings()` in `app/settings.py` with prefix `GOFRSEC_`.
BOOTSTRAP: app startup calls `initialize_application_state()` from `app/bootstrap.py`, builds the repository bundle, and applies bootstrap admin membership.
STORAGE: in-memory repositories by default; Vault-backed repositories when `GOFRSEC_VAULT_URL` plus token/AppRole config is present.
AUTH DIRECTION: future Keycloak/JWKS/verifier work should layer onto this service without breaking the current bootstrap/status surface.

### Port assignments

| Port | Service |
|------|---------|
| 8060 | Reserved MCP port in shared settings |
| 8061 | Reserved MCPO port in shared settings |
| 8062 | gofr-sec web server |
| 8306 | Default mapped host port for ephemeral test Vault |

### Scripts

| Script | Purpose |
|--------|---------|
| `scripts/run_tests.sh` | THE test entry point. Runs code-quality first, then targeted/unit/integration suites. |
| `docker/run-dev.sh` | Start the dev container for local gofr-sec work. |
| `docker/build-dev.sh` | Build the dev container image. |

### Key module map

| Module | Role |
|--------|------|
| `app/main_web.py` | Web entry point; parses CLI args and starts Uvicorn |
| `app/web_server/web_server.py` | FastAPI app assembly and startup hook registration |
| `app/bootstrap.py` | Repository bundle construction and application startup state initialization |
| `app/settings.py` | Shared + service-specific settings, including Vault/bootstrap/signing/cache sections |
| `app/api/routes/health.py` | Current root, ping, and status endpoints |
| `app/api/dependencies.py` | FastAPI dependencies for reading app state |
| `app/services/bootstrap_service.py` | Reserved admin-group bootstrap planning and application |
| `app/domain/models.py` | Core domain dataclasses |
| `app/domain/rules.py` | Reserved-group and runtime-group invariants |
| `app/repositories/interfaces.py` | Repository protocols |
| `app/repositories/in_memory.py` | In-memory repository implementations |
| `app/repositories/vault_users.py` | Vault-backed user profile repository |
| `app/repositories/vault_groups.py` | Vault-backed group and membership repositories |
| `app/repositories/vault_tokens.py` | Vault-backed issued-token repository |
| `app/repositories/vault_paths.py` | Canonical Vault path layout |

### Current service surface

- Endpoints: `/`, `/ping`, `/v1/status`, `/docs`
- Test tree: `test/code_quality/`, `test/config/`, `test/api/`, `test/domain/`, `test/integration/`
- Design anchors: `docs/gofr_sec_proposal.md` and current implementation-plan documents under `docs/`
