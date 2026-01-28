#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_LOG="$ROOT_DIR/.backend.log"
FRONTEND_LOG="$ROOT_DIR/.frontend.log"
BACKEND_PID_FILE="$ROOT_DIR/.backend.pid"
FRONTEND_PID_FILE="$ROOT_DIR/.frontend.pid"

cleanup() {
  if [[ -n "${BACKEND_PID:-}" ]]; then
    kill "$BACKEND_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT

echo "Starting backend..."
cd "$ROOT_DIR"
if [[ -f "$ROOT_DIR/.env" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$ROOT_DIR/.env"
  set +a
fi
if [[ -f "$ROOT_DIR/.env.local" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$ROOT_DIR/.env.local"
  set +a
fi
if ! command -v poetry >/dev/null 2>&1; then
  echo "Poetry not found. Installing..."
  if command -v brew >/dev/null 2>&1; then
    if ! brew install poetry; then
      echo "Poetry install reported link conflicts. Attempting overwrite..."
      brew link --overwrite certifi pycparser cffi
      brew install poetry
    fi
  else
    curl -sSL https://install.python-poetry.org | python3 -
    export PATH="$HOME/.local/bin:$PATH"
  fi
fi

PYTHON_311="$(command -v python3.11 || true)"
if [[ -z "$PYTHON_311" ]]; then
  if command -v brew >/dev/null 2>&1; then
    echo "Python 3.11 not found. Installing via Homebrew..."
    brew install python@3.11
    PYTHON_311="$(brew --prefix python@3.11)/bin/python3.11"
  else
    echo "Python 3.11 not found and Homebrew is unavailable."
    echo "Install Python 3.11 and ensure python3.11 is on PATH."
    exit 1
  fi
fi

poetry env use "$PYTHON_311"
poetry install --extras local-embeddings
poetry run python -m src.main >"$BACKEND_LOG" 2>&1 &
BACKEND_PID=$!
echo "$BACKEND_PID" >"$BACKEND_PID_FILE"
echo "Backend PID: $BACKEND_PID"
echo "Backend log: $BACKEND_LOG"

echo "Starting frontend..."
cd "$ROOT_DIR/ui"
if [[ ! -d node_modules ]]; then
  npm install
fi

npm run dev >"$FRONTEND_LOG" 2>&1 &
FRONTEND_PID=$!
echo "$FRONTEND_PID" >"$FRONTEND_PID_FILE"
echo "Frontend PID: $FRONTEND_PID"
echo "Frontend log: $FRONTEND_LOG"

for _ in {1..30}; do
  if grep -q "Local:" "$FRONTEND_LOG" 2>/dev/null; then
    FRONTEND_URL="$(grep -m1 "Local:" "$FRONTEND_LOG" | awk '{print $NF}')"
    echo "Frontend running at: $FRONTEND_URL"
    break
  fi
  sleep 1
done

echo "Tailing frontend log (Ctrl+C to stop)..."
tail -f "$FRONTEND_LOG"
