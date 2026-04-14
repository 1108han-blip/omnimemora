"""
dashboard.py - OmniMemora 本地可视化 Dashboard
==============================================
基于 Streamlit 的轻量本地可视化界面，用于实时查看服务状态与 usage log。

运行方式：
    streamlit run tools/dashboard.py
    # 或从项目根目录
    python -m streamlit run tools/dashboard.py

依赖：
    pip install streamlit requests

技术说明：
    - 只读 tools/usage_logs.jsonl 和 /health?mode=local
    - 不改 engine / adapter / wrapper 架构
    - 坏 JSON 行自动跳过，不中断页面
"""
import json
import os
import sys
from datetime import datetime
from typing import Any, Dict, List, Optional

import requests
import streamlit as st

# Lazy-load usage_insight to keep dashboard boot-fast even if insight module has issues
def _load_insight():
    try:
        sys.path.insert(0, os.path.dirname(__file__))
        from usage_insight import analyze, load_records
        return analyze, load_records
    except Exception:
        return None, None

# -------------------------------------------------------------------------
# Constants
# -------------------------------------------------------------------------
def _default_adapter_url() -> str:
    explicit = os.getenv("OMNIMEMORA_ADAPTER_URL", "").strip()
    if explicit:
        return explicit.rstrip("/")
    host = os.getenv("OMNIMEMORA_ADAPTER_HOST", "127.0.0.1").strip() or "127.0.0.1"
    port = os.getenv("OMNIMEMORA_ADAPTER_PORT", "18011").strip() or "18011"
    return f"http://{host}:{port}"


ADAPTER_URL = _default_adapter_url()
HEALTH_URL = f"{ADAPTER_URL}/health?mode=local"
LOG_FILE = os.path.join(os.path.dirname(__file__), "usage_logs.jsonl")

# -------------------------------------------------------------------------
# Data loading
# -------------------------------------------------------------------------

def load_usage_logs() -> List[Dict[str, Any]]:
    """Load all JSONL log entries, skipping malformed lines."""
    entries = []
    if not os.path.exists(LOG_FILE):
        return entries
    try:
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except Exception:
        pass
    return entries


def fetch_health() -> Optional[Dict[str, Any]]:
    """Fetch OmniMemora health endpoint. Returns None on failure."""
    try:
        r = requests.get(HEALTH_URL, timeout=5)
        if r.status_code < 400:
            return r.json()
    except requests.RequestException:
        pass
    except Exception:
        pass
    return None


def get_last_request_time(entries: List[Dict[str, Any]]) -> Optional[str]:
    """Return ISO timestamp of most recent entry, or None."""
    if not entries:
        return None
    timestamps = [e.get("timestamp") for e in entries if e.get("timestamp")]
    return max(timestamps) if timestamps else None


# -------------------------------------------------------------------------
# Stats computation
# -------------------------------------------------------------------------

def compute_stats(entries: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Compute summary statistics from log entries."""
    total = len(entries)

    # By task_type
    by_type: Dict[str, int] = {}
    for e in entries:
        t = e.get("task_type", "unknown")
        by_type[t] = by_type.get(t, 0) + 1

    # By agent_id
    by_agent: Dict[str, int] = {}
    for e in entries:
        aid = (e.get("_meta") or {}).get("agent_id", "unknown")
        by_agent[aid] = by_agent.get(aid, 0) + 1

    # Bypass ratio
    bypass_true = sum(1 for e in entries if e.get("context_bypass") is True)
    bypass_ratio = bypass_true / total if total > 0 else 0.0

    # Avg saved_tokens_estimate
    saved_vals = [
        (e.get("context_stats") or {}).get("saved_tokens_estimate", 0)
        for e in entries
    ]
    avg_saved = sum(saved_vals) / len(saved_vals) if saved_vals else 0.0

    return {
        "total": total,
        "by_type": by_type,
        "by_agent": by_agent,
        "bypass_true": bypass_true,
        "bypass_false": total - bypass_true,
        "bypass_ratio": bypass_ratio,
        "avg_saved_tokens": avg_saved,
    }


# -------------------------------------------------------------------------
# Streamlit page
# -------------------------------------------------------------------------

def main():
    st.set_page_config(
        page_title="OmniMemora Dashboard",
        page_icon="🧠",
        layout="wide",
    )


    # ---- Load data ----
    health = fetch_health()
    entries = load_usage_logs()
    stats = compute_stats(entries)
    last_ts = get_last_request_time(entries)

    # ---- Header ----
    st.title("🧠 OmniMemora Dashboard")
    st.markdown("— 本地实时监控（不连 Viking）")

    # ---- Section 1: Top Status Bar ----
    st.markdown("### 服务状态")
    cols = st.columns(4)

    # Service health
    if health is not None:
        status = health.get("status", "unknown")
        health_display = "✅ healthy" if status == "healthy" else f"⚠️ {status}"
    else:
        health_display = "❌ unavailable"
    cols[0].metric("OmniMemora 服务", health_display)

    # Adapter URL
    cols[1].metric("Adapter URL", ADAPTER_URL)

    # Last request time
    display_ts = last_ts.strftime("%m-%d %H:%M:%S") if last_ts and not isinstance(last_ts, str) else (last_ts or "—")
    cols[2].metric("最近请求", display_ts)

    # Log file status
    log_exists = os.path.exists(LOG_FILE)
    log_display = "✅ 存在" if log_exists else "❌ 不存在"
    log_lines = stats["total"]
    cols[3].metric("日志文件", f"{log_display}  ({log_lines} 条)")

    st.divider()

    # ---- Section 2: Summary ----
    st.markdown("### 汇总统计")

    summary_cols = st.columns(5)
    summary_cols[0].metric("总调用数", stats["total"])
    summary_cols[1].metric("Bypass=true", f"{stats['bypass_true']} ({stats['bypass_ratio']:.0%})")
    summary_cols[2].metric("Avg Saved Tokens", f"{stats['avg_saved_tokens']:.1f}")

    # task_type breakdown
    impl_count = stats["by_type"].get("implementation", 0)
    deci_count = stats["by_type"].get("decision", 0)
    cont_count = stats["by_type"].get("continuation", 0)
    unk_count = stats["by_type"].get("unknown", 0)

    summary_cols[3].metric(
        "Task Type 分布",
        f"impl:{impl_count} | dec:{deci_count} | cont:{cont_count}" + (f" | unk:{unk_count}" if unk_count else ""),
    )

    # Agent breakdown
    agent_str = " | ".join(f"{k}:{v}" for k, v in sorted(stats["by_agent"].items()))
    summary_cols[4].metric("By Agent", agent_str or "—")

    st.divider()

    # ---- Section 3: Filters ----
    st.markdown("### 筛选")
    filter_cols = st.columns(3)

    all_agents = sorted({(e.get("_meta") or {}).get("agent_id", "unknown") for e in entries})
    all_types = sorted({e.get("task_type", "unknown") for e in entries})

    with filter_cols[0]:
        selected_agent = st.selectbox("agent_id", ["全部"] + all_agents)
    with filter_cols[1]:
        selected_type = st.selectbox("task_type", ["全部"] + all_types)
    with filter_cols[2]:
        bypass_options = ["全部", "true", "false"]
        selected_bypass = st.selectbox("context_bypass", bypass_options)

    # ---- Section 4: Recent Requests Table ----
    st.markdown("### 最近请求（最多 20 条）")

    # Apply filters
    filtered = entries
    if selected_agent != "全部":
        filtered = [e for e in filtered if (e.get("_meta") or {}).get("agent_id") == selected_agent]
    if selected_type != "全部":
        filtered = [e for e in filtered if e.get("task_type") == selected_type]
    if selected_bypass != "全部":
        bypass_val = selected_bypass == "true"
        filtered = [e for e in filtered if e.get("context_bypass") == bypass_val]

    # Take last 20
    display_entries = filtered[-20:]

    if not display_entries:
        st.info("暂无日志记录，或筛选结果为空。")
        return

    # Build table rows
    rows = []
    for e in display_entries:
        meta = e.get("_meta") or {}
        ctx = e.get("context_stats") or {}
        rows.append({
            "timestamp": e.get("timestamp", "")[:19],
            "agent_id": meta.get("agent_id", ""),
            "task_type": e.get("task_type", ""),
            "bypass": "✅" if e.get("context_bypass") else "❌",
            "saved_tokens": ctx.get("saved_tokens_estimate", 0),
            "matched_keywords": ", ".join(meta.get("matched_keywords", []) or []),
            "request_id": meta.get("request_id", ""),
            "query": e.get("query", ""),
        })

    st.dataframe(
        rows,
        column_order=["timestamp", "agent_id", "task_type", "bypass", "saved_tokens", "matched_keywords", "request_id"],
        hide_index=True,
        width="stretch",
    )

    # ---- Section 5: Insight 诊断 ----
    st.divider()
    st.markdown("### Insight 诊断")

    analyze_fn, load_fn = _load_insight()
    if analyze_fn is None:
        st.warning("无法加载 usage_insight.py，诊断功能不可用。")
    else:
        try:
            insight_records, invalid_lines = load_fn(LOG_FILE)
            result = analyze_fn(insight_records, invalid_lines, min_sample=10)

            # Recommendations
            if result.recommendations:
                st.markdown("**建议：**")
                for rec in result.recommendations:
                    if "不要改 policy" in rec or "继续扩大样本" in rec:
                        st.success(f"✅ {rec}")
                    elif "红灯" in rec or "过低" in rec:
                        st.error(f"🚨 {rec}")
                    else:
                        st.warning(f"⚠️ {rec}")

            # Issues summary
            if result.issues:
                high_issues = [i for i in result.issues if i["severity"] == "high"]
                medium_issues = [i for i in result.issues if i["severity"] == "medium"]
                if high_issues:
                    st.markdown(f"**🚨 高优先级问题（{len(high_issues)} 条）：**")
                    for issue in high_issues[:10]:
                        st.markdown(
                            f"- `{issue['type']}` | line={issue['line_no']} | "
                            f"request_id={issue['request_id'][:12]}... | {issue['message']}"
                        )
                if medium_issues:
                    st.markdown(f"**⚠️ 中优先级问题（{len(medium_issues)} 条）：**")
                    for issue in medium_issues[:10]:
                        st.markdown(
                            f"- `{issue['type']}` | line={issue['line_no']} | "
                            f"request_id={issue['request_id'][:12]}... | {issue['message']}"
                        )
            elif not result.recommendations or all("继续扩大样本" in r for r in result.recommendations):
                st.info("暂无明显问题，建议继续累计样本后再诊断。")

            # Task type inject/bypass summary
            st.markdown("**按 task_type 注断：**")
            for task_type, summary in result.by_task_type.items():
                inj = summary["injected"]
                byp = summary["bypassed"]
                total = summary["total"]
                st.markdown(
                    f"- **{task_type}**：共 {total} 条 | "
                    f"注入 {inj} ({summary['inject_rate_pct']}%) | "
                    f"bypass {byp} ({summary['bypass_rate_pct']}%)"
                )

        except Exception as e:
            st.warning(f"诊断分析失败：{e}")

    # ---- Footer note ----
    st.caption(
        f"日志来源：{LOG_FILE}  |  服务健康检查：{HEALTH_URL}  |  "
        f"刷新：Streamlit 自动 · 或按 R"
    )


if __name__ == "__main__":
    main()
