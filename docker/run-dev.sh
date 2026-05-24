#!/bin/bash
# Run GOFR-SEC development container
# Uses gofr-sec-dev:latest image (built from gofr-base:latest)
# Standard user: gofr (UID 1000, GID 1000)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

GOFR_USER="gofr"
GOFR_UID=1000
GOFR_GID=1000

CONTAINER_NAME="gofr-sec-dev"
IMAGE_NAME="gofr-sec-dev:latest"

MCP_PORT="${GOFRSEC_MCP_PORT:-8060}"
MCPO_PORT="${GOFRSEC_MCPO_PORT:-8061}"
WEB_PORT="${GOFRSEC_WEB_PORT:-8062}"
DOCKER_NETWORK="${GOFRSEC_DOCKER_NETWORK:-gofr-net}"

while [ $# -gt 0 ]; do
    case $1 in
        --mcp-port)
            MCP_PORT="$2"
            shift 2
            ;;
        --mcpo-port)
            MCPO_PORT="$2"
            shift 2
            ;;
        --web-port)
            WEB_PORT="$2"
            shift 2
            ;;
        --network)
            DOCKER_NETWORK="$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: $0 [--mcp-port PORT] [--mcpo-port PORT] [--web-port PORT] [--network NAME]"
            exit 1
            ;;
    esac
done

echo "======================================================================="
echo "Starting GOFR-SEC Development Container"
echo "======================================================================="
echo "User: ${GOFR_USER} (UID=${GOFR_UID}, GID=${GOFR_GID})"
echo "Ports: MCP=$MCP_PORT, MCPO=$MCPO_PORT, Web=$WEB_PORT"
echo "Network: $DOCKER_NETWORK"
echo "======================================================================="

if ! docker network inspect $DOCKER_NETWORK >/dev/null 2>&1; then
    echo "Creating network: $DOCKER_NETWORK"
    docker network create $DOCKER_NETWORK
fi

VOLUME_NAME="gofr-sec-data-dev"
if ! docker volume inspect $VOLUME_NAME >/dev/null 2>&1; then
    echo "Creating volume: $VOLUME_NAME"
    docker volume create $VOLUME_NAME
fi

if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    echo "Stopping existing container: $CONTAINER_NAME"
    docker stop "$CONTAINER_NAME" 2>/dev/null || true
    docker rm "$CONTAINER_NAME" 2>/dev/null || true
fi

HOST_DOCKER_GID=$(getent group docker | cut -d: -f3 || echo "999")

docker run -d \
    --name "$CONTAINER_NAME" \
    --network "$DOCKER_NETWORK" \
    -p ${MCP_PORT}:8060 \
    -p ${MCPO_PORT}:8061 \
    -p ${WEB_PORT}:8062 \
    -v "$PROJECT_ROOT:/home/gofr/devroot/gofr-sec:rw" \
    -v /home/parris3142/devroot/gofr-plot/:/home/gofr/devroot/gofr-plot:ro \
    -v ${VOLUME_NAME}:/home/gofr/devroot/gofr-sec/data:rw \
    -v /var/run/docker.sock:/var/run/docker.sock \
    -e GOFRSEC_ENV=development \
    -e GOFRSEC_DEBUG=true \
    -e GOFRSEC_LOG_LEVEL=DEBUG \
    -e DOCKER_GID="$HOST_DOCKER_GID" \
    "$IMAGE_NAME"

echo ""
echo "======================================================================="
echo "Container started: $CONTAINER_NAME"
echo "======================================================================="
echo ""
echo "Ports:"
echo "  - $MCP_PORT: MCP server"
echo "  - $MCPO_PORT: MCPO proxy"
echo "  - $WEB_PORT: Web interface"
echo ""
echo "Useful commands:"
echo "  docker logs -f $CONTAINER_NAME          # Follow logs"
echo "  docker exec -it $CONTAINER_NAME bash    # Shell access"
echo "  docker stop $CONTAINER_NAME             # Stop container"