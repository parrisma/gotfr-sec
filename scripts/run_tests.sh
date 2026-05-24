#!/bin/bash
# =============================================================================
# GOFR-SEC Test Runner
# =============================================================================
# Standardized test runner for the gofr-sec service.
#
# Usage:
#   ./scripts/run_tests.sh                          # Run code-quality then unit tests
#   ./scripts/run_tests.sh --unit                   # Run unit tests only
#   ./scripts/run_tests.sh --integration            # Run integration tests
#   ./scripts/run_tests.sh --coverage               # Run with coverage report
#   ./scripts/run_tests.sh --coverage-html          # Run with HTML coverage report
#   ./scripts/run_tests.sh --docker                 # Run inside gofr-sec dev container
#   ./scripts/run_tests.sh --cleanup-only           # Clean transient test artifacts
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${PROJECT_ROOT}"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

PROJECT_NAME="gofr-sec"
ENV_PREFIX="GOFRSEC"
CONTAINER_NAME="gofr-sec-dev"
TEST_DIR="test"
COVERAGE_SOURCE="app"
LOG_DIR="${PROJECT_ROOT}/logs"
TEST_DATA_DIR="${PROJECT_ROOT}/data/test"

USE_UV=false
if command -v uv >/dev/null 2>&1; then
    USE_UV=true
fi

VENV_DIR="${PROJECT_ROOT}/.venv"
if [ "${USE_UV}" = true ]; then
    unset VIRTUAL_ENV
    PYTHON_CMD=(uv run python)
    echo "Using uv run for tooling."
elif [ -f "${VENV_DIR}/bin/activate" ]; then
    source "${VENV_DIR}/bin/activate"
    PYTHON_CMD=(python)
    echo "Activated venv: ${VENV_DIR}"
else
    PYTHON_CMD=(python)
    echo -e "${YELLOW}Warning: no uv command or venv found; using system python.${NC}"
fi

export PYTHONPATH="${PROJECT_ROOT}:${PROJECT_ROOT}/lib/gofr-common/src:${PYTHONPATH:-}"
export GOFRSEC_ENV="TEST"
export GOFRSEC_LOG_LEVEL="DEBUG"
export GOFRSEC_MCP_PORT="${GOFRSEC_MCP_PORT:-8060}"
export GOFRSEC_MCPO_PORT="${GOFRSEC_MCPO_PORT:-8061}"
export GOFRSEC_WEB_PORT="${GOFRSEC_WEB_PORT:-8062}"
export GOFRSEC_DATA_DIR="${GOFRSEC_DATA_DIR:-${TEST_DATA_DIR}}"

VAULT_CONTAINER_NAME="gofr-sec-vault-test"
VAULT_IMAGE="hashicorp/vault:1.15.4"
VAULT_INTERNAL_PORT=8200
VAULT_TEST_PORT="${GOFRSEC_VAULT_PORT_TEST:-8306}"
VAULT_TEST_TOKEN="${GOFR_TEST_VAULT_DEV_TOKEN:-gofr-dev-root-token}"
TEST_NETWORK="${GOFR_TEST_NETWORK:-gofr-test-net}"

mkdir -p "${LOG_DIR}" "${TEST_DATA_DIR}"

print_header() {
    echo -e "${GREEN}=== ${PROJECT_NAME} Test Runner ===${NC}"
    echo "Project root: ${PROJECT_ROOT}"
    echo "Environment: ${GOFRSEC_ENV}"
    echo "PYTHONPATH: ${PYTHONPATH}"
    echo "Data dir: ${GOFRSEC_DATA_DIR}"
    echo "Web port: ${GOFRSEC_WEB_PORT}"
    echo ""
}

cleanup_environment() {
    echo -e "${YELLOW}Cleaning up test environment...${NC}"
    rm -rf "${PROJECT_ROOT}/.pytest_cache" 2>/dev/null || true
    rm -rf "${PROJECT_ROOT}/htmlcov" 2>/dev/null || true
    rm -f "${PROJECT_ROOT}/.coverage" 2>/dev/null || true
    echo -e "${GREEN}Cleanup complete${NC}"
}

is_running_in_docker() {
    [ -f "/.dockerenv" ] && return 0
    grep -qa "docker\|containerd" /proc/1/cgroup 2>/dev/null && return 0
    return 1
}

start_vault_test_container() {
    echo -e "${BLUE}Starting Vault in ephemeral dev mode...${NC}"

    if ! command -v docker >/dev/null 2>&1; then
        echo -e "${RED}Docker is required for Vault integration tests.${NC}"
        return 1
    fi

    if ! docker network ls --format '{{.Name}}' | grep -q "^${TEST_NETWORK}$"; then
        docker network create "${TEST_NETWORK}" >/dev/null
    fi

    if is_running_in_docker; then
        docker network connect "${TEST_NETWORK}" "$(hostname)" >/dev/null 2>&1 || true
    fi

    if ! docker images "${VAULT_IMAGE}" --format '{{.Repository}}' | grep -q "vault"; then
        docker pull "${VAULT_IMAGE}"
    fi

    if docker ps -aq -f name="^${VAULT_CONTAINER_NAME}$" | grep -q .; then
        docker rm -f "${VAULT_CONTAINER_NAME}" >/dev/null 2>&1 || true
    fi

    docker run -d \
        --name "${VAULT_CONTAINER_NAME}" \
        --hostname "${VAULT_CONTAINER_NAME}" \
        --network "${TEST_NETWORK}" \
        --cap-add IPC_LOCK \
        -p "${VAULT_TEST_PORT}:${VAULT_INTERNAL_PORT}" \
        -e "VAULT_DEV_ROOT_TOKEN_ID=${VAULT_TEST_TOKEN}" \
        -e "VAULT_DEV_LISTEN_ADDRESS=0.0.0.0:${VAULT_INTERNAL_PORT}" \
        -e "VAULT_LOG_LEVEL=warn" \
        "${VAULT_IMAGE}" \
        server -dev >/dev/null

    echo -n "Waiting for Vault to be ready"
    local retries=0
    local max_retries=30
    while [ "${retries}" -lt "${max_retries}" ]; do
        if docker exec -e VAULT_ADDR="http://127.0.0.1:${VAULT_INTERNAL_PORT}" \
            "${VAULT_CONTAINER_NAME}" vault status >/dev/null 2>&1; then
            echo " ready"
            break
        fi
        echo -n "."
        sleep 1
        retries=$((retries + 1))
    done

    if [ "${retries}" -eq "${max_retries}" ]; then
        echo ""
        echo -e "${RED}Vault failed to start within ${max_retries}s${NC}"
        docker logs "${VAULT_CONTAINER_NAME}" 2>&1 | tail -20
        return 1
    fi

    docker exec -e VAULT_ADDR="http://127.0.0.1:${VAULT_INTERNAL_PORT}" \
        -e VAULT_TOKEN="${VAULT_TEST_TOKEN}" \
        "${VAULT_CONTAINER_NAME}" \
        vault secrets enable -path=secret -version=2 kv >/dev/null 2>&1 || true

    if is_running_in_docker; then
        export GOFR_VAULT_URL="http://${VAULT_CONTAINER_NAME}:${VAULT_INTERNAL_PORT}"
    else
        export GOFR_VAULT_URL="http://localhost:${VAULT_TEST_PORT}"
    fi
    export GOFR_VAULT_TOKEN="${VAULT_TEST_TOKEN}"
    export GOFRSEC_VAULT_URL="${GOFR_VAULT_URL}"
    export GOFRSEC_VAULT_TOKEN="${GOFR_VAULT_TOKEN}"
    echo "Vault URL: ${GOFR_VAULT_URL}"
}

stop_vault_test_container() {
    echo -e "${YELLOW}Stopping Vault test container...${NC}"
    if docker ps -q -f name="^${VAULT_CONTAINER_NAME}$" | grep -q .; then
        docker rm -f "${VAULT_CONTAINER_NAME}" >/dev/null 2>&1 || true
    fi
}

pytest_command() {
    "${PYTHON_CMD[@]}" -m pytest "$@"
}

run_code_quality_tests() {
    echo -e "${BLUE}Running code-quality tests...${NC}"
    pytest_command "${TEST_DIR}/code_quality/" -v
}

explicit_code_quality_target() {
    local arg
    for arg in "${PYTEST_ARGS[@]}"; do
        case "${arg}" in
            *"${TEST_DIR}/code_quality"*|*"code_quality"*)
                return 0
                ;;
        esac
    done
    return 1
}

USE_DOCKER=false
COVERAGE=false
COVERAGE_HTML=false
RUN_UNIT=false
RUN_INTEGRATION=false
CLEANUP_ONLY=false
USE_VAULT=false
NO_VAULT=false
PYTEST_ARGS=()

while [[ $# -gt 0 ]]; do
    case "$1" in
        --docker)
            USE_DOCKER=true
            shift
            ;;
        --coverage|--cov)
            COVERAGE=true
            shift
            ;;
        --coverage-html)
            COVERAGE=true
            COVERAGE_HTML=true
            shift
            ;;
        --unit)
            RUN_UNIT=true
            shift
            ;;
        --integration)
            RUN_INTEGRATION=true
            USE_VAULT=true
            shift
            ;;
        --vault)
            USE_VAULT=true
            shift
            ;;
        --no-vault)
            NO_VAULT=true
            USE_VAULT=false
            shift
            ;;
        --cleanup-only)
            CLEANUP_ONLY=true
            shift
            ;;
        --help|-h)
            echo "Usage: $0 [OPTIONS] [PYTEST_ARGS...]"
            echo ""
            echo "Options:"
            echo "  --docker         Run tests inside Docker container"
            echo "  --coverage       Run with coverage report"
            echo "  --coverage-html  Run with HTML coverage report"
            echo "  --unit           Run unit tests only"
            echo "  --integration    Run integration tests with ephemeral Vault"
            echo "  --vault          Start ephemeral Vault before running tests"
            echo "  --no-vault       Skip Vault startup"
            echo "  --cleanup-only   Clean transient test artifacts"
            echo "  --help, -h       Show this help message"
            exit 0
            ;;
        *)
            PYTEST_ARGS+=("$1")
            shift
            ;;
    esac
done

print_header

if [ "${CLEANUP_ONLY}" = true ]; then
    cleanup_environment
    exit 0
fi

cleanup_environment

if [ "${NO_VAULT}" = true ]; then
    USE_VAULT=false
fi

if [ "${USE_DOCKER}" = true ]; then
    if ! docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
        echo -e "${RED}Container ${CONTAINER_NAME} is not running.${NC}"
        echo "Run: ./docker/run-dev.sh"
        exit 1
    fi

    INNER_ARGS=()
    [ "${COVERAGE}" = true ] && INNER_ARGS+=("--coverage")
    [ "${COVERAGE_HTML}" = true ] && INNER_ARGS+=("--coverage-html")
    [ "${RUN_UNIT}" = true ] && INNER_ARGS+=("--unit")
    [ "${RUN_INTEGRATION}" = true ] && INNER_ARGS+=("--integration")
    [ "${NO_VAULT}" = true ] && INNER_ARGS+=("--no-vault")
    INNER_ARGS+=("${PYTEST_ARGS[@]}")

    docker exec "${CONTAINER_NAME}" bash -lc \
        "cd /home/gofr/devroot/gofr-sec && ./scripts/run_tests.sh ${INNER_ARGS[*]}"
    exit $?
fi

COVERAGE_ARGS=()
if [ "${COVERAGE}" = true ]; then
    COVERAGE_ARGS+=("--cov=${COVERAGE_SOURCE}" "--cov-report=term-missing")
    if [ "${COVERAGE_HTML}" = true ]; then
        COVERAGE_ARGS+=("--cov-report=html:htmlcov")
    fi
fi

echo -e "${GREEN}=== Running Tests ===${NC}"
set +e
TEST_EXIT_CODE=0
QUALITY_EXIT=0

if ! explicit_code_quality_target; then
    run_code_quality_tests
    QUALITY_EXIT=$?
fi

if [ "${QUALITY_EXIT}" -ne 0 ]; then
    TEST_EXIT_CODE=${QUALITY_EXIT}
else
    if [ "${USE_VAULT}" = true ]; then
        start_vault_test_container
        trap 'stop_vault_test_container' EXIT
    fi

    if [ ${#PYTEST_ARGS[@]} -gt 0 ]; then
        pytest_command "${PYTEST_ARGS[@]}" "${COVERAGE_ARGS[@]}"
        TEST_EXIT_CODE=$?
    elif [ "${RUN_UNIT}" = true ]; then
        echo ""
        echo -e "${BLUE}Running unit tests...${NC}"
        pytest_command "${TEST_DIR}/" \
            --ignore="${TEST_DIR}/code_quality" \
            -m "not vault_integration and not keycloak_contract" \
            -v \
            "${COVERAGE_ARGS[@]}"
        TEST_EXIT_CODE=$?
    elif [ "${RUN_INTEGRATION}" = true ]; then
        echo ""
        echo -e "${BLUE}Running integration tests...${NC}"
        pytest_command "${TEST_DIR}/" \
            --ignore="${TEST_DIR}/code_quality" \
            -v \
            "${COVERAGE_ARGS[@]}"
        TEST_EXIT_CODE=$?
    else
        echo ""
        echo -e "${BLUE}Running unit tests...${NC}"
        pytest_command "${TEST_DIR}/" \
            --ignore="${TEST_DIR}/code_quality" \
            -m "not vault_integration and not keycloak_contract" \
            -v "${COVERAGE_ARGS[@]}"
        TEST_EXIT_CODE=$?
    fi
fi
set -e

echo ""
if [ "${TEST_EXIT_CODE}" -eq 0 ]; then
    echo -e "${GREEN}=== Tests Passed ===${NC}"
    if [ "${COVERAGE}" = true ] && [ "${COVERAGE_HTML}" = true ]; then
        echo -e "${BLUE}HTML coverage report: ${PROJECT_ROOT}/htmlcov/index.html${NC}"
    fi
else
    echo -e "${RED}=== Tests Failed (exit code: ${TEST_EXIT_CODE}) ===${NC}"
fi

exit "${TEST_EXIT_CODE}"