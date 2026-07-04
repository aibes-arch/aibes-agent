#!/usr/bin/env bash
# aibes-agent one-click Web UI startup script
#
# Usage:
#   ./scripts/run-web.sh
#   ./scripts/run-web.sh --host 0.0.0.0 --port 8080
#   ./scripts/run-web.sh --config aibes-agent.yaml

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

CONFIG=""
HOST=""
PORT=""
INSTALL=0

while [[ $# -gt 0 ]]; do
    case "$1" in
        --config|-c)
            CONFIG="$2"
            shift 2
            ;;
        --host)
            HOST="$2"
            shift 2
            ;;
        --port)
            PORT="$2"
            shift 2
            ;;
        --install)
            INSTALL=1
            shift
            ;;
        *)
            echo "[ERROR] Unknown option: $1" >&2
            exit 1
            ;;
    esac
done

VENV_PATH="$PROJECT_ROOT/.venv"

if [[ "$INSTALL" -eq 1 ]] || [[ ! -d "$VENV_PATH" ]]; then
    echo "[INFO] Virtual environment missing, starting install..."
    ./scripts/install.sh
fi

source "$VENV_PATH/bin/activate"

CMD_ARGS=("web")
[[ -n "$CONFIG" ]] && CMD_ARGS+=("--config" "$CONFIG")
[[ -n "$HOST" ]] && CMD_ARGS+=("--host" "$HOST")
[[ -n "$PORT" ]] && CMD_ARGS+=("--port" "$PORT")

echo "[INFO] Starting Web UI: aibes-agent ${CMD_ARGS[*]}"
aibes-agent "${CMD_ARGS[@]}"
