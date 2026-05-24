#!/bin/bash
set -e

GOFR_USER="gofr"
PROJECT_DIR="/home/${GOFR_USER}/devroot/gofr-sec"
COMMON_DIR="$PROJECT_DIR/lib/gofr-common"
VENV_DIR="$PROJECT_DIR/.venv"

echo "======================================================================="
echo "GOFR-SEC Container Entrypoint"
echo "======================================================================="

if [ -d "$PROJECT_DIR/data" ]; then
    if [ ! -w "$PROJECT_DIR/data" ]; then
        echo "Fixing permissions for $PROJECT_DIR/data..."
        sudo chown -R ${GOFR_USER}:${GOFR_USER} "$PROJECT_DIR/data" 2>/dev/null || \
            echo "Warning: Could not fix permissions. Run container with --user $(id -u):$(id -g)"
    fi
fi

if [ -S /var/run/docker.sock ]; then
    echo "Configuring Docker socket access..."
    TARGET_GID=${DOCKER_GID:-$(stat -c '%g' /var/run/docker.sock)}

    if ! getent group "$TARGET_GID" >/dev/null; then
        echo "Creating docker-host group with GID $TARGET_GID"
        sudo groupadd -g "$TARGET_GID" docker-host
    fi

    echo "Adding user $GOFR_USER to group with GID $TARGET_GID"
    sudo usermod -aG "$TARGET_GID" "$GOFR_USER"
fi

mkdir -p "$PROJECT_DIR/data/storage" "$PROJECT_DIR/data/auth"
mkdir -p "$PROJECT_DIR/logs"

if [ ! -f "$VENV_DIR/bin/python" ] || [ ! -x "$VENV_DIR/bin/python" ]; then
    echo "Creating Python virtual environment..."
    cd "$PROJECT_DIR"
    UV_VENV_CLEAR=1 uv venv "$VENV_DIR" --python=python3.11
    echo "Virtual environment created at $VENV_DIR"
fi

if [ -d "$COMMON_DIR" ]; then
    echo "Installing gofr-common (editable)..."
    cd "$PROJECT_DIR"
    uv pip install -e "$COMMON_DIR"
else
    echo "Warning: gofr-common not found at $COMMON_DIR"
    echo "Make sure the submodule is initialized: git submodule update --init"
fi

if [ -f "$PROJECT_DIR/pyproject.toml" ]; then
    echo "Installing project dependencies from pyproject.toml..."
    cd "$PROJECT_DIR"
    uv pip install -e ".[dev]" || echo "Warning: Could not install project dependencies"
elif [ -f "$PROJECT_DIR/requirements.txt" ]; then
    echo "Installing project dependencies from requirements.txt..."
    cd "$PROJECT_DIR"
    uv pip install -r requirements.txt || echo "Warning: Could not install project dependencies"
fi

echo ""
echo "Environment ready. Installed packages:"
uv pip list

echo ""
echo "======================================================================="
echo "Entrypoint complete. Executing: $@"
echo "======================================================================="

exec "$@"