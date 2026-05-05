#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUNTIME_PORT="${RUNTIME_PORT:-8765}"
ADAPTER_PORT="${PORT:-${OMNIMEMORA_ADAPTER_PORT:-18011}}"
LAUNCH_AGENT_DIR="${HOME}/Library/LaunchAgents"
RUNTIME_PLIST="${LAUNCH_AGENT_DIR}/com.omnimemora.runtime.plist"
ADAPTER_PLIST="${LAUNCH_AGENT_DIR}/com.omnimemora.adapter.plist"
LOG_DIR="${OMNIMEMORA_LOG_DIR:-${HOME}/.omnimemora/adapter}"
LOG_FILE="${OMNIMEMORA_AUTOSTART_LOG:-${LOG_DIR}/product_autostart.log}"

mkdir -p "$LOG_DIR"

log() {
  printf '%s %s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" "$*" >>"$LOG_FILE"
}

healthy() {
  local url="$1"
  curl -fsS --max-time 2 "$url" >/dev/null 2>&1
}

runtime_healthy() {
  healthy "http://127.0.0.1:${RUNTIME_PORT}/health"
}

adapter_healthy() {
  healthy "http://127.0.0.1:${ADAPTER_PORT}/health?mode=local"
}

wait_for_adapter() {
  local attempts="${1:-10}"
  local i
  for ((i = 1; i <= attempts; i++)); do
    if adapter_healthy; then
      return 0
    fi
    sleep 1
  done
  return 1
}

bootstrap_or_kickstart() {
  local label="$1"
  local plist="$2"
  local domain="gui/$(id -u)"
  if [ ! -f "$plist" ]; then
    log "plist_missing label=${label} plist=${plist}"
    return 1
  fi

  if launchctl print "${domain}/${label}" >/dev/null 2>&1; then
    log "kickstart label=${label}"
    launchctl kickstart -k "${domain}/${label}" >/dev/null 2>&1 || true
  else
    log "bootstrap label=${label} plist=${plist}"
    launchctl bootstrap "$domain" "$plist" >/dev/null 2>&1 || true
    launchctl kickstart -k "${domain}/${label}" >/dev/null 2>&1 || true
  fi
}

if runtime_healthy && adapter_healthy; then
  log "already_healthy runtime_port=${RUNTIME_PORT} adapter_port=${ADAPTER_PORT}"
  exit 0
fi

log "repair_start runtime_healthy=$(runtime_healthy && echo true || echo false) adapter_healthy=$(adapter_healthy && echo true || echo false)"

bootstrap_or_kickstart "com.omnimemora.runtime" "$RUNTIME_PLIST" || true
bootstrap_or_kickstart "com.omnimemora.adapter" "$ADAPTER_PLIST" || true

if wait_for_adapter 12; then
  log "repair_success method=launchd"
  exit 0
fi

log "launchd_repair_failed falling_back_to_start_sh root=${ROOT_DIR}"
exec "${ROOT_DIR}/start.sh"
