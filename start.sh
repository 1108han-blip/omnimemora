#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUNTIME_PORT="${RUNTIME_PORT:-8765}"
ADAPTER_PORT="${PORT:-18011}"
LOG_DIR="$ROOT_DIR/tools/verification/logs"
TRACK_B_SELF_HEAL_ENABLED="${TRACK_B_SELF_HEAL_ENABLED:-1}"
TRACK_B_RUNTIME_RESTART_ATTEMPTS="${TRACK_B_RUNTIME_RESTART_ATTEMPTS:-1}"
TRACK_B_RECOVERY_SETTLE_SECONDS="${TRACK_B_RECOVERY_SETTLE_SECONDS:-3}"

RUNTIME_BIN="${RUNTIME_BIN:-$ROOT_DIR/tools/omnimemora-runtime}"
RUNTIME_EXE_LEGACY="$ROOT_DIR/tools/omnimemora.exe"
ADAPTER_SCRIPT="$ROOT_DIR/tools/_run_adapter.py"
INTERNAL_API_TOKEN="${OMNIMEMORA_INTERNAL_API_TOKEN:-track-b-$$-$(date +%s)}"
TRACK_B_DATA_DIR="${OMNIMEMORA_RUNTIME_DATA_DIR:-${OMNIMEMORA_DATA_DIR:-$HOME/.omnimemora}}"
TRACK_B_STATUS_PATH="${OMNIMEMORA_TRACK_B_STATUS_PATH:-${TRACK_B_DATA_DIR}/track_b_status.json}"
AGENT_MODES_PATH="${OMNIMEMORA_AGENT_MODES_PATH:-$ROOT_DIR/5_connectors/adapter/config/agent_modes.json}"
STOPPING=0

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
OMNIMEMORA_AGENT_MODES_PATH="$AGENT_MODES_PATH" \
"$RUNTIME_BIN" serve >"$LOG_DIR/runtime_start.out.log" 2>"$LOG_DIR/runtime_start.err.log" &
RUNTIME_PID=$!

echo "[2/2] Starting adapter on :$ADAPTER_PORT ..."
PORT="$ADAPTER_PORT" \
MEMORY_BACKEND_URL="http://127.0.0.1:${RUNTIME_PORT}" \
OMNIMEMORA_INTERNAL_API_TOKEN="$INTERNAL_API_TOKEN" \
OMNIMEMORA_AGENT_MODES_PATH="$AGENT_MODES_PATH" \
"$PYTHON_BIN" "$ADAPTER_SCRIPT" >"$LOG_DIR/adapter_start.out.log" 2>"$LOG_DIR/adapter_start.err.log" &
ADAPTER_PID=$!

cleanup() {
  STOPPING=1
  kill "${SUPERVISOR_PID:-}" "$ADAPTER_PID" "$RUNTIME_PID" >/dev/null 2>&1 || true
}
trap cleanup EXIT INT TERM

set_track_b_override() {
  local json_payload="$1"
  curl -sf \
    -X POST \
    -H "Content-Type: application/json" \
    -H "X-Internal-Token: ${INTERNAL_API_TOKEN}" \
    -d "$json_payload" \
    "http://127.0.0.1:${ADAPTER_PORT}/proxy/system-status/override" >/dev/null || true
}

clear_track_b_override() {
  curl -sf \
    -X DELETE \
    -H "X-Internal-Token: ${INTERNAL_API_TOKEN}" \
    "http://127.0.0.1:${ADAPTER_PORT}/proxy/system-status/override" >/dev/null || true
}

write_track_b_status_file() {
  local json_payload="$1"
  mkdir -p "$(dirname "$TRACK_B_STATUS_PATH")"
  printf '%s\n' "$json_payload" >"$TRACK_B_STATUS_PATH"
}

clear_track_b_status_file() {
  rm -f "$TRACK_B_STATUS_PATH" >/dev/null 2>&1 || true
}

start_runtime_process() {
  OMNIMEMORA_RUNTIME_PORT="$RUNTIME_PORT" \
  "$RUNTIME_BIN" serve >>"$LOG_DIR/runtime_start.out.log" 2>>"$LOG_DIR/runtime_start.err.log" &
  RUNTIME_PID=$!
}

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

runtime_self_heal_loop() {
  local attempts_left="$TRACK_B_RUNTIME_RESTART_ATTEMPTS"
  if [ "$TRACK_B_SELF_HEAL_ENABLED" != "1" ]; then
    return 0
  fi

  while true; do
    if ! kill -0 "$ADAPTER_PID" >/dev/null 2>&1; then
      return 0
    fi

    if kill -0 "$RUNTIME_PID" >/dev/null 2>&1 && curl -sf "http://127.0.0.1:${RUNTIME_PORT}/health" >/dev/null 2>&1; then
      sleep 2
      continue
    fi

    set_track_b_override '{"status":"recovering-gateway","gateway_health":"healthy","capability_health":"degraded","routing_effective":false,"recommended_action":"wait_for_recovery","error_code":"runtime_unreachable"}'

    if [ "$attempts_left" -le 0 ]; then
      set_track_b_override '{"status":"degraded-capability","gateway_health":"healthy","capability_health":"degraded","routing_effective":false,"recommended_action":"degrade_to_passthrough","error_code":"runtime_restart_failed"}'
      sleep 2
      continue
    fi

    attempts_left=$((attempts_left - 1))
    echo "[TRACK_B] Runtime unhealthy, attempting restart ..."
    start_runtime_process
    if wait_for_health \
      "Runtime(restart)" \
      "http://127.0.0.1:${RUNTIME_PORT}/health" \
      "$RUNTIME_PID" \
      "$LOG_DIR/runtime_start.out.log" \
      "$LOG_DIR/runtime_start.err.log" \
      15; then
      echo "[TRACK_B] Runtime recovered."
      sleep "$TRACK_B_RECOVERY_SETTLE_SECONDS"
      clear_track_b_override
      clear_track_b_status_file
    else
      set_track_b_override '{"status":"degraded-capability","gateway_health":"healthy","capability_health":"degraded","routing_effective":false,"recommended_action":"degrade_to_passthrough","error_code":"runtime_restart_failed"}'
      write_track_b_status_file '{"status":"degraded-capability","gateway_health":"healthy","capability_health":"degraded","routing_effective":false,"user_action_required":false,"recommended_action":"degrade_to_passthrough","error_code":"runtime_restart_failed"}'
    fi

    sleep 2
  done
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

runtime_self_heal_loop &
SUPERVISOR_PID=$!
ADAPTER_EXIT_CODE=0
wait "$ADAPTER_PID" || ADAPTER_EXIT_CODE=$?
if [ "$STOPPING" != "1" ] && kill -0 "$RUNTIME_PID" >/dev/null 2>&1; then
  echo "[TRACK_B] Adapter exited with code ${ADAPTER_EXIT_CODE}; entering user-decision-required state."
  write_track_b_status_file '{"status":"user-decision-required","gateway_health":"unhealthy","capability_health":"healthy","routing_effective":false,"user_action_required":true,"recommended_action":"disable_route_or_uninstall","error_code":"gateway_unreachable"}'
  wait "$RUNTIME_PID"
fi
kill "$SUPERVISOR_PID" "$RUNTIME_PID" >/dev/null 2>&1 || true
