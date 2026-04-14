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

if ! command -v python >/dev/null 2>&1; then
  echo "[ERROR] python is required."
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
"$RUNTIME_BIN" serve >"$LOG_DIR/runtime_start.out.log" 2>"$LOG_DIR/runtime_start.err.log" &
RUNTIME_PID=$!

echo "[2/2] Starting adapter on :$ADAPTER_PORT ..."
PORT="$ADAPTER_PORT" python "$ADAPTER_SCRIPT" >"$LOG_DIR/adapter_start.out.log" 2>"$LOG_DIR/adapter_start.err.log" &
ADAPTER_PID=$!

cleanup() {
  kill "$ADAPTER_PID" "$RUNTIME_PID" >/dev/null 2>&1 || true
}
trap cleanup EXIT INT TERM

for _ in $(seq 1 30); do
  if curl -sf "http://127.0.0.1:${RUNTIME_PORT}/health" >/dev/null; then
    break
  fi
  sleep 1
done

for _ in $(seq 1 30); do
  if curl -sf "http://127.0.0.1:${ADAPTER_PORT}/health" >/dev/null; then
    break
  fi
  sleep 1
done

echo "[OK] Runtime: http://127.0.0.1:${RUNTIME_PORT}/health"
echo "[OK] Adapter: http://127.0.0.1:${ADAPTER_PORT}/health"
echo "Press Ctrl+C to stop both services."

wait "$RUNTIME_PID" "$ADAPTER_PID"
