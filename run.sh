#!/usr/bin/env bash
set -euo pipefail

# Simple launcher: creates a venv, installs deps, and runs the app.
# Usage:
#   ./run.sh                   # if ./cards exists, uses it automatically
#   ./run.sh --cards ./cards   # or pass any args through

cd "$(dirname "$0")"

VENV_DIR="${VENV_DIR:-.venv}"
PYTHON_BIN="${PYTHON:-python3}"

if [ ! -d "$VENV_DIR" ]; then
  echo "[setup] Creating virtual environment in $VENV_DIR"
  "$PYTHON_BIN" -m venv "$VENV_DIR"
fi

# shellcheck disable=SC1090
source "$VENV_DIR/bin/activate"

python -m pip install --upgrade pip >/dev/null
pip install -r requirements.txt

if [ $# -eq 0 ] && [ -d "./cards" ]; then
  exec python endless_treasure.py --cards ./cards
else
  exec python endless_treasure.py "$@"
fi

