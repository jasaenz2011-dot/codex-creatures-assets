#!/usr/bin/env bash
# Creates an isolated, portable virtualenv for the inference backend so it
# never depends on (or pollutes) the system Python.
set -euo pipefail

cd "$(dirname "$0")/.."

PYTHON_BIN="${PYTHON_BIN:-python3}"

"$PYTHON_BIN" -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

echo "Backend virtualenv ready. Activate it with: source backend/.venv/bin/activate"
