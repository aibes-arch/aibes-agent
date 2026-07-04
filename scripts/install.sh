#!/usr/bin/env bash
# aibes-agent one-click install / update script
#
# Usage:
#   ./scripts/install.sh
#   ./scripts/install.sh --no-git-pull
#   ./scripts/install.sh --extras "dev,cli,web,mcp"

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

NO_GIT_PULL=0
EXTRAS="dev,cli,web,mcp,drilling,code_review,documents"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --no-git-pull)
            NO_GIT_PULL=1
            shift
            ;;
        --extras)
            EXTRAS="$2"
            shift 2
            ;;
        *)
            echo "[ERROR] Unknown option: $1" >&2
            exit 1
            ;;
    esac
done

echo "==================================="
echo "  aibes-agent install / update"
echo "==================================="

PYTHON="${PYTHON:-python3}"
if ! command -v "$PYTHON" >/dev/null 2>&1; then
    PYTHON="python"
fi

if ! command -v "$PYTHON" >/dev/null 2>&1; then
    echo "[ERROR] python/python3 not found. Please install Python 3.11+." >&2
    exit 1
fi

VERSION="$($PYTHON --version 2>&1 | awk '{print $2}')"
echo "[INFO] Found: Python $VERSION"

MAJOR="$(echo "$VERSION" | cut -d. -f1)"
MINOR="$(echo "$VERSION" | cut -d. -f2)"

if [[ "$MAJOR" -lt 3 ]] || { [[ "$MAJOR" -eq 3 ]] && [[ "$MINOR" -lt 11 ]]; }; then
    echo "[ERROR] Python >= 3.11 required, found $MAJOR.$MINOR" >&2
    exit 1
fi

if [[ "$NO_GIT_PULL" -eq 0 ]] && [[ -d .git ]] && command -v git >/dev/null 2>&1; then
    echo "[INFO] Pulling latest source..."
    git pull || echo "[WARN] git pull failed, continuing with current source"
else
    echo "[INFO] Skipping git pull"
fi

VENV_PATH="$PROJECT_ROOT/.venv"
if [[ ! -d "$VENV_PATH" ]]; then
    echo "[INFO] Creating virtual environment .venv..."
    "$PYTHON" -m venv "$VENV_PATH"
else
    echo "[INFO] Virtual environment .venv already exists"
fi

"$VENV_PATH/bin/pip" install --upgrade pip || echo "[WARN] pip upgrade failed, continuing anyway"

echo "[INFO] Installing/updating: .[$EXTRAS]"
"$VENV_PATH/bin/pip" install -e ".[$EXTRAS]"

echo ""
echo "[SUCCESS] aibes-agent installed/updated!"
echo "  Virtual env: $VENV_PATH"
echo "  Next steps:"
echo "    ./scripts/run.sh               # Run default demo"
echo "    ./scripts/run.sh <script.py>   # Run a custom script"
echo "    ./scripts/run-web.sh           # Start Web UI"
echo "    $VENV_PATH/bin/aibes-agent --help  # Show CLI help"
