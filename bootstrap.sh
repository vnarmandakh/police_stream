#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$REPO_ROOT/edge_project"

PYTHON_BIN="${PYTHON:-python3}"

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "Error: $PYTHON_BIN is not installed." >&2
  exit 1
fi

cd "$PROJECT_DIR"

if [ ! -d .venv ]; then
  "$PYTHON_BIN" -m venv .venv
fi

source .venv/bin/activate

if ! python -m pip install --upgrade pip; then
  echo "Warning: unable to upgrade pip (check network connectivity)." >&2
fi

if ! python -m pip install -r requirements.txt; then
  echo "Error: failed to install Python dependencies. Check network or proxy settings." >&2
  exit 1
fi

echo "Virtual environment created at $PROJECT_DIR/.venv"
echo "Run 'source edge_project/.venv/bin/activate' before using manage.py."
