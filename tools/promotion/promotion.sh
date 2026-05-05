#!/usr/bin/env bash
# OmniMemora Promotion Automation - Entry Point
# =============================================
# 统一 promotion 入口，支持 runtime / adapter / ui 及组合
#
# 用法:
#   promotion runtime          # 仅 runtime
#   promotion adapter         # 仅 adapter
#   promotion ui              # 仅 UI
#   promotion runtime+adapter # runtime + adapter
#   promotion adapter+ui      # adapter + UI
#   promotion runtime+adapter+ui  # 全部
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
LIB_DIR="$SCRIPT_DIR/promotion/lib"
LOG_DIR="$PROJECT_ROOT/tools/verification/logs"
TOOLS_DIR="$PROJECT_ROOT/tools"
SERVICE_DIR="${OMNIMEMORA_SERVICE_DIR:-$HOME/.omnimemora/service}"
CURRENT_SERVICE_DIR="$SERVICE_DIR/current"

# 预设
RUNTIME_PORT="${RUNTIME_PORT:-8765}"
ADAPTER_PORT="${ADAPTER_PORT:-18011}"
UI_PORT="${UI_PORT:-5173}"

# 默认环境
export PATH="/usr/local/bin:$PATH"
PYTHON_BIN="${PYTHON_BIN:-$(command -v python3 || true)}"
GO_BIN="${GO_BIN:-$(command -v go || true)}"
if [ -z "$GO_BIN" ]; then
    for p in /usr/local/go/bin/go /opt/homebrew/bin/go /usr/bin/go; do
        if [ -x "$p" ]; then
            GO_BIN="$p"
            break
        fi
    done
fi
NODE_BIN="${NODE_BIN:-$(command -v node || true)}"
NPM_BIN="${NPM_BIN:-$(command -v npm || true)}"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info()  { echo -e "${GREEN}[INFO]${NC} $*"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*"; }

# 初始化日志
mkdir -p "$LOG_DIR"
PROMOTION_LOG="$LOG_DIR/promotion_$(date '+%Y%m%d_%H%M%S').log"

log_output() {
    tee -a "$PROMOTION_LOG"
}

# 读取 running reality 组件状态
read_running_reality_state() {
    local runtime_state="unknown"
    local adapter_state="unknown"
    local ui_state="unknown"

    if curl -sf "http://127.0.0.1:${RUNTIME_PORT}/health" >/dev/null 2>&1; then
        runtime_state="healthy"
    elif curl -sf --connect-timeout 2 "http://127.0.0.1:${RUNTIME_PORT}/health" >/dev/null 2>&1; then
        runtime_state="unreachable"
    else
        runtime_state="not_running"
    fi

    if curl -sf "http://127.0.0.1:${ADAPTER_PORT}/health" >/dev/null 2>&1; then
        adapter_state="healthy"
    elif curl -sf --connect-timeout 2 "http://127.0.0.1:${ADAPTER_PORT}/health" >/dev/null 2>&1; then
        adapter_state="unreachable"
    else
        adapter_state="not_running"
    fi

    if curl -sf --connect-timeout 2 "http://127.0.0.1:${UI_PORT}/" >/dev/null 2>&1; then
        ui_state="healthy"
    elif [ -n "${NODE_BIN:-}" ] && [ -n "${NPM_BIN:-}" ]; then
        ui_state="not_running"
    else
        ui_state="no_node"
    fi

    echo "runtime=$runtime_state adapter=$adapter_state ui=$ui_state"
}

# 读取 adapter runtime fingerprint（pid|started_at|code_source_main）
read_adapter_fingerprint() {
    local endpoint="http://127.0.0.1:${ADAPTER_PORT}/debug/runtime_fingerprint"
    local payload
    payload=$(curl -sf --connect-timeout 5 "$endpoint" 2>/dev/null || true)
    if [ -z "$payload" ]; then
        echo "unknown|unknown|unknown"
        return 1
    fi

    local parsed
    parsed=$(printf '%s' "$payload" | python3 -c '
import json, sys
try:
    obj = json.load(sys.stdin)
    pid = str(obj.get("pid", "unknown"))
    started = str(obj.get("started_at", "unknown"))
    code_source = obj.get("code_source", {}) or {}
    main_src = str(code_source.get("5_connectors.adapter.main", "unknown"))
    print(f"{pid}|{started}|{main_src}")
except Exception:
    print("unknown|unknown|unknown")
' 2>/dev/null || true)

    if [ -z "$parsed" ]; then
        echo "unknown|unknown|unknown"
        return 1
    fi
    echo "$parsed"
}

is_number() {
    local value="${1:-}"
    [[ "$value" =~ ^[0-9]+([.][0-9]+)?$ ]]
}

read_runtime_health_uptime() {
    local payload
    payload=$(curl -sf --connect-timeout 5 "http://127.0.0.1:${RUNTIME_PORT}/health" 2>/dev/null || true)
    if [ -z "$payload" ]; then
        echo "unknown"
        return 1
    fi
    local parsed
    parsed=$(printf '%s' "$payload" | python3 -c '
import json, sys
try:
    obj = json.load(sys.stdin)
    val = obj.get("uptime_seconds", "unknown")
    print(val)
except Exception:
    print("unknown")
' 2>/dev/null || true)
    if [ -z "$parsed" ]; then
        echo "unknown"
        return 1
    fi
    echo "$parsed"
}

read_runtime_pid() {
    local launchd_pid=""
    if command -v launchctl >/dev/null 2>&1; then
        launchd_pid=$(launchctl print "gui/$(id -u)/com.omnimemora.runtime" 2>/dev/null | awk '/pid = /{print $3; exit}' || true)
        if [ -n "$launchd_pid" ] && [[ "$launchd_pid" =~ ^[0-9]+$ ]] && [ "$launchd_pid" -gt 0 ]; then
            echo "$launchd_pid"
            return 0
        fi
    fi

    local pgrep_pid=""
    pgrep_pid=$(pgrep -f "omnimemora-runtime.*serve" 2>/dev/null | head -n 1 || true)
    if [ -n "$pgrep_pid" ] && [[ "$pgrep_pid" =~ ^[0-9]+$ ]] && [ "$pgrep_pid" -gt 0 ]; then
        echo "$pgrep_pid"
        return 0
    fi

    echo "unknown"
    return 1
}

read_runtime_command() {
    local pid="${1:-unknown}"
    if [ -z "$pid" ] || [ "$pid" = "unknown" ]; then
        echo "unknown"
        return 1
    fi
    local cmd=""
    cmd=$(ps -p "$pid" -o command= 2>/dev/null | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//' || true)
    if [ -z "$cmd" ]; then
        echo "unknown"
        return 1
    fi
    echo "$cmd"
}

# runtime fingerprint（pid|uptime_seconds|command）
read_runtime_fingerprint() {
    local pid uptime cmd
    pid=$(read_runtime_pid || true)
    uptime=$(read_runtime_health_uptime || true)
    cmd=$(read_runtime_command "$pid" || true)
    [ -n "$pid" ] || pid="unknown"
    [ -n "$uptime" ] || uptime="unknown"
    [ -n "$cmd" ] || cmd="unknown"
    echo "${pid}|${uptime}|${cmd}"
}

wait_runtime_health() {
    local retries="${1:-25}"
    local delay="${2:-1}"
    local i
    for ((i=1; i<=retries; i++)); do
        if curl -sf --connect-timeout 3 "http://127.0.0.1:${RUNTIME_PORT}/health" >/dev/null 2>&1; then
            return 0
        fi
        sleep "$delay"
    done
    return 1
}

runtime_fingerprint_indicates_change() {
    local pre_pid="$1"
    local pre_uptime="$2"
    local post_pid="$3"
    local post_uptime="$4"

    if [ -z "$post_pid" ] || [ "$post_pid" = "unknown" ]; then
        return 1
    fi

    if [ -n "$pre_pid" ] && [ "$pre_pid" != "unknown" ] && [ "$post_pid" = "$pre_pid" ]; then
        return 1
    fi

    if is_number "$pre_uptime" && is_number "$post_uptime"; then
        if awk -v pre="$pre_uptime" -v post="$post_uptime" 'BEGIN{exit !(post < pre)}'; then
            return 0
        fi
        # short window fallback: post uptime is fresh right after restart
        if awk -v post="$post_uptime" 'BEGIN{exit !(post <= 120)}'; then
            return 0
        fi
        return 1
    fi

    return 0
}

restart_runtime_with_method() {
    local method="$1"
    local service_runtime_dir="$2"
    local launchd_label="gui/$(id -u)/com.omnimemora.runtime"

    case "$method" in
        launchctl_kickstart_k)
            launchctl kickstart -k "$launchd_label" >/dev/null 2>&1
            ;;
        launchctl_stop_start)
            launchctl stop "$launchd_label" >/dev/null 2>&1 || true
            sleep 2
            launchctl start "$launchd_label" >/dev/null 2>&1
            ;;
        direct_kill_start_fallback|direct_kill_start)
            local runtime_pids
            runtime_pids=$(pgrep -f "omnimemora-runtime.*serve" 2>/dev/null || true)
            if [ -n "$runtime_pids" ]; then
                kill $runtime_pids 2>/dev/null || true
                sleep 2
            fi
            OMNIMEMORA_RUNTIME_PORT="$RUNTIME_PORT" \
            OMNIMEMORA_ADAPTER_PORT="$ADAPTER_PORT" \
            "$service_runtime_dir" serve >"$LOG_DIR/runtime_promotion.out.log" 2>"$LOG_DIR/runtime_promotion.err.log" &
            ;;
        *)
            return 1
            ;;
    esac

    return 0
}

# 前置条件校验
check_prerequisites() {
    log_info "=== 前置条件校验 ===" | log_output

    # 检查 worktree 是否在可控范围
    if ! git -C "$PROJECT_ROOT" rev-parse 2>/dev/null; then
        log_error "当前目录不是 git worktree 或不在仓库内"
        return 1
    fi

    # 检查 promotion 目标是否明确
    if [ -z "${TARGET:-}" ]; then
        log_error "未指定 promotion 目标，请使用: promotion runtime|adapter|ui|runtime+adapter|runtime+adapter+ui"
        return 1
    fi

    # 检查当前阶段结论是否已记录（检查 docs 目录是否有相关记录）
    if [ ! -d "$PROJECT_ROOT/docs" ]; then
        log_warn "docs 目录不存在，跳过阶段结论检查"
    fi

    # 检查 runtime 源码
    local runtime_src="$PROJECT_ROOT/4_core/local-runtime"
    if [ ! -d "$runtime_src" ]; then
        log_error "Runtime 源码目录不存在: $runtime_src"
        return 1
    fi

    # 检查 adapter 源码
    local adapter_src="$PROJECT_ROOT/5_connectors/adapter"
    if [ ! -d "$adapter_src" ]; then
        log_error "Adapter 源码目录不存在: $adapter_src"
        return 1
    fi

    # 检查 UI 源码
    local ui_src="$PROJECT_ROOT/6_console/demo-dashboard"
    if [[ "$TARGET" == *"ui"* ]] && [ ! -d "$ui_src" ]; then
        log_error "UI 源码目录不存在: $ui_src"
        return 1
    fi

    log_info "前置条件校验通过" | log_output
    return 0
}

# 解析目标组件
parse_target() {
    local target="$1"
    RUNTIME_NEEDED=0
    ADAPTER_NEEDED=0
    UI_NEEDED=0

    case "$target" in
        runtime)
            RUNTIME_NEEDED=1
            ;;
        adapter)
            ADAPTER_NEEDED=1
            ;;
        ui)
            UI_NEEDED=1
            ;;
        runtime+adapter)
            RUNTIME_NEEDED=1
            ADAPTER_NEEDED=1
            ;;
        adapter+ui)
            ADAPTER_NEEDED=1
            UI_NEEDED=1
            ;;
        runtime+adapter+ui)
            RUNTIME_NEEDED=1
            ADAPTER_NEEDED=1
            UI_NEEDED=1
            ;;
        *)
            log_error "未知目标: $target"
            return 1
            ;;
    esac
    return 0
}

# Runtime promotion
promote_runtime() {
    log_info "=== Runtime Promotion ===" | log_output

    local runtime_src="$PROJECT_ROOT/4_core/local-runtime"
    local runtime_bin="$TOOLS_DIR/omnimemora-runtime"
    local startup_repair_src="$TOOLS_DIR/start_omnimemora_daemon.sh"
    local service_runtime_dir="$CURRENT_SERVICE_DIR/tools/omnimemora-runtime"
    local service_startup_repair="$CURRENT_SERVICE_DIR/tools/start_omnimemora_daemon.sh"

    # 1. 构建
    log_info "[1/4] 构建 Runtime ..." | log_output
    if ! (cd "$runtime_src" && "$GO_BIN" build -o "$runtime_bin" .); then
        log_error "Runtime 构建失败"
        echo "failed:build" >> "$PROMOTION_LOG"
        return 1
    fi
    log_info "Runtime 构建成功" | log_output

    # 2. 同步到 service/current
    log_info "[2/5] 同步 Runtime 到 $CURRENT_SERVICE_DIR ..." | log_output
    mkdir -p "$CURRENT_SERVICE_DIR/tools"
    cp "$runtime_bin" "$service_runtime_dir"
    if [ ! -f "$startup_repair_src" ]; then
        log_error "Product startup repair launcher 不存在: $startup_repair_src"
        echo "failed:startup_repair_launcher_missing" >> "$PROMOTION_LOG"
        return 1
    fi
    cp "$startup_repair_src" "$service_startup_repair"
    chmod +x "$service_startup_repair"
    log_info "Runtime 同步完成" | log_output

    # 2b. 同步 CSP-001 compile strategy policy bundle
    local policy_src="$runtime_src/config/compile_strategy_policies"
    local policy_dest="$CURRENT_SERVICE_DIR/tools/config/compile_strategy_policies"
    log_info "[2b/5] 同步 Compile Strategy Policy Bundle ..." | log_output
    if [ ! -d "$policy_src" ]; then
        log_error "Policy bundle 源目录不存在（应为 $policy_src）：promotion 必须失败，禁止静默 fallback"
        echo "runtime_compile_strategy_policy_bundle=missing" >> "$PROMOTION_LOG"
        echo "runtime_compile_strategy_policy_active_version=" >> "$PROMOTION_LOG"
        echo "runtime_compile_strategy_policy_bundle_path=" >> "$PROMOTION_LOG"
        echo "failed:policy_bundle_missing" >> "$PROMOTION_LOG"
        return 1
    fi
    mkdir -p "$policy_dest"
    cp "$policy_src/manifest.json" "$policy_dest/"
    cp "$policy_src/local-default-v1.json" "$policy_dest/"
    log_info "  Policy bundle 同步完成" | log_output

    # 2c. 验证 policy bundle（manifest 必须存在且有效）
    local manifest="$policy_dest/manifest.json"
    if [ ! -f "$manifest" ]; then
        log_error "Policy manifest.json 未找到：promotion 必须失败"
        echo "runtime_compile_strategy_policy_bundle=missing" >> "$PROMOTION_LOG"
        echo "failed:policy_manifest_missing" >> "$PROMOTION_LOG"
        return 1
    fi
    local active_version
    active_version=$(python3 -c "import json; d=json.load(open('$manifest')); print(d.get('active_version','unknown'))" 2>/dev/null || echo "unknown")
    log_info "  Policy bundle 验证通过: active_version=$active_version" | log_output
    echo "runtime_compile_strategy_policy_bundle=present" >> "$PROMOTION_LOG"
    echo "runtime_compile_strategy_policy_active_version=$active_version" >> "$PROMOTION_LOG"
    echo "runtime_compile_strategy_policy_bundle_path=$policy_dest" >> "$PROMOTION_LOG"

    # 3. 受控重载 + restart truth gate
    log_info "[3/5] 重载 Runtime ..." | log_output
    local pre_fingerprint pre_pid pre_uptime pre_command
    pre_fingerprint=$(read_runtime_fingerprint)
    IFS='|' read -r pre_pid pre_uptime pre_command <<< "$pre_fingerprint"
    log_info "  pre-fingerprint: pid=$pre_pid uptime_seconds=$pre_uptime" | log_output
    log_info "  pre-command: $pre_command" | log_output
    echo "runtime_pre_pid=$pre_pid" >> "$PROMOTION_LOG"
    echo "runtime_pre_uptime_seconds=$pre_uptime" >> "$PROMOTION_LOG"
    echo "runtime_pre_command=$pre_command" >> "$PROMOTION_LOG"

    local restart_method="unknown"
    local restart_truth="unchanged"
    local post_pid="unknown"
    local post_uptime="unknown"
    local post_command="unknown"
    local launchctl_available=0
    if command -v launchctl >/dev/null 2>&1; then
        launchctl_available=1
    fi

    local methods=()
    if [ "$launchctl_available" -eq 1 ]; then
        methods=("launchctl_kickstart_k" "launchctl_stop_start" "direct_kill_start_fallback")
    else
        methods=("direct_kill_start")
    fi

    local method
    for method in "${methods[@]}"; do
        case "$method" in
            launchctl_kickstart_k)
                log_info "  优先使用 launchctl kickstart -k 重启 Runtime ..." | log_output
                ;;
            launchctl_stop_start)
                log_warn "  kickstart 未生效，回退 launchctl stop/start ..." | log_output
                ;;
            direct_kill_start_fallback)
                log_warn "  stop/start 未生效，回退 direct kill+start ..." | log_output
                ;;
            direct_kill_start)
                log_info "  launchctl 不可用，使用 direct kill+start ..." | log_output
                ;;
        esac

        if ! restart_runtime_with_method "$method" "$service_runtime_dir"; then
            log_warn "  重启方法失败: $method" | log_output
            continue
        fi

        if ! wait_runtime_health 30 1; then
            log_warn "  Runtime 健康未恢复: $method" | log_output
            continue
        fi

        local current_fingerprint
        current_fingerprint=$(read_runtime_fingerprint)
        IFS='|' read -r post_pid post_uptime post_command <<< "$current_fingerprint"
        log_info "  post-fingerprint[$method]: pid=$post_pid uptime_seconds=$post_uptime" | log_output
        log_info "  post-command[$method]: $post_command" | log_output

        if runtime_fingerprint_indicates_change "$pre_pid" "$pre_uptime" "$post_pid" "$post_uptime"; then
            restart_method="$method"
            restart_truth="changed"
            break
        fi
    done

    # 4. 验证
    log_info "[4/5] 验证 Runtime ..." | log_output
    echo "runtime_post_pid=$post_pid" >> "$PROMOTION_LOG"
    echo "runtime_post_uptime_seconds=$post_uptime" >> "$PROMOTION_LOG"
    echo "runtime_post_command=$post_command" >> "$PROMOTION_LOG"
    echo "runtime_restart_truth=$restart_truth" >> "$PROMOTION_LOG"
    echo "runtime_restart_method=$restart_method" >> "$PROMOTION_LOG"

    if ! curl -sf "http://127.0.0.1:${RUNTIME_PORT}/health" >/dev/null 2>&1; then
        log_error "Runtime 健康检查失败：API 不可达" | log_output
        echo "runtime:failed:api_unreachable" >> "$PROMOTION_LOG"
        return 1
    fi

    if [ -z "$post_pid" ] || [ "$post_pid" = "unknown" ]; then
        log_error "Runtime restart 失败：post pid 为空或 unknown" | log_output
        echo "runtime:failed:runtime_restart_not_effective" >> "$PROMOTION_LOG"
        return 1
    fi

    if [ -n "$pre_pid" ] && [ "$pre_pid" != "unknown" ] && [ "$post_pid" = "$pre_pid" ]; then
        log_error "Runtime restart 失败：pid 未变化 (pre=$pre_pid post=$post_pid)" | log_output
        echo "runtime:failed:runtime_restart_pid_unchanged" >> "$PROMOTION_LOG"
        return 1
    fi

    if is_number "$pre_uptime" && is_number "$post_uptime"; then
        if ! awk -v pre="$pre_uptime" -v post="$post_uptime" 'BEGIN{exit (post < pre || post <= 120) ? 0 : 1}'; then
            log_error "Runtime restart 失败：uptime 未重置且不在短窗口 (pre=$pre_uptime post=$post_uptime)" | log_output
            echo "runtime:failed:runtime_restart_not_effective" >> "$PROMOTION_LOG"
            return 1
        fi
    fi

    local expected_runtime_cmd="$CURRENT_SERVICE_DIR/tools/omnimemora-runtime"
    if [[ "$post_command" != *"$expected_runtime_cmd"* ]]; then
        log_error "Runtime command 不匹配 running reality: $post_command" | log_output
        echo "runtime:failed:command_mismatch" >> "$PROMOTION_LOG"
        return 1
    fi

    if [ "$restart_truth" != "changed" ]; then
        log_error "Runtime restart truth 未通过：fingerprint 未变化" | log_output
        echo "runtime:failed:runtime_restart_not_effective" >> "$PROMOTION_LOG"
        return 1
    fi

    log_info "Runtime 健康检查通过，restart truth 已通过" | log_output
    echo "runtime:promoted" >> "$PROMOTION_LOG"
    return 0
}

# Adapter promotion
promote_adapter() {
    log_info "=== Adapter Promotion ===" | log_output

    local adapter_src="$PROJECT_ROOT/5_connectors/adapter"
    local adapter_launcher="$TOOLS_DIR/_run_adapter.py"

    # 1. 确定实际运行文件集合
    log_info "[1/4] 分析 Adapter 运行文件 ..." | log_output
    local adapter_files=$(find "$adapter_src" -name "*.py" -type f 2>/dev/null | grep -v __pycache__ | grep -v "\.pyc" || true)
    if [ -z "$adapter_files" ]; then
        log_error "未找到 Adapter Python 文件"
        echo "failed:no_adapter_files" >> "$PROMOTION_LOG"
        return 1
    fi
    log_info "找到 $(echo "$adapter_files" | wc -l) 个 Python 文件" | log_output

    # 2. 同步到 service/current
    log_info "[2/4] 同步 Adapter 文件到 $CURRENT_SERVICE_DIR ..." | log_output
    mkdir -p "$CURRENT_SERVICE_DIR/5_connectors/adapter"
    for f in $adapter_files; do
        # 去掉 adapter_src 前缀，还原相对路径
        local relpath="${f#$adapter_src/}"
        local dest="$CURRENT_SERVICE_DIR/5_connectors/adapter/$relpath"
        mkdir -p "$(dirname "$dest")"
        cp "$f" "$dest"
    done
    # 同步 logic 依赖（adapter 运行态依赖 4_core/logic）
    # 这是 adapter dependency sync，不是 runtime promotion 扩面。
    local logic_src="$PROJECT_ROOT/4_core/logic"
    if [ -d "$logic_src" ]; then
        log_info "[2.5/4] 同步 Adapter logic 依赖到 $CURRENT_SERVICE_DIR ..." | log_output
        local logic_files
        logic_files=$(find "$logic_src" -name "*.py" -type f 2>/dev/null | grep -v __pycache__ | grep -v "\.pyc" || true)
        if [ -n "$logic_files" ]; then
            mkdir -p "$CURRENT_SERVICE_DIR/4_core/logic"
            for f in $logic_files; do
                local relpath="${f#$logic_src/}"
                local dest="$CURRENT_SERVICE_DIR/4_core/logic/$relpath"
                mkdir -p "$(dirname "$dest")"
                cp "$f" "$dest"
            done
            log_info "  已同步 $(echo "$logic_files" | wc -l) 个 logic Python 文件" | log_output
        else
            log_warn "  未找到 logic Python 文件，跳过 logic 依赖同步" | log_output
        fi
    else
        log_warn "  logic 源码目录不存在: $logic_src，跳过 logic 依赖同步" | log_output
    fi

    # 同步 launcher
    cp "$adapter_launcher" "$CURRENT_SERVICE_DIR/tools/_run_adapter.py"

    # 3. 重启 Adapter（通过 launchd 管理）
    log_info "[3/4] 重启 Adapter ..." | log_output
    local pre_fingerprint pre_pid pre_started_at pre_code_source
    pre_fingerprint=$(read_adapter_fingerprint)
    IFS='|' read -r pre_pid pre_started_at pre_code_source <<< "$pre_fingerprint"
    log_info "  pre-fingerprint: pid=$pre_pid started_at=$pre_started_at" | log_output
    log_info "  pre-code-source: $pre_code_source" | log_output
    echo "adapter_pre_pid=$pre_pid" >> "$PROMOTION_LOG"
    echo "adapter_pre_started_at=$pre_started_at" >> "$PROMOTION_LOG"

    local restart_method="unknown"
    local launchd_label="gui/$(id -u)/com.omnimemora.adapter"
    if command -v launchctl >/dev/null 2>&1; then
        log_info "  优先使用 launchctl kickstart -k 重启 Adapter ..." | log_output
        if launchctl kickstart -k "$launchd_label" >/dev/null 2>&1; then
            restart_method="launchctl_kickstart_k"
        else
            log_warn "  kickstart -k 失败，回退到 stop/start ..." | log_output
            if launchctl stop "$launchd_label" >/dev/null 2>&1; then
                sleep 2
                if launchctl start "$launchd_label" >/dev/null 2>&1; then
                    restart_method="launchctl_stop_start"
                fi
            fi
            if [ "$restart_method" = "unknown" ]; then
                log_warn "  stop/start 失败，回退到直接 kill+start ..." | log_output
                local adapter_pid_fallback
                adapter_pid_fallback=$(pgrep -f "_run_adapter" 2>/dev/null || true)
                if [ -n "$adapter_pid_fallback" ]; then
                    kill "$adapter_pid_fallback" 2>/dev/null || true
                    sleep 2
                fi
                cd "$CURRENT_SERVICE_DIR"
                PORT="$ADAPTER_PORT" \
                MEMORY_BACKEND_URL="http://127.0.0.1:${RUNTIME_PORT}" \
                "$PYTHON_BIN" "$CURRENT_SERVICE_DIR/tools/_run_adapter.py" >"$LOG_DIR/adapter_promotion.out.log" 2>"$LOG_DIR/adapter_promotion.err.log" &
                restart_method="direct_kill_start_fallback"
            fi
        fi
    else
        # Fallback: 直接重启
        log_info "  launchctl 不可用，使用直接重启 ..." | log_output
        local adapter_pid
        adapter_pid=$(pgrep -f "_run_adapter" 2>/dev/null || true)
        if [ -n "$adapter_pid" ]; then
            kill "$adapter_pid" 2>/dev/null || true
            sleep 2
        fi
        cd "$CURRENT_SERVICE_DIR"
        PORT="$ADAPTER_PORT" \
        MEMORY_BACKEND_URL="http://127.0.0.1:${RUNTIME_PORT}" \
        "$PYTHON_BIN" "$CURRENT_SERVICE_DIR/tools/_run_adapter.py" >"$LOG_DIR/adapter_promotion.out.log" 2>"$LOG_DIR/adapter_promotion.err.log" &
        restart_method="direct_kill_start"
    fi
    log_info "  重启方法: $restart_method" | log_output
    sleep 3

    # 4. 三层验证 + restart truth gate
    log_info "[4/4] 验证 Adapter 三层 reality + restart truth ..." | log_output

    # plist reality (launchctl print)
    local plist_ok=0
    if command -v launchctl >/dev/null 2>&1; then
        if launchctl print "gui/$(id -u)/com.omnimemora.adapter" >/dev/null 2>&1; then
            plist_ok=1
            log_info "  [plist reality] OK" | log_output
        else
            log_warn "  [plist reality] 未通过 launchctl 检查（可能由本次 promotion 重启覆盖）" | log_output
        fi
    fi

    # process reality
    local process_ok=0
    if pgrep -f "_run_adapter" >/dev/null 2>&1; then
        process_ok=1
        log_info "  [process reality] OK" | log_output
    else
        log_warn "  [process reality] 未通过（可能由本次 promotion 重启覆盖）" | log_output
    fi

    # API reality
    local api_ok=0
    if curl -sf "http://127.0.0.1:${ADAPTER_PORT}/health" >/dev/null 2>&1; then
        api_ok=1
        log_info "  [API reality :${ADAPTER_PORT}] OK" | log_output
    else
        log_error "  [API reality] 失败"
        echo "adapter_restart_truth=unknown" >> "$PROMOTION_LOG"
        echo "adapter_code_source=unknown" >> "$PROMOTION_LOG"
        echo "adapter_restart_method=$restart_method" >> "$PROMOTION_LOG"
        echo "adapter:failed:api_unreachable" >> "$PROMOTION_LOG"
        return 1
    fi

    local post_fingerprint post_pid post_started_at post_code_source
    post_fingerprint=$(read_adapter_fingerprint)
    IFS='|' read -r post_pid post_started_at post_code_source <<< "$post_fingerprint"

    local restart_truth="unknown"
    if [ "$pre_started_at" != "unknown" ] && [ "$post_started_at" != "unknown" ]; then
        if [ "$pre_started_at" != "$post_started_at" ]; then
            restart_truth="changed"
        else
            restart_truth="unchanged"
        fi
    fi

    echo "adapter_post_pid=$post_pid" >> "$PROMOTION_LOG"
    echo "adapter_post_started_at=$post_started_at" >> "$PROMOTION_LOG"
    echo "adapter_restart_truth=$restart_truth" >> "$PROMOTION_LOG"
    echo "adapter_code_source=$post_code_source" >> "$PROMOTION_LOG"
    echo "adapter_restart_method=$restart_method" >> "$PROMOTION_LOG"

    log_info "  post-fingerprint: pid=$post_pid started_at=$post_started_at" | log_output
    log_info "  post-code-source: $post_code_source" | log_output
    log_info "  restart-truth: $restart_truth" | log_output

    local expected_code_source="$CURRENT_SERVICE_DIR/5_connectors/adapter/main.py"
    if [ "$post_code_source" != "$expected_code_source" ]; then
        log_error "Adapter code_source 未指向 running reality: $expected_code_source" | log_output
        echo "adapter:failed:code_source_mismatch" >> "$PROMOTION_LOG"
        return 1
    fi

    if [ "$restart_truth" != "changed" ]; then
        log_error "Adapter restart 未生效：started_at 未变化或不可判定" | log_output
        echo "failed:adapter_restart_not_effective" >> "$PROMOTION_LOG"
        echo "adapter:failed:adapter_restart_not_effective" >> "$PROMOTION_LOG"
        return 1
    fi

    if [ "$pre_pid" = "$post_pid" ]; then
        log_error "Adapter restart 异常：started_at 已变化但 pid 未变化（默认失败）" | log_output
        echo "failed:adapter_restart_pid_unchanged" >> "$PROMOTION_LOG"
        echo "adapter:failed:adapter_restart_pid_unchanged" >> "$PROMOTION_LOG"
        return 1
    fi

    if [ "$api_ok" -eq 1 ]; then
        log_info "Adapter promotion 成功（restart truth 已通过）" | log_output
        echo "adapter:promoted" >> "$PROMOTION_LOG"
        return 0
    else
        log_error "Adapter promotion 失败"
        echo "adapter:failed" >> "$PROMOTION_LOG"
        return 1
    fi
}

# UI promotion
promote_ui() {
    log_info "=== UI Promotion ===" | log_output

    local ui_src="$PROJECT_ROOT/6_console/demo-dashboard"

    # 1. 环境检查
    log_info "[1/6] 环境检查 ..." | log_output
    if [ -z "${NODE_BIN:-}" ] || [ -z "${NPM_BIN:-}" ]; then
        log_error "Node.js 或 npm 未安装"
        echo "failed:no_node" >> "$PROMOTION_LOG"
        return 1
    fi

    local node_version
    node_version=$("$NODE_BIN" --version 2>/dev/null || echo "unknown")
    local npm_version
    npm_version=$("$NPM_BIN" --version 2>/dev/null || echo "unknown")
    log_info "  Node: $node_version, npm: $npm_version" | log_output

    # 2. npm install（如需要）
    log_info "[2/6] 检查依赖 ..." | log_output
    if [ ! -d "$ui_src/node_modules" ]; then
        log_info "  执行 npm install ..." | log_output
        cd "$ui_src"
        "$NPM_BIN" install >"$LOG_DIR/ui_npm_install.log" 2>&1 || {
            log_error "npm install 失败"
            echo "failed:npm_install" >> "$PROMOTION_LOG"
            return 1
        }
    fi

    # 3. build
    log_info "[3/6] 执行 npm run build ..." | log_output
    cd "$ui_src"
    "$NPM_BIN" run build >"$LOG_DIR/ui_build.log" 2>&1 || {
        log_error "npm run build 失败"
        echo "failed:build" >> "$PROMOTION_LOG"
        return 1
    }
    log_info "UI build 成功" | log_output

    # 4. bring-up (npm run dev)
    log_info "[4/6] 启动 UI 开发服务器 ..." | log_output
    # 停止现有 UI 进程
    pkill -f "vite" 2>/dev/null || true
    sleep 1

    # 启动新进程
    cd "$ui_src"
    PATH="/usr/local/bin:$PATH" "$NPM_BIN" run dev >"$LOG_DIR/ui_dev.log" 2>&1 &
    sleep 5

    # 5. 验证
    log_info "[5/6] 验证 UI ..." | log_output
    local ui_root_ok=0
    local ui_agents_ok=0
    if curl -sf --connect-timeout 5 "http://127.0.0.1:${UI_PORT}/" >/dev/null 2>&1; then
        ui_root_ok=1
        log_info "  [UI root] OK" | log_output
    else
        log_warn "  [UI root] 失败或响应慢" | log_output
    fi

    if curl -sf --connect-timeout 5 "http://127.0.0.1:${UI_PORT}/agents?tenant=all" >/dev/null 2>&1; then
        ui_agents_ok=1
        log_info "  [UI /agents?tenant=all] OK" | log_output
    else
        log_warn "  [UI /agents?tenant=all] 失败或响应慢" | log_output
    fi

    # 6. 基本对位（与 adapter API 对照）
    log_info "[6/6] UI 对位检查 ..." | log_output
    local adapter_agents
    adapter_agents=$(curl -sf "http://127.0.0.1:${ADAPTER_PORT}/agents/control" 2>/dev/null | head -c 200 || echo "{}")
    log_info "  Adapter /agents/control 响应: $(echo "$adapter_agents" | head -c 100)..." | log_output

    # 两个验证都必须通过才算成功
    if [ "$ui_root_ok" -eq 1 ] && [ "$ui_agents_ok" -eq 1 ]; then
        log_info "UI promotion 成功" | log_output
        echo "ui:promoted" >> "$PROMOTION_LOG"
        return 0
    else
        log_error "UI promotion 失败（部分验证未通过）" | log_output
        echo "ui:failed" >> "$PROMOTION_LOG"
        return 1
    fi
}

# 写入 deployed-state marker
write_deployed_state_marker() {
    local final_status="$1"
    local repo_rev="$2"

    mkdir -p "$CURRENT_SERVICE_DIR"

    local marker_file="$CURRENT_SERVICE_DIR/.omnimemora_promotion_state.json"
    local timestamp
    timestamp=$(date -u '+%Y-%m-%dT%H:%M:%S')

    # Parse promotion log to find actual primary_breakpoint.
    # Component-level failure lines look like:
    #   runtime:failed:health_check
    #   adapter:failed:api_unreachable
    #   failed:build
    #   ui:failed
    # Valid breakpoint vocabulary: build, file_sync, reload, health_check,
    #   ui_bringup, ui_alignment, prerequisite_failed, none
    local primary_breakpoint="none"
    if [ -f "$PROMOTION_LOG" ]; then
        local failed_line
        failed_line=$(grep -m1 -E '^(runtime|adapter|ui):failed(:|$)' "$PROMOTION_LOG" 2>/dev/null || true)
        if [ -n "$failed_line" ]; then
            # Extract the failure reason (last field after the last colon)
            local reason="${failed_line##*:}"
            # Bare "failed" with no reason is not actionable; map to "unknown"
            if [ "$reason" = "failed" ] || [ -z "$reason" ]; then
                primary_breakpoint="unknown"
            else
                primary_breakpoint="$reason"
            fi
        fi
    fi

    cat > "$marker_file" << EOF
{
  "timestamp": "$timestamp",
  "target": "$TARGET",
  "repo_revision": "$repo_rev",
  "final_status": "$final_status",
  "primary_breakpoint": "$primary_breakpoint",
  "log_file": "$PROMOTION_LOG"
}
EOF
    log_info "Deployed-state marker written: $marker_file"
}

# 输出结构化结果
output_result() {
    local final_status="$1"
    local repo_rev
    repo_rev=$(git -C "$PROJECT_ROOT" rev-parse --short HEAD 2>/dev/null || echo "unknown")

    echo ""
    log_info "=== Promotion 结果 ==="
    echo "promotion_target: $TARGET"
    echo "repo_revision: $repo_rev"
    echo "running_reality_before: $(cat "$LOG_DIR/running_reality_before.txt" 2>/dev/null || echo 'unknown')"
    echo "running_reality_after: $(read_running_reality_state)"
    echo "final_status: $final_status"
    echo "log_file: $PROMOTION_LOG"

    # Write deployed-state marker
    write_deployed_state_marker "$final_status" "$repo_rev"
}

# 主流程
main() {
    if [ $# -lt 1 ]; then
        echo "用法: promotion <target>"
        echo "  target: runtime|adapter|ui|runtime+adapter|adapter+ui|runtime+adapter+ui"
        exit 1
    fi

    TARGET="$1"
    log_info "OmniMemora Promotion 入口"
    log_info "目标: $TARGET"
    log_info "项目目录: $PROJECT_ROOT"
    log_info "日志: $PROMOTION_LOG"

    # 记录初始状态
    read_running_reality_state > "$LOG_DIR/running_reality_before.txt"

    # 解析目标
    parse_target "$TARGET" || exit 1

    # 前置条件校验
    if ! check_prerequisites; then
        log_error "前置条件校验失败"
        output_result "prerequisite_failed"
        exit 1
    fi

    # 执行 promotion
    local runtime_result=0
    local adapter_result=0
    local ui_result=0

    if [ "$RUNTIME_NEEDED" -eq 1 ]; then
        if ! promote_runtime; then
            runtime_result=1
        fi
    fi

    if [ "$ADAPTER_NEEDED" -eq 1 ]; then
        if ! promote_adapter; then
            adapter_result=1
        fi
    fi

    if [ "$UI_NEEDED" -eq 1 ]; then
        if ! promote_ui; then
            ui_result=1
        fi
    fi

    # 输出结果
    if [ "$runtime_result" -eq 0 ] && [ "$adapter_result" -eq 0 ] && [ "$ui_result" -eq 0 ]; then
        output_result "running_reality_promoted"
        exit 0
    elif [ "$runtime_result" -eq 1 ] || [ "$adapter_result" -eq 1 ]; then
        output_result "promotion_failed"
        exit 1
    else
        output_result "running_reality_partial"
        exit 0
    fi
}

main "$@"
