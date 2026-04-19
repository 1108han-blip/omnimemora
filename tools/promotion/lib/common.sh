#!/usr/bin/env bash
# OmniMemora Promotion - 通用工具库
# ================================
# 提供 promotion 流程中共用的工具函数

# 等待服务健康
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

# 检查命令是否存在
require_command() {
    local cmd="$1"
    local name="${2:-$cmd}"
    if ! command -v "$cmd" >/dev/null 2>&1; then
        echo "[ERROR] $name is required but not found in PATH"
        return 1
    fi
    return 0
}

# 检查 Python 模块是否存在
require_python_module() {
    local module="$1"
    local python_bin="${2:-$(command -v python3)}"
    if ! "$python_bin" - <<'PY' 2>/dev/null
from importlib.util import find_spec
import sys
import sysconfig
module = sys.argv[1]
if find_spec(module) is None:
    print(module)
    sys.exit(1)
PY "$module"; then
        echo "[ERROR] Python module '$module' is required but not installed"
        return 1
    fi
    return 0
}

# 获取进程 PID（按命令行匹配）
get_pid_by_cmdline() {
    local pattern="$1"
    pgrep -f "$pattern" 2>/dev/null | head -1 || true
}

# 安全停止进程
safe_kill() {
    local pid="$1"
    local timeout_seconds="${2:-5}"
    if [ -z "$pid" ] || [ "$pid" -eq 0 ]; then
        return 0
    fi
    if kill -0 "$pid" >/dev/null 2>&1; then
        kill "$pid" 2>/dev/null || true
        for _ in $(seq 1 "$timeout_seconds"); do
            if ! kill -0 "$pid" >/dev/null 2>&1; then
                return 0
            fi
            sleep 1
        done
        kill -9 "$pid" 2>/dev/null || true
    fi
    return 0
}

# 检查服务是否健康
check_service_health() {
    local url="$1"
    local timeout="${2:-2}"
    curl -sf --connect-timeout "$timeout" "$url" >/dev/null 2>&1
}

# 获取 Git 提交hash
get_git_rev() {
    local dir="${1:-.}"
    git -C "$dir" rev-parse --short HEAD 2>/dev/null || echo "unknown"
}

# 生成结构化记录材料
generate_record_material() {
    local promotion_type="$1"
    local components="$2"
    local running_reality_result="$3"
    local base_complete="$4"
    local primary_breakpoint="$5"

    cat <<EOF
## Promotion Record

**promotion_type**: $promotion_type
**input_components**: $components
**running_reality_result**: $running_reality_result
**base_complete**: $base_complete
**primary_breakpoint**: $primary_breakpoint

EOF
}