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
    local service_runtime_dir="$CURRENT_SERVICE_DIR/tools/omnimemora-runtime"

    # 1. 构建
    log_info "[1/4] 构建 Runtime ..." | log_output
    if ! (cd "$runtime_src" && "$GO_BIN" build -o "$runtime_bin" .); then
        log_error "Runtime 构建失败"
        echo "failed:build" >> "$PROMOTION_LOG"
        return 1
    fi
    log_info "Runtime 构建成功" | log_output

    # 2. 同步到 service/current
    log_info "[2/4] 同步 Runtime 到 $CURRENT_SERVICE_DIR ..." | log_output
    mkdir -p "$CURRENT_SERVICE_DIR/tools"
    cp "$runtime_bin" "$service_runtime_dir"
    log_info "Runtime 同步完成" | log_output

    # 3. 受控重载（通过 launchd 管理）
    log_info "[3/4] 重载 Runtime ..." | log_output
    if command -v launchctl >/dev/null 2>&1; then
        log_info "  通过 launchd 重载 Runtime ..." | log_output
        launchctl stop "gui/$(id -u)/com.omnimemora.runtime" 2>/dev/null || true
        sleep 2
        launchctl start "gui/$(id -u)/com.omnimemora.runtime" 2>/dev/null || true
    else
        # Fallback: 直接重启
        log_info "  launchctl 不可用，使用直接重启 ..." | log_output
        local runtime_pid
        runtime_pid=$(pgrep -f "omnimemora-runtime.*serve" 2>/dev/null || true)
        if [ -n "$runtime_pid" ]; then
            kill "$runtime_pid" 2>/dev/null || true
            sleep 2
        fi
        OMNIMEMORA_RUNTIME_PORT="$RUNTIME_PORT" \
        OMNIMEMORA_ADAPTER_PORT="$ADAPTER_PORT" \
        "$service_runtime_dir" serve >"$LOG_DIR/runtime_promotion.out.log" 2>"$LOG_DIR/runtime_promotion.err.log" &
    fi
    sleep 3

    # 4. 验证
    log_info "[4/4] 验证 Runtime ..." | log_output
    if curl -sf "http://127.0.0.1:${RUNTIME_PORT}/health" >/dev/null 2>&1; then
        log_info "Runtime 健康检查通过" | log_output
        echo "runtime:promoted" >> "$PROMOTION_LOG"
        return 0
    else
        log_error "Runtime 健康检查失败"
        echo "runtime:failed:health_check" >> "$PROMOTION_LOG"
        return 1
    fi
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
    if command -v launchctl >/dev/null 2>&1; then
        log_info "  通过 launchd 重载 Adapter ..." | log_output
        launchctl stop "gui/$(id -u)/com.omnimemora.adapter" 2>/dev/null || true
        sleep 2
        launchctl start "gui/$(id -u)/com.omnimemora.adapter" 2>/dev/null || true
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
    fi
    sleep 3

    # 4. 三层验证
    log_info "[4/4] 验证 Adapter 三层 reality ..." | log_output

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
        echo "failed:api_unreachable" >> "$PROMOTION_LOG"
        return 1
    fi

    if [ "$api_ok" -eq 1 ]; then
        log_info "Adapter promotion 成功" | log_output
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
