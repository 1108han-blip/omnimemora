#!/usr/bin/env python3
"""OmniMemora usage insight analyzer.

Reads usage_logs.jsonl and turns raw request logs into decision-ready signals.

Focus:
- policy stability
- injection quality
- token savings
- suspicious routing / bypass patterns

This script is intentionally standalone so it can run in a Windows local environment
without external dependencies.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import statistics
from collections import Counter, defaultdict
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, Iterable, List, Optional, Tuple


KNOWN_TASK_TYPES = ("implementation", "decision", "continuation")


@dataclass
class LogRecord:
    line_no: int
    raw: Dict[str, Any]
    request_id: str
    agent_id: str
    task_type: str
    context_bypass: Optional[bool]
    matched_keywords: List[str]
    injected: bool
    raw_tokens: Optional[int]
    optimized_tokens: Optional[int]
    saved_tokens: Optional[int]
    selected_count: Optional[int]
    relevance_score: Optional[float]
    duration_ms: Optional[float]


@dataclass
class TaskMetrics:
    total: int = 0
    injected: int = 0
    bypassed: int = 0
    missing_bypass_flag: int = 0
    empty_keyword_injections: int = 0
    suspicious_injections: int = 0
    suspicious_bypasses: int = 0
    with_token_data: int = 0
    total_raw_tokens: int = 0
    total_optimized_tokens: int = 0
    total_saved_tokens: int = 0
    selected_counts: List[int] = field(default_factory=list)
    relevance_scores: List[float] = field(default_factory=list)
    durations_ms: List[float] = field(default_factory=list)


@dataclass
class InsightResult:
    total_records: int
    valid_records: int
    invalid_lines: int
    duplicate_request_ids: int
    by_task_type: Dict[str, Dict[str, Any]]
    by_agent: Dict[str, Dict[str, Any]]
    overall: Dict[str, Any]
    issues: List[Dict[str, Any]]
    recommendations: List[str]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyze OmniMemora usage logs")
    parser.add_argument(
        "--input",
        default=os.path.join("tools", "usage_logs.jsonl"),
        help="Path to usage_logs.jsonl",
    )
    parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="Output format",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Only read first N records (0 = all)",
    )
    parser.add_argument(
        "--min-sample",
        type=int,
        default=30,
        help="Minimum sample size before policy recommendations become strong",
    )
    return parser.parse_args()


def safe_int(value: Any) -> Optional[int]:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def safe_float(value: Any) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def first_non_null(record: Dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in record and record[key] is not None:
            return record[key]
    return None


def derive_selected_count(record: Dict[str, Any]) -> Optional[int]:
    direct = safe_int(first_non_null(record, "selected_count", "selected_memories_count", "selected_items_count"))
    if direct is not None:
        return direct

    for key in ("selected_memories", "selected_items", "optimized_context_items", "final_context_items"):
        value = record.get(key)
        if isinstance(value, list):
            return len(value)

    optimization = record.get("optimization")
    if isinstance(optimization, dict):
        for key in ("selected_count", "selected_memories_count"):
            direct = safe_int(optimization.get(key))
            if direct is not None:
                return direct
    return None


def derive_token_metrics(record: Dict[str, Any]) -> Tuple[Optional[int], Optional[int], Optional[int]]:
    raw_tokens = safe_int(
        first_non_null(
            record,
            "raw_tokens",
            "input_tokens_before",
            "tokens_before",
            "candidate_tokens",
        )
    )
    optimized_tokens = safe_int(
        first_non_null(
            record,
            "optimized_tokens",
            "compressed_tokens",
            "input_tokens_after",
            "tokens_after",
            "final_tokens",
        )
    )
    saved_tokens = safe_int(
        first_non_null(
            record,
            "saved_tokens",
            "token_savings",
            "tokens_saved",
        )
    )

    if saved_tokens is None and raw_tokens is not None and optimized_tokens is not None:
        saved_tokens = raw_tokens - optimized_tokens
    if optimized_tokens is None and raw_tokens is not None and saved_tokens is not None:
        optimized_tokens = raw_tokens - saved_tokens
    if raw_tokens is None and optimized_tokens is not None and saved_tokens is not None:
        raw_tokens = optimized_tokens + saved_tokens

    return raw_tokens, optimized_tokens, saved_tokens


def parse_record(obj: Dict[str, Any], line_no: int) -> LogRecord:
    # request_id / agent_id may live at top level or inside _meta (wrapper log format)
    meta = obj.get("_meta") or {}
    request_id = str(
        first_non_null(obj, "request_id", "id", "trace_id")
        or first_non_null(meta, "request_id")
        or f"line-{line_no}"
    )
    agent_id = str(
        first_non_null(obj, "agent_id", "agent", "source_agent")
        or first_non_null(meta, "agent_id")
        or "unknown"
    )
    task_type = str(first_non_null(obj, "task_type", "task", "intent") or "unknown")
    context_bypass = obj.get("context_bypass")
    if context_bypass is not None:
        context_bypass = bool(context_bypass)

    # matched_keywords lives at top level OR inside _meta (wrapper real usage log format)
    matched_keywords = obj.get("matched_keywords")
    if not isinstance(matched_keywords, list):
        matched_keywords = (obj.get("_meta") or {}).get("matched_keywords", [])
    if not isinstance(matched_keywords, list):
        matched_keywords = []

    raw_tokens, optimized_tokens, saved_tokens = derive_token_metrics(obj)
    selected_count = derive_selected_count(obj)
    relevance_score = safe_float(first_non_null(obj, "relevance_score", "avg_relevance", "context_score"))
    duration_ms = safe_float(first_non_null(obj, "duration_ms", "latency_ms", "elapsed_ms"))

    injected = context_bypass is False

    return LogRecord(
        line_no=line_no,
        raw=obj,
        request_id=request_id,
        agent_id=agent_id,
        task_type=task_type,
        context_bypass=context_bypass,
        matched_keywords=matched_keywords,
        injected=injected,
        raw_tokens=raw_tokens,
        optimized_tokens=optimized_tokens,
        saved_tokens=saved_tokens,
        selected_count=selected_count,
        relevance_score=relevance_score,
        duration_ms=duration_ms,
    )


def load_records(path: str, limit: int = 0) -> Tuple[List[LogRecord], int]:
    records: List[LogRecord] = []
    invalid_lines = 0
    with open(path, "r", encoding="utf-8") as f:
        for idx, line in enumerate(f, start=1):
            if limit and len(records) >= limit:
                break
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                if not isinstance(obj, dict):
                    raise ValueError("Log line is not a JSON object")
                records.append(parse_record(obj, idx))
            except Exception:
                invalid_lines += 1
    return records, invalid_lines


def pct(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round((numerator / denominator) * 100, 1)


def summarize_task_metrics(metrics: TaskMetrics) -> Dict[str, Any]:
    avg_selected = round(statistics.mean(metrics.selected_counts), 2) if metrics.selected_counts else None
    avg_relevance = round(statistics.mean(metrics.relevance_scores), 3) if metrics.relevance_scores else None
    p50_duration = round(statistics.median(metrics.durations_ms), 1) if metrics.durations_ms else None
    avg_duration = round(statistics.mean(metrics.durations_ms), 1) if metrics.durations_ms else None

    savings_rate = None
    if metrics.with_token_data and metrics.total_raw_tokens > 0:
        savings_rate = round(metrics.total_saved_tokens / metrics.total_raw_tokens * 100, 1)

    return {
        "total": metrics.total,
        "injected": metrics.injected,
        "bypassed": metrics.bypassed,
        "inject_rate_pct": pct(metrics.injected, metrics.total),
        "bypass_rate_pct": pct(metrics.bypassed, metrics.total),
        "missing_bypass_flag": metrics.missing_bypass_flag,
        "empty_keyword_injections": metrics.empty_keyword_injections,
        "empty_keyword_injection_rate_pct": pct(metrics.empty_keyword_injections, metrics.injected),
        "suspicious_injections": metrics.suspicious_injections,
        "suspicious_bypasses": metrics.suspicious_bypasses,
        "with_token_data": metrics.with_token_data,
        "raw_tokens": metrics.total_raw_tokens,
        "optimized_tokens": metrics.total_optimized_tokens,
        "saved_tokens": metrics.total_saved_tokens,
        "savings_rate_pct": savings_rate,
        "avg_selected_count": avg_selected,
        "avg_relevance_score": avg_relevance,
        "avg_duration_ms": avg_duration,
        "p50_duration_ms": p50_duration,
    }


def analyze(records: List[LogRecord], invalid_lines: int, min_sample: int) -> InsightResult:
    request_ids = Counter(r.request_id for r in records)
    duplicate_request_ids = sum(1 for _, count in request_ids.items() if count > 1)

    task_buckets: Dict[str, TaskMetrics] = defaultdict(TaskMetrics)
    agent_buckets: Dict[str, TaskMetrics] = defaultdict(TaskMetrics)
    overall = TaskMetrics()
    issues: List[Dict[str, Any]] = []

    def apply(record: LogRecord, metrics: TaskMetrics) -> None:
        metrics.total += 1

        if record.context_bypass is True:
            metrics.bypassed += 1
        elif record.context_bypass is False:
            metrics.injected += 1
        else:
            metrics.missing_bypass_flag += 1

        if record.injected and not record.matched_keywords:
            metrics.empty_keyword_injections += 1

        if record.injected and (not record.matched_keywords or (record.selected_count is not None and record.selected_count <= 0)):
            metrics.suspicious_injections += 1

        if record.context_bypass is True and record.task_type in ("decision", "continuation"):
            metrics.suspicious_bypasses += 1

        if record.raw_tokens is not None and record.optimized_tokens is not None and record.saved_tokens is not None:
            metrics.with_token_data += 1
            metrics.total_raw_tokens += max(record.raw_tokens, 0)
            metrics.total_optimized_tokens += max(record.optimized_tokens, 0)
            metrics.total_saved_tokens += max(record.saved_tokens, 0)

        if record.selected_count is not None:
            metrics.selected_counts.append(record.selected_count)
        if record.relevance_score is not None:
            metrics.relevance_scores.append(record.relevance_score)
        if record.duration_ms is not None:
            metrics.durations_ms.append(record.duration_ms)

    for record in records:
        apply(record, overall)
        apply(record, task_buckets[record.task_type])
        apply(record, agent_buckets[record.agent_id])

        if record.task_type == "implementation" and record.injected:
            issues.append(
                {
                    "severity": "medium",
                    "type": "implementation_injected",
                    "request_id": record.request_id,
                    "line_no": record.line_no,
                    "message": "Implementation request was injected instead of bypassed.",
                }
            )

        if record.task_type in ("decision", "continuation") and record.context_bypass is True:
            issues.append(
                {
                    "severity": "high",
                    "type": "decision_or_continuation_bypassed",
                    "request_id": record.request_id,
                    "line_no": record.line_no,
                    "message": f"{record.task_type} request was bypassed.",
                }
            )

        if record.injected and not record.matched_keywords:
            issues.append(
                {
                    "severity": "medium",
                    "type": "empty_keyword_injection",
                    "request_id": record.request_id,
                    "line_no": record.line_no,
                    "message": "Context injected, but matched_keywords is empty.",
                }
            )

        if record.saved_tokens is not None and record.saved_tokens < 0:
            issues.append(
                {
                    "severity": "high",
                    "type": "negative_token_savings",
                    "request_id": record.request_id,
                    "line_no": record.line_no,
                    "message": f"Negative token savings: {record.saved_tokens}.",
                }
            )

    by_task_type = {name: summarize_task_metrics(metrics) for name, metrics in sorted(task_buckets.items())}
    by_agent = {name: summarize_task_metrics(metrics) for name, metrics in sorted(agent_buckets.items())}
    overall_summary = summarize_task_metrics(overall)

    recommendations: List[str] = []

    if overall.total < min_sample:
        recommendations.append(
            f"样本量只有 {overall.total}，先继续跑真实 usage，至少累计到 {min_sample}+ 再动 policy。"
        )

    impl = task_buckets.get("implementation")
    if impl and impl.total:
        injected_rate = impl.injected / impl.total
        if injected_rate > 0.05:
            recommendations.append(
                f"implementation 被注入比例为 {injected_rate * 100:.1f}% ，高于 5% 阈值，先检查分类器关键词或 wrapper 映射。"
            )

    for t in ("decision", "continuation"):
        bucket = task_buckets.get(t)
        if bucket and bucket.total:
            bypass_rate = bucket.bypassed / bucket.total
            if bypass_rate > 0.05:
                recommendations.append(
                    f"{t} 被 bypass 比例为 {bypass_rate * 100:.1f}% ，这通常代表错判，优先排查 task_type 分类和 policy 命中条件。"
                )
            empty_kw_rate = (bucket.empty_keyword_injections / bucket.injected) if bucket.injected else 0.0
            if empty_kw_rate > 0.2:
                recommendations.append(
                    f"{t} 的空关键词注入比例为 {empty_kw_rate * 100:.1f}% ，注入质量偏低，先补 matched_keywords 或候选召回诊断。"
                )

    if overall.with_token_data == 0:
        recommendations.append("日志里没有稳定的 token 字段，先补 raw_tokens / optimized_tokens / saved_tokens，否则无法证明核心价值。")
    elif overall.total_raw_tokens > 0:
        savings_rate = overall.total_saved_tokens / overall.total_raw_tokens
        if savings_rate < 0.1:
            recommendations.append(
                f"整体 token savings 只有 {savings_rate * 100:.1f}% ，过低，先检查压缩是否真的生效。"
            )
        elif savings_rate >= 0.3:
            recommendations.append(
                f"整体 token savings 为 {savings_rate * 100:.1f}% ，说明优化方向成立，下一步重点看错判与无效注入。"
            )

    if duplicate_request_ids > 0:
        recommendations.append(f"发现 {duplicate_request_ids} 个重复 request_id，先确认日志是否重复写入。")

    if not recommendations:
        recommendations.append("当前没有明显红灯，继续扩大样本，暂时不要改 policy。")

    return InsightResult(
        total_records=overall.total + invalid_lines,
        valid_records=overall.total,
        invalid_lines=invalid_lines,
        duplicate_request_ids=duplicate_request_ids,
        by_task_type=by_task_type,
        by_agent=by_agent,
        overall=overall_summary,
        issues=issues[:100],
        recommendations=recommendations,
    )


def render_text(result: InsightResult) -> str:
    lines: List[str] = []
    lines.append("# OmniMemora Usage Insight")
    lines.append("")
    lines.append("## Overall")
    lines.append(f"- valid records: {result.valid_records}")
    lines.append(f"- invalid lines: {result.invalid_lines}")
    lines.append(f"- duplicate request_ids: {result.duplicate_request_ids}")
    lines.append(f"- inject rate: {result.overall['inject_rate_pct']}%")
    lines.append(f"- bypass rate: {result.overall['bypass_rate_pct']}%")
    if result.overall.get("savings_rate_pct") is not None:
        lines.append(
            f"- token savings: {result.overall['saved_tokens']} / {result.overall['raw_tokens']} ({result.overall['savings_rate_pct']}%)"
        )
    else:
        lines.append("- token savings: unavailable")

    lines.append("")
    lines.append("## By task_type")
    for task_type, summary in result.by_task_type.items():
        lines.append(f"### {task_type}")
        lines.append(f"- total: {summary['total']}")
        lines.append(f"- injected: {summary['injected']} ({summary['inject_rate_pct']}%)")
        lines.append(f"- bypassed: {summary['bypassed']} ({summary['bypass_rate_pct']}%)")
        lines.append(f"- empty keyword injections: {summary['empty_keyword_injections']} ({summary['empty_keyword_injection_rate_pct']}%)")
        if summary.get("savings_rate_pct") is not None:
            lines.append(
                f"- token savings: {summary['saved_tokens']} / {summary['raw_tokens']} ({summary['savings_rate_pct']}%)"
            )
        if summary.get("avg_selected_count") is not None:
            lines.append(f"- avg selected count: {summary['avg_selected_count']}")
        if summary.get("avg_duration_ms") is not None:
            lines.append(f"- avg latency: {summary['avg_duration_ms']} ms")
        lines.append("")

    lines.append("## Recommendations")
    for rec in result.recommendations:
        lines.append(f"- {rec}")

    if result.issues:
        lines.append("")
        lines.append("## Top issues")
        for issue in result.issues[:20]:
            lines.append(
                f"- [{issue['severity']}] {issue['type']} | request_id={issue['request_id']} | line={issue['line_no']} | {issue['message']}"
            )

    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    if not os.path.exists(args.input):
        raise SystemExit(f"Input file not found: {args.input}")

    records, invalid_lines = load_records(args.input, limit=args.limit)
    result = analyze(records, invalid_lines, min_sample=args.min_sample)

    if args.format == "json":
        print(json.dumps(asdict(result), ensure_ascii=False, indent=2))
    else:
        print(render_text(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
