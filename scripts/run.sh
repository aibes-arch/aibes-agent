#!/usr/bin/env bash
# aibes-agent one-click run script
#
# Usage:
#   ./scripts/run.sh
#   ./scripts/run.sh examples/planner_demo.py
#   ./scripts/run.sh --yes-to-all
#   ./scripts/run.sh --config aibes-agent.yaml

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

SCRIPT="examples/readme_demo.py"
YES_TO_ALL=0
CONFIG=""
INSTALL=0
EXTRA_ARGS=()

while [[ $# -gt 0 ]]; do
    case "$1" in
        --yes-to-all|-y)
            YES_TO_ALL=1
            shift
            ;;
        --config|-c)
            CONFIG="$2"
            shift 2
            ;;
        --install)
            INSTALL=1
            shift
            ;;
        -*)
            EXTRA_ARGS+=("$1")
            shift
            ;;
        *)
            SCRIPT="$1"
            shift
            ;;
    esac
done

VENV_PATH="$PROJECT_ROOT/.venv"

if [[ "$INSTALL" -eq 1 ]] || [[ ! -d "$VENV_PATH" ]]; then
    echo "[INFO] Virtual environment missing, starting install..."
    ./scripts/install.sh
fi

source "$VENV_PATH/bin/activate"

CMD_ARGS=("run" "$SCRIPT")
[[ "$YES_TO_ALL" -eq 1 ]] && CMD_ARGS+=("--yes-to-all")
[[ -n "$CONFIG" ]] && CMD_ARGS+=("--config" "$CONFIG")
[[ ${#EXTRA_ARGS[@]} -gt 0 ]] && CMD_ARGS+=("${EXTRA_ARGS[@]}")

echo "[INFO] Running: aibes-agent ${CMD_ARGS[*]}"
aibes-agent "${CMD_ARGS[@]}"
