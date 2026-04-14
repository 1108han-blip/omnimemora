"""
analyze_usage_logs.py - Wrapper Real Usage Log Analyzer
========================================================
读取 tools/usage_logs.jsonl，输出最小统计摘要。

用法：
    python analyze_usage_logs.py                        # 默认读取 tools/usage_logs.jsonl
    python analyze_usage_logs.py --path /path/to/log.jsonl
    python analyze_usage_logs.py --tail 50              # 只看最近 50 条
"""
import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path


def load_logs(path: str, tail: int = 0) -> list:
    """
    Load JSON Lines file.

    If tail > 0, only the last N lines are loaded.
    Skips malformed rows.
    """
    with open(path, encoding="utf-8") as f:
        if tail > 0:
            f.seek(0, 2)
            file_size = f.tell()
            # ~300 bytes per line estimate; overshoot slightly to avoid cut-off entries
            read_size = min(file_size, tail * 300 + 500)
            f.seek(max(0, file_size - read_size))
            lines = f.readlines()
            # Drop the possibly partial first line (overshoot boundary)
            lines = lines[-(tail + 1):] if len(lines) > tail else lines
            lines = lines[-tail:] if len(lines) >= tail else lines
        else:
            lines = f.readlines()

    rows = []
    for i, line in enumerate(lines, 1):
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            print(f"[analyze] WARNING: skipping line near end (malformed JSON)", file=sys.stderr)
    return rows


def mean(values: list) -> float:
    return sum(values) / len(values) if values else 0.0


def main():
    parser = argparse.ArgumentParser(description="Analyze OmniMemora Wrapper Real Usage Logs")
    parser.add_argument(
        "--path",
        default=None,
        help="Path to usage_logs.jsonl (default: tools/usage_logs.jsonl)",
    )
    parser.add_argument(
        "--tail",
        type=int,
        default=0,
        help="Only analyze the last N entries (default: 0 = all)",
    )
    args = parser.parse_args()

    log_path = args.path or str(Path(__file__).parent / "usage_logs.jsonl")

    try:
        logs = load_logs(log_path, tail=args.tail)
    except FileNotFoundError:
        print(f"[analyze] ERROR: file not found: {log_path}", file=sys.stderr)
        sys.exit(1)
    except OSError as e:
        print(f"[analyze] ERROR: could not read {log_path}: {e}", file=sys.stderr)
        sys.exit(1)

    total = len(logs)
    if total == 0:
        print("[analyze] No log entries found.")
        sys.exit(0)

    # ── 1. 按 agent_id 分组 ──────────────────────────────────
    by_agent: defaultdict = defaultdict(int)
    for row in logs:
        by_agent[row.get("_meta", {}).get("agent_id", "unknown")] += 1

    # ── 2. 按 task_type 分组 ─────────────────────────────────
    by_task: defaultdict = defaultdict(int)
    for row in logs:
        by_task[row.get("task_type", "unknown")] += 1

    # ── 3. context_bypass 统计 ───────────────────────────────
    bypass_count = sum(1 for row in logs if row.get("context_bypass") is True)
    bypass_ratio = bypass_count / total

    # ── 4. 整体平均 saved_tokens ──────────────────────────────
    saved_vals = [row.get("context_stats", {}).get("saved_tokens_estimate", 0) for row in logs]
    avg_saved = mean(saved_vals)

    # ── 5. 按 agent_id 分组平均 saved_tokens ─────────────────
    saved_by_agent: defaultdict = defaultdict(list)
    for row in logs:
        aid = row.get("_meta", {}).get("agent_id", "unknown")
        saved_by_agent[aid].append(row.get("context_stats", {}).get("saved_tokens_estimate", 0))

    # ── 6. 按 task_type 分组平均 saved_tokens ───────────────
    saved_by_task: defaultdict = defaultdict(list)
    for row in logs:
        tt = row.get("task_type", "unknown")
        saved_by_task[tt].append(row.get("context_stats", {}).get("saved_tokens_estimate", 0))

    # ── 打印摘要 ─────────────────────────────────────────────
    tail_note = f" (last {total} of file)" if args.tail > 0 else ""

    print()
    print("=" * 52)
    print(" OMNIMEMORA WRAPPER REAL USAGE LOG — STATS SUMMARY")
    print("=" * 52)
    print()
    print(f"  Log file : {log_path}{tail_note}")
    print(f"  Total    : {total} entries")
    print()

    print("  [1] By agent_id")
    for aid, cnt in sorted(by_agent.items(), key=lambda x: -x[1]):
        print(f"    {aid:<20} {cnt:>4} calls")
    print()

    print("  [2] By task_type")
    for tt, cnt in sorted(by_task.items(), key=lambda x: -x[1]):
        print(f"    {tt:<20} {cnt:>4} calls")
    print()

    print("  [3] Context Bypass")
    print(f"    bypass=true  : {bypass_count:>4} ({bypass_ratio:.1%})")
    print(f"    bypass=false : {total - bypass_count:>4} ({1-bypass_ratio:.1%})")
    print()

    print(f"  [4] Avg saved_tokens_estimate (overall) : {avg_saved:.1f}")
    print()

    print("  [5] Avg saved_tokens_estimate by agent_id")
    for aid, vals in sorted(saved_by_agent.items(), key=lambda x: -mean(x[1])):
        print(f"    {aid:<20} {mean(vals):>6.1f}  (n={len(vals)})")
    print()

    print("  [6] Avg saved_tokens_estimate by task_type")
    for tt, vals in sorted(saved_by_task.items(), key=lambda x: -mean(x[1])):
        print(f"    {tt:<20} {mean(vals):>6.1f}  (n={len(vals)})")
    print()
    print("=" * 52)


if __name__ == "__main__":
    main()
