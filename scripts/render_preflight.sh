#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"
PYTHON_BIN="${PYTHON_BIN:-python}"

echo "[1/5] Checking required deploy files..."
for f in render.yaml Procfile requirements.txt main.py; do
  [[ -f "$f" ]] || { echo "Missing required file: $f"; exit 1; }
done

echo "[2/5] Checking Python environment..."
if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "Python binary not found: $PYTHON_BIN"
  echo "Activate your virtualenv first, or set PYTHON_BIN."
  exit 1
fi
if ! "$PYTHON_BIN" -c "import fastapi" >/dev/null 2>&1; then
  echo "Missing backend dependencies in current Python environment."
  echo "Run: pip install -r requirements.txt"
  exit 1
fi

echo "[3/5] Running API contract tests..."
"$PYTHON_BIN" -m unittest app.tests.test_phase2_contracts -v

echo "[4/5] Running endpoint tests..."
"$PYTHON_BIN" -m unittest app.tests.test_api_endpoints -v

echo "[5/5] Verifying app import..."
"$PYTHON_BIN" - <<'PY'
from app.main import app
print('backend_import_ok')
PY

echo "Preflight passed. Backend is deployment-ready."
