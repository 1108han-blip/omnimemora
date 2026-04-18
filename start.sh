#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUNTIME_PORT="${RUNTIME_PORT:-8765}"
ADAPTER_PORT="${PORT:-18011}"
LOG_DIR="$ROOT_DIR/tools/verification/logs"

RUNTIME_BIN="${RUNTIME_BIN:-$ROOT_DIR/tools/omnimemora-runtime}"
RUNTIME_EXE_LEGACY="$ROOT_DIR/tools/omnimemora.exe"
ADAPTER_SCRIPT="$ROOT_DIR/tools/_run_adapter.py"

if ! command -v curl >/dev/null 2>&1; then
  echo "[ERROR] curl is required."
  exit 1
fi

PYTHON_BIN="${PYTHON_BIN:-$(command -v python3 || true)}"

if [ -z "$PYTHON_BIN" ]; then
  echo "[ERROR] python3 is required."
  exit 1
fi

if [ ! -f "$RUNTIME_BIN" ]; then
  if [ -f "$RUNTIME_EXE_LEGACY" ]; then
    RUNTIME_BIN="$RUNTIME_EXE_LEGACY"
  else
    if ! command -v go >/dev/null 2>&1; then
      echo "[ERROR] Go is required to build runtime binary."
      exit 1
    fi
    echo "[INFO] Runtime binary not found, building from source ..."
    (
      cd "$ROOT_DIR/4_core/local-runtime"
      go build -o "$RUNTIME_BIN" .
    )
  fi
fi

if [ ! -f "$ADAPTER_SCRIPT" ]; then
  echo "[ERROR] Adapter launcher not found at $ADAPTER_SCRIPT"
  exit 1
fi

mkdir -p "$LOG_DIR"

echo "[1/2] Starting runtime on :$RUNTIME_PORT ..."
OMNIMEMORA_RUNTIME_PORT="$RUNTIME_PORT" \
"$RUNTIME_BIN" serve >"$LOG_DIR/runtime_start.out.log" 2>"$LOG_DIR/runtime_start.err.log" &
RUNTIME_PID=$!

echo "[2/2] Starting adapter on :$ADAPTER_PORT ..."
PORT="$ADAPTER_PORT" \
MEMORY_BACKEND_URL="http://127.0.0.1:${RUNTIME_PORT}" \
"$PYTHON_BIN" "$ADAPTER_SCRIPT" >"$LOG_DIR/adapter_start.out.log" 2>"$LOG_DIR/adapter_start.err.log" &
ADAPTER_PID=$!

cleanup() {
  kill "$ADAPTER_PID" "$RUNTIME_PID" >/dev/null 2>&1 || true
}
trap cleanup EXIT INT TERM

wait_for_health() {
  local service_name="$1"
  local url="$2"
  local pid="$3"
  local stdout_log="$4"
  local stderr_log="$5"
  local timeout_seconds="${6:-30}"

  for _ in $(seq 1 "$timeout_seconds"); do
    if ! kill -0 "$pid" >/dev/null 2>&1; then
      echo "[ERROR] ${service_name} exited before becoming healthy."
      echo "        stdout: $stdout_log"
      echo "        stderr: $stderr_log"
      return 1
    fi
    if curl -sf "$url" >/dev/null; then
      echo "[OK] ${service_name}: $url"
      return 0
    fi
    sleep 1
  done

  echo "[ERROR] ${service_name} failed health check before timeout (${timeout_seconds}s)."
  echo "        health: $url"
  echo "        stdout: $stdout_log"
  echo "        stderr: $stderr_log"
  return 1
}

wait_for_health \
  "Runtime" \
  "http://127.0.0.1:${RUNTIME_PORT}/health" \
  "$RUNTIME_PID" \
  "$LOG_DIR/runtime_start.out.log" \
  "$LOG_DIR/runtime_start.err.log"

wait_for_health \
  "Adapter" \
  "http://127.0.0.1:${ADAPTER_PORT}/health" \
  "$ADAPTER_PID" \
  "$LOG_DIR/adapter_start.out.log" \
  "$LOG_DIR/adapter_start.err.log"

echo "Press Ctrl+C to stop both services."

wait "$RUNTIME_PID" "$ADAPTER_PID"
