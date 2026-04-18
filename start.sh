#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUNTIME_PORT="${RUNTIME_PORT:-8765}"
ADAPTER_PORT="${PORT:-18011}"
LOG_DIR="$ROOT_DIR/tools/verification/logs"
SUPERVISOR_LOG="$LOG_DIR/track_b_supervisor.log"
TRACK_B_SELF_HEAL_ENABLED="${TRACK_B_SELF_HEAL_ENABLED:-1}"
TRACK_B_RUNTIME_RESTART_ATTEMPTS="${TRACK_B_RUNTIME_RESTART_ATTEMPTS:-1}"
TRACK_B_RECOVERY_SETTLE_SECONDS="${TRACK_B_RECOVERY_SETTLE_SECONDS:-3}"

RUNTIME_BIN="${RUNTIME_BIN:-$ROOT_DIR/tools/omnimemora-runtime}"
RUNTIME_EXE_LEGACY="$ROOT_DIR/tools/omnimemora.exe"
RUNTIME_SOURCE_DIR="$ROOT_DIR/4_core/local-runtime"
ADAPTER_SCRIPT="$ROOT_DIR/tools/_run_adapter.py"
INTERNAL_API_TOKEN="${OMNIMEMORA_INTERNAL_API_TOKEN:-track-b-$$-$(date +%s)}"
TRACK_B_DATA_DIR="${OMNIMEMORA_RUNTIME_DATA_DIR:-${OMNIMEMORA_DATA_DIR:-$HOME/.omnimemora}}"
TRACK_B_STATUS_PATH="${OMNIMEMORA_TRACK_B_STATUS_PATH:-${TRACK_B_DATA_DIR}/track_b_status.json}"
GATEWAY_DECISION_PATH="${OMNIMEMORA_GATEWAY_DECISION_PATH:-${TRACK_B_DATA_DIR}/gateway_decision.json}"
AGENT_MODES_PATH="${OMNIMEMORA_AGENT_MODES_PATH:-$ROOT_DIR/5_connectors/adapter/config/agent_modes.json}"
STOPPING=0

mkdir -p "$LOG_DIR"
: >"$SUPERVISOR_LOG"

log_supervisor() {
  printf '%s %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*" >>"$SUPERVISOR_LOG"
}

if ! command -v curl >/dev/null 2>&1; then
  echo "[ERROR] curl is required."
  exit 1
fi

PYTHON_BIN="${PYTHON_BIN:-$(command -v python3 || true)}"

if [ -z "$PYTHON_BIN" ]; then
  echo "[ERROR] python3 is required."
  exit 1
fi

if ! "$PYTHON_BIN" - <<'PY' >/dev/null 2>&1
from importlib.util import find_spec
import sys

required = ("uvicorn",)
missing = [name for name in required if find_spec(name) is None]
if missing:
    print(",".join(missing))
    sys.exit(1)
PY
then
  echo "[ERROR] Adapter Python dependency missing. Required module(s): uvicorn"
  echo "        Interpreter: $PYTHON_BIN"
  echo "        Candidate/runtime validation cannot continue until adapter deps are available."
  exit 1
fi

if [ ! -f "$RUNTIME_BIN" ]; then
  if [ -f "$RUNTIME_EXE_LEGACY" ]; then
    RUNTIME_BIN="$RUNTIME_EXE_LEGACY"
  else
    RUNTIME_BIN_NEEDS_BUILD=1
  fi
fi

if [ -f "$RUNTIME_BIN" ] && [ -d "$RUNTIME_SOURCE_DIR" ]; then
  if find "$RUNTIME_SOURCE_DIR" \( -name '*.go' -o -name 'go.mod' -o -name 'go.sum' \) -newer "$RUNTIME_BIN" -print -quit | grep -q .; then
    RUNTIME_BIN_NEEDS_BUILD=1
    log_supervisor "runtime binary is stale; source newer than binary path=${RUNTIME_BIN}"
  fi
fi

if [ "${RUNTIME_BIN_NEEDS_BUILD:-0}" = "1" ]; then
  if ! command -v go >/dev/null 2>&1; then
    echo "[ERROR] Go is required to build runtime binary."
    exit 1
  fi
  echo "[INFO] Runtime binary missing or stale, building from source ..."
  log_supervisor "building runtime binary path=${RUNTIME_BIN}"
  (
    cd "$RUNTIME_SOURCE_DIR"
    go build -o "$RUNTIME_BIN" .
  )
fi

if [ ! -f "$ADAPTER_SCRIPT" ]; then
  echo "[ERROR] Adapter launcher not found at $ADAPTER_SCRIPT"
  exit 1
fi

echo "[1/2] Starting runtime on :$RUNTIME_PORT ..."
log_supervisor "runtime start requested port=${RUNTIME_PORT}"
OMNIMEMORA_RUNTIME_PORT="$RUNTIME_PORT" \
OMNIMEMORA_AGENT_MODES_PATH="$AGENT_MODES_PATH" \
"$RUNTIME_BIN" serve >"$LOG_DIR/runtime_start.out.log" 2>"$LOG_DIR/runtime_start.err.log" &
RUNTIME_PID=$!

echo "[2/2] Starting adapter on :$ADAPTER_PORT ..."
start_adapter_process() {
  log_supervisor "adapter start requested port=${ADAPTER_PORT}"
  PORT="$ADAPTER_PORT" \
  MEMORY_BACKEND_URL="http://127.0.0.1:${RUNTIME_PORT}" \
  OMNIMEMORA_INTERNAL_API_TOKEN="$INTERNAL_API_TOKEN" \
  OMNIMEMORA_AGENT_MODES_PATH="$AGENT_MODES_PATH" \
  "$PYTHON_BIN" "$ADAPTER_SCRIPT" >>"$LOG_DIR/adapter_start.out.log" 2>>"$LOG_DIR/adapter_start.err.log" &
  ADAPTER_PID=$!
}
start_adapter_process

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

clear_gateway_decision_file() {
  log_supervisor "clearing gateway decision file path=${GATEWAY_DECISION_PATH}"
  rm -f "$GATEWAY_DECISION_PATH" >/dev/null 2>&1 || true
}

read_gateway_decision() {
  if [ ! -f "$GATEWAY_DECISION_PATH" ]; then
    return 1
  fi
  DECISION_PATH="$GATEWAY_DECISION_PATH" "$PYTHON_BIN" - <<'PY'
import json
import os
import sys

path = os.environ["DECISION_PATH"]
try:
    with open(path, "r", encoding="utf-8") as fh:
        payload = json.load(fh)
except Exception:
    sys.exit(1)

action = str(payload.get("action") or "").strip()
family_id = str(payload.get("family_id") or "").strip()
reason = str(payload.get("transition_reason") or "").strip()
source = str(payload.get("decision_source") or "").strip()
if not action:
    sys.exit(1)
print(action)
print(family_id)
print(reason)
print(source)
PY
}

start_runtime_process() {
  log_supervisor "runtime restart requested port=${RUNTIME_PORT}"
  OMNIMEMORA_RUNTIME_PORT="$RUNTIME_PORT" \
  "$RUNTIME_BIN" serve >>"$LOG_DIR/runtime_start.out.log" 2>>"$LOG_DIR/runtime_start.err.log" &
  RUNTIME_PID=$!
}

write_manual_recovery_status() {
  local reason="$1"
  local error_code="${2:-gateway_unreachable}"
  write_track_b_status_file "{\"status\":\"recovering-gateway\",\"status_source\":\"manual-override\",\"transition_reason\":\"${reason}\",\"gateway_health\":\"recovering\",\"capability_health\":\"healthy\",\"routing_effective\":false,\"user_action_required\":false,\"recommended_action\":\"wait_for_recovery\",\"error_code\":\"${error_code}\"}"
}

write_user_decision_required_status() {
  local reason="$1"
  local error_code="${2:-gateway_unreachable}"
  write_track_b_status_file "{\"status\":\"user-decision-required\",\"status_source\":\"gateway-exit-monitor\",\"transition_reason\":\"${reason}\",\"gateway_health\":\"unhealthy\",\"capability_health\":\"healthy\",\"routing_effective\":false,\"user_action_required\":true,\"recommended_action\":\"disable_route_or_uninstall\",\"error_code\":\"${error_code}\"}"
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

    set_track_b_override '{"status":"recovering-gateway","status_source":"runtime-restart-monitor","transition_reason":"runtime_unreachable","gateway_health":"healthy","capability_health":"degraded","routing_effective":false,"recommended_action":"wait_for_recovery","error_code":"runtime_unreachable"}'

    if [ "$attempts_left" -le 0 ]; then
      set_track_b_override '{"status":"degraded-capability","status_source":"runtime-restart-monitor","transition_reason":"runtime_restart_failed","gateway_health":"healthy","capability_health":"degraded","routing_effective":false,"recommended_action":"degrade_to_passthrough","error_code":"runtime_restart_failed"}'
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
      set_track_b_override '{"status":"degraded-capability","status_source":"runtime-restart-monitor","transition_reason":"runtime_restart_failed","gateway_health":"healthy","capability_health":"degraded","routing_effective":false,"recommended_action":"degrade_to_passthrough","error_code":"runtime_restart_failed"}'
      write_track_b_status_file '{"status":"degraded-capability","status_source":"runtime-restart-monitor","transition_reason":"runtime_restart_failed","gateway_health":"healthy","capability_health":"degraded","routing_effective":false,"user_action_required":false,"recommended_action":"degrade_to_passthrough","error_code":"runtime_restart_failed"}'
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
while true; do
  ADAPTER_EXIT_CODE=0
  wait "$ADAPTER_PID" || ADAPTER_EXIT_CODE=$?
  if [ "$STOPPING" = "1" ]; then
    break
  fi
  if ! kill -0 "$RUNTIME_PID" >/dev/null 2>&1; then
    break
  fi

  echo "[TRACK_B] Adapter exited with code ${ADAPTER_EXIT_CODE}; entering user-decision-required state."
  log_supervisor "adapter exited code=${ADAPTER_EXIT_CODE}; waiting for user decision"
  write_user_decision_required_status "gateway_process_exited" "gateway_unreachable"

  while kill -0 "$RUNTIME_PID" >/dev/null 2>&1; do
    DECISION_LINES="$(read_gateway_decision || true)"
    if [ -z "${DECISION_LINES:-}" ]; then
      sleep 1
      continue
    fi
    log_supervisor "raw decision lines captured: $(printf '%s' "$DECISION_LINES" | tr '\n' '|' )"

    ACTION="$(printf '%s\n' "$DECISION_LINES" | sed -n '1p')"
    FAMILY_ID="$(printf '%s\n' "$DECISION_LINES" | sed -n '2p')"
    TRANSITION_REASON="$(printf '%s\n' "$DECISION_LINES" | sed -n '3p')"
    DECISION_SOURCE="$(printf '%s\n' "$DECISION_LINES" | sed -n '4p')"
    log_supervisor "decision payload received action='${ACTION}' family='${FAMILY_ID}' reason='${TRANSITION_REASON}' source='${DECISION_SOURCE}'"
    clear_gateway_decision_file

    if [ -z "$ACTION" ]; then
      log_supervisor "decision ignored because action is empty"
      sleep 1
      continue
    fi

    echo "[TRACK_B] Received user decision '${ACTION}' for family '${FAMILY_ID}'. Restarting gateway ..."
    log_supervisor "gateway restart requested after action='${ACTION}' family='${FAMILY_ID}'"
    write_manual_recovery_status "${TRANSITION_REASON:-user_requested_gateway_restart}" "gateway_restart_requested"
    start_adapter_process
    if wait_for_health \
      "Adapter(restart)" \
      "http://127.0.0.1:${ADAPTER_PORT}/health" \
      "$ADAPTER_PID" \
      "$LOG_DIR/adapter_start.out.log" \
      "$LOG_DIR/adapter_start.err.log" \
      15; then
      echo "[TRACK_B] Gateway recovered after user decision."
      log_supervisor "gateway restart succeeded after action='${ACTION}' family='${FAMILY_ID}'"
      sleep "$TRACK_B_RECOVERY_SETTLE_SECONDS"
      clear_track_b_status_file
      break
    fi

    echo "[TRACK_B] Gateway restart failed after user decision."
    log_supervisor "gateway restart failed after action='${ACTION}' family='${FAMILY_ID}'"
    write_user_decision_required_status "gateway_restart_failed_after_user_action" "gateway_restart_failed"
  done

  if ! kill -0 "$RUNTIME_PID" >/dev/null 2>&1; then
    break
  fi
done
kill "$SUPERVISOR_PID" "$RUNTIME_PID" >/dev/null 2>&1 || true
