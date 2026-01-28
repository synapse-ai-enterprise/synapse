#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_PID_FILE="$ROOT_DIR/.backend.pid"
FRONTEND_PID_FILE="$ROOT_DIR/.frontend.pid"

kill_pid_file() {
  local label="$1"
  local pid_file="$2"
  if [[ -f "$pid_file" ]]; then
    local pid
    pid="$(cat "$pid_file")"
    if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
      echo "Stopping $label (PID $pid)"
      kill "$pid" 2>/dev/null || true
    else
      echo "$label PID not running"
    fi
    rm -f "$pid_file"
  else
    echo "$label PID file not found"
  fi
}

kill_port() {
  local port="$1"
  local pids
  pids=$(lsof -ti tcp:"$port" || true)
  if [[ -n "$pids" ]]; then
    echo "Stopping processes on port $port: $pids"
    kill $pids 2>/dev/null || true
  fi
}

kill_pid_file "Backend" "$BACKEND_PID_FILE"
kill_pid_file "Frontend" "$FRONTEND_PID_FILE"

# Fallback in case PID files are missing or stale
kill_port 8000
kill_port 5173
kill_port 5174
