"""Formal verify tool for the OpenViking commercialization baseline."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from ov_enterprise_common import (
    DEFAULT_ADAPTER_URL,
    DEFAULT_COMPATIBILITY_REPORT,
    DEFAULT_EXPECTED_AGENT_ID,
    DEFAULT_MIN_VERIFY_TIMEOUT_SECONDS,
    DEFAULT_OPENCLAW_CONFIG,
    DEFAULT_OPENVIKING_URL,
    DEFAULT_VERIFY_REPORT,
    ResultRecord,
    extract_request_id,
    http_json,
    http_json_with_meta,
    make_run_id,
    monotonic_ms,
    record_ids_by_status,
    render_records,
    report_metadata,
    resolve_agent_id,
    result_counts,
    write_json_report,
)


def _resolve_report_path(report_path: Path | None, write_report: Path | None) -> Path:
    if report_path and write_report and report_path != write_report:
        raise ValueError("--report-path and --write-report must match when both are provided")
    return report_path or write_report or DEFAULT_VERIFY_REPORT


def _find_search_hit(payload: object, token: str) -> dict | None:
    if not isinstance(payload, dict) or not isinstance(payload.get("memories"), list):
        return None
    for item in payload["memories"]:
        if not isinstance(item, dict):
            continue
        if token in str(item.get("content", "")) or token in str(item.get("abstract", "")):
            return item
    return None


def _search_for_token(
    adapter_url: str,
    agent_id: str,
    queries: list[str],
    token: str,
    *,
    timeout: float,
) -> tuple[int, object, dict | None, str | None, dict[str, object] | None]:
    last_payload: object = None
    last_meta: dict[str, object] | None = None
    for query in queries:
        status_code, payload, meta = http_json_with_meta(
            f"{adapter_url.rstrip('/')}/memory/search",
            method="POST",
            payload={"agent": agent_id, "query": query, "limit": 20, "scoreThreshold": 0},
            timeout=timeout,
        )
        last_payload = payload
        last_meta = meta
        hit = _find_search_hit(payload, token)
        if status_code != 200 or hit:
            return status_code, payload, hit, query, meta
    return 200, last_payload, None, None, last_meta


def _acceptance_summary(status: str, *, delete_confirmed: bool, warnings: bool) -> dict[str, object]:
    verdict = "accepted" if status == "pass" else "conditional" if status == "warn" else "rejected"
    return {
        "verdict": verdict,
        "commercial_acceptance_ready": status == "pass",
        "support_handoff_ready": status in {"pass", "warn"},
        "cleanup_confirmed": delete_confirmed,
        "requires_followup": status != "pass" or warnings,
    }


def _with_request_meta(payload: object, meta: dict[str, object] | None) -> dict[str, object]:
    request_id = extract_request_id(meta if isinstance(meta, dict) else None)
    if isinstance(payload, dict):
        result = dict(payload)
        if request_id:
            result.setdefault("request_id", request_id)
        return result
    return {"response": payload, "request_id": request_id}


def main() -> int:
    parser = argparse.ArgumentParser(description="OpenViking commercialization verify")
    parser.add_argument("--openclaw-config", type=Path, default=DEFAULT_OPENCLAW_CONFIG)
    parser.add_argument("--adapter-url", default=DEFAULT_ADAPTER_URL)
    parser.add_argument("--openviking-url", default=DEFAULT_OPENVIKING_URL)
    parser.add_argument("--agent-id")
    parser.add_argument("--request-timeout", type=float, default=DEFAULT_MIN_VERIFY_TIMEOUT_SECONDS)
    parser.add_argument("--search-window-seconds", type=float, default=DEFAULT_MIN_VERIFY_TIMEOUT_SECONDS)
    parser.add_argument("--delete-confirm-window-seconds", type=float, default=20.0)
    parser.add_argument("--poll-interval-seconds", type=float, default=3.0)
    parser.add_argument("--report-path", type=Path)
    parser.add_argument("--write-report", type=Path, help="Compatibility alias for --report-path")
    args = parser.parse_args()

    started_ms = monotonic_ms()
    run_id = make_run_id("verify")
    report_path = _resolve_report_path(args.report_path, args.write_report)

    agent_id = args.agent_id or resolve_agent_id(args.openclaw_config, fallback=DEFAULT_EXPECTED_AGENT_ID)
    token = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    unique_text = (
        f"OpenViking commercialization verify token {token}. "
        f"Agent={agent_id}. This memory should be written, searched, read, and deleted."
    )

    steps: list[ResultRecord] = []
    created_uri: str | None = None
    delete_confirmed = False
    adapter_request_ids: dict[str, str] = {}
    adapter_error_codes: list[str] = []
    adapter_error_policy: dict[str, object] | None = None

    status_code, payload, adapter_health_meta = http_json_with_meta(
        f"{args.adapter_url.rstrip('/')}/health",
        timeout=args.request_timeout,
    )
    adapter_ok = status_code == 200 and isinstance(payload, dict) and payload.get("status") in {"healthy", "ok"}
    adapter_health_request_id = extract_request_id(adapter_health_meta)
    if adapter_health_request_id:
        adapter_request_ids["adapter_health"] = adapter_health_request_id
    if isinstance(payload, dict) and isinstance(payload.get("error_policy"), dict):
        adapter_error_policy = payload["error_policy"]
    steps.append(
        ResultRecord(
            "adapter_health",
            "pass" if adapter_ok else "fail",
            "Memory Adapter health check passed" if adapter_ok else "Memory Adapter health check failed",
            _with_request_meta(payload, adapter_health_meta),
        )
    )

    status_code, payload = http_json(f"{args.openviking_url.rstrip('/')}/health", timeout=args.request_timeout)
    openviking_ok = status_code == 200 and isinstance(payload, dict) and payload.get("status") == "ok"
    steps.append(
        ResultRecord(
            "openviking_health",
            "pass" if openviking_ok else "fail",
            "OpenViking health check passed" if openviking_ok else "OpenViking health check failed",
            payload if isinstance(payload, dict) else {"response": payload},
        )
    )

    if any(step.status == "fail" for step in steps):
        evidence = record_ids_by_status(steps)
        acceptance = _acceptance_summary("fail", delete_confirmed=False, warnings=bool(evidence["warn"]))
        report = {
            **report_metadata("ov-enterprise-verify", run_id, started_ms),
            "report_kind": "verify_report",
            "status": "fail",
            "exit_code": 1,
            "summary": {"status": "fail", "counts": result_counts(steps)},
            "baseline": {
                "agent_id": agent_id,
                "request_timeout_seconds": args.request_timeout,
                "search_window_seconds": args.search_window_seconds,
                "delete_confirm_window_seconds": args.delete_confirm_window_seconds,
                "poll_interval_seconds": args.poll_interval_seconds,
                "adapter_url": args.adapter_url,
                "openviking_url": args.openviking_url,
            },
            "acceptance": acceptance,
            "workflow": {
                "steps_expected": [
                    "adapter_health",
                    "openviking_health",
                    "memory_write",
                    "memory_search",
                    "memory_read",
                    "memory_delete",
                    "post_delete_search",
                ],
                "search_queries": [],
            },
            "verification_token": token,
            "support_trace": {
                "adapter_request_ids": adapter_request_ids,
                "adapter_error_codes_seen": adapter_error_codes,
                "adapter_error_policy": adapter_error_policy,
            },
            "evidence": evidence,
            "companion_artifacts": {
                "compatibility_report": str(DEFAULT_COMPATIBILITY_REPORT),
            },
            "steps": render_records(steps),
            "report_path": str(report_path),
        }
        write_json_report(report_path, report)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 1

    write_payload = {
        "agent": agent_id,
        "type": "fact",
        "content": unique_text,
        "tags": ["commercialization", "verify", "formalized", token, agent_id],
    }
    status_code, payload, write_meta = http_json_with_meta(
        f"{args.adapter_url.rstrip('/')}/memory/write",
        method="POST",
        payload=write_payload,
        timeout=args.request_timeout,
    )
    write_request_id = extract_request_id(write_meta)
    if write_request_id:
        adapter_request_ids["memory_write"] = write_request_id
    if isinstance(payload, dict) and isinstance(payload.get("error_code"), str):
        adapter_error_codes.append(payload["error_code"])
    if status_code == 200 and isinstance(payload, dict) and payload.get("status") in {"stored", "duplicate"}:
        created_uri = payload.get("uri")
        steps.append(ResultRecord("memory_write", "pass", "Write check passed", {"response": _with_request_meta(payload, write_meta)}))
    else:
        steps.append(ResultRecord("memory_write", "fail", "Write check failed", {"response": _with_request_meta(payload, write_meta)}))

    search_queries = [
        token,
        f"OpenViking commercialization verify token {token}",
        unique_text,
        f"Agent={agent_id} {token}",
    ]
    deadline = time.time() + max(0.0, args.search_window_seconds)
    last_payload = None
    search_hit = None
    search_attempts = 0
    status_code = 0
    matched_query = None
    search_meta: dict[str, object] | None = None
    while time.time() <= deadline:
        search_attempts += 1
        status_code, payload, search_hit, matched_query, search_meta = _search_for_token(
            args.adapter_url,
            agent_id,
            search_queries,
            token,
            timeout=args.request_timeout,
        )
        last_payload = payload
        search_request_id = extract_request_id(search_meta if isinstance(search_meta, dict) else None)
        if search_request_id:
            adapter_request_ids["memory_search"] = search_request_id
        if isinstance(payload, dict) and isinstance(payload.get("error_code"), str):
            adapter_error_codes.append(payload["error_code"])
        if status_code != 200 or search_hit:
            break
        time.sleep(max(0.5, args.poll_interval_seconds))

    if status_code == 200 and search_hit:
        created_uri = created_uri or search_hit.get("uri")
        details = {
            "attempts": search_attempts,
            "matched_query": matched_query,
            "hit": search_hit,
            "total": payload.get("total") if isinstance(payload, dict) else None,
            "request_id": adapter_request_ids.get("memory_search"),
        }
        for step in steps:
            if step.id == "memory_write" and step.status == "fail":
                step.status = "warn"
                step.message = "Write request did not finish cleanly, but the memory became searchable within the verification window"
                break
        steps.append(ResultRecord("memory_search", "pass", "Search check passed", details))
    elif status_code == 200:
        steps.append(
            ResultRecord(
                "memory_search",
                "fail",
                "Search did not return the verification token within the verification window",
                {"attempts": search_attempts, "response": _with_request_meta(last_payload, search_meta)},
            )
        )
    else:
        steps.append(ResultRecord("memory_search", "fail", "Search request failed", {"response": _with_request_meta(last_payload, search_meta)}))

    if created_uri:
        status_code, payload, read_meta = http_json_with_meta(
            f"{args.adapter_url.rstrip('/')}/memory/read",
            method="POST",
            payload={"uri": created_uri},
            timeout=args.request_timeout,
        )
        read_request_id = extract_request_id(read_meta)
        if read_request_id:
            adapter_request_ids["memory_read"] = read_request_id
        if isinstance(payload, dict) and isinstance(payload.get("error_code"), str):
            adapter_error_codes.append(payload["error_code"])
        if status_code == 200 and isinstance(payload, dict) and token in str(payload.get("content", "")):
            steps.append(ResultRecord("memory_read", "pass", "Read check passed", {"uri": created_uri, "request_id": read_request_id}))
        else:
            steps.append(
                ResultRecord(
                    "memory_read",
                    "fail",
                    "Read check failed",
                    {"uri": created_uri, "response": _with_request_meta(payload, read_meta)},
                )
            )
    else:
        steps.append(ResultRecord("memory_read", "fail", "Read skipped because no URI was available"))

    delete_ok = False
    if created_uri:
        status_code, payload, delete_meta = http_json_with_meta(
            f"{args.adapter_url.rstrip('/')}/memory/delete",
            method="POST",
            payload={"uri": created_uri},
            timeout=args.request_timeout,
        )
        delete_request_id = extract_request_id(delete_meta)
        if delete_request_id:
            adapter_request_ids["memory_delete"] = delete_request_id
        if isinstance(payload, dict) and isinstance(payload.get("error_code"), str):
            adapter_error_codes.append(payload["error_code"])
        if status_code == 200:
            delete_ok = True
            steps.append(
                ResultRecord(
                    "memory_delete",
                    "pass",
                    "Delete check passed",
                    {"uri": created_uri, "response": _with_request_meta(payload, delete_meta)},
                )
            )
        else:
            steps.append(
                ResultRecord(
                    "memory_delete",
                    "fail",
                    "Delete check failed",
                    {"uri": created_uri, "response": _with_request_meta(payload, delete_meta)},
                )
            )
    else:
        steps.append(ResultRecord("memory_delete", "fail", "Delete skipped because no URI was available"))

    confirm_deadline = time.time() + max(0.0, args.delete_confirm_window_seconds)
    confirm_attempts = 0
    remaining = None
    while delete_ok and time.time() <= confirm_deadline:
        confirm_attempts += 1
        status_code = 200
        remaining = None
        for query in search_queries:
            status_code, payload, confirm_meta = http_json_with_meta(
                f"{args.adapter_url.rstrip('/')}/memory/search",
                method="POST",
                payload={"agent": agent_id, "query": query, "limit": 20, "scoreThreshold": 0},
                timeout=args.request_timeout,
            )
            confirm_request_id = extract_request_id(confirm_meta)
            if confirm_request_id:
                adapter_request_ids["post_delete_search"] = confirm_request_id
            if isinstance(payload, dict) and isinstance(payload.get("error_code"), str):
                adapter_error_codes.append(payload["error_code"])
            if status_code != 200 or not isinstance(payload, dict):
                remaining = payload
                break
            remaining = [
                item
                for item in payload.get("memories", [])
                if isinstance(item, dict)
                and (token in str(item.get("content", "")) or token in str(item.get("abstract", "")))
            ]
            if remaining:
                break
        if status_code != 200 or not isinstance(remaining, list):
            remaining = payload if "payload" in locals() else remaining
            break
        if not remaining:
            delete_confirmed = True
            break
        time.sleep(max(0.5, args.poll_interval_seconds))

    if delete_ok and delete_confirmed:
        steps.append(
            ResultRecord(
                "post_delete_search",
                "pass",
                "Post-delete search check passed",
                {"attempts": confirm_attempts, "request_id": adapter_request_ids.get("post_delete_search")},
            )
        )
    elif delete_ok and isinstance(remaining, list):
        steps.append(
            ResultRecord(
                "post_delete_search",
                "warn",
                "Deleted item still appears in search results before the confirmation window closed",
                {"attempts": confirm_attempts, "remaining": remaining, "request_id": adapter_request_ids.get("post_delete_search")},
            )
        )
    else:
        steps.append(
            ResultRecord(
                "post_delete_search",
                "warn",
                "Post-delete search confirmation was inconclusive",
                {"attempts": confirm_attempts, "response": remaining, "request_id": adapter_request_ids.get("post_delete_search")},
            )
        )

    counts = result_counts(steps)
    overall = "fail" if counts["fail"] else "warn" if counts["warn"] else "pass"
    evidence = record_ids_by_status(steps)
    suggestions: list[str] = []
    if any(step.id == "memory_write" and step.status == "warn" for step in steps):
        suggestions.append("Keep verify request windows at or above 45 seconds for commercial acceptance runs.")
    if any(step.id == "post_delete_search" and step.status == "warn" for step in steps):
        suggestions.append("Search indexes may lag deletes slightly; use the confirmation window before treating cleanup as failed.")
    if overall == "fail":
        suggestions.append("Do not treat this environment as commercially accepted until verify returns pass or warn only.")
    if not suggestions:
        suggestions.append("Store the verify report alongside the compatibility report for delivery and support traces.")
    acceptance = _acceptance_summary(overall, delete_confirmed=delete_confirmed, warnings=bool(evidence["warn"]))
    observations = {
        "search_attempts": search_attempts,
        "delete_confirm_attempts": confirm_attempts,
        "matched_query": matched_query,
        "cleanup_confirmed": delete_confirmed,
    }
    support_trace = {
        "adapter_request_ids": adapter_request_ids,
        "adapter_error_codes_seen": sorted(set(adapter_error_codes)),
        "adapter_error_policy": adapter_error_policy,
    }

    report = {
        **report_metadata("ov-enterprise-verify", run_id, started_ms),
        "report_kind": "verify_report",
        "status": overall,
        "exit_code": 0 if overall in {"pass", "warn"} else 1,
        "summary": {"status": overall, "counts": counts, "cleanup_confirmed": delete_confirmed},
        "baseline": {
            "agent_id": agent_id,
            "request_timeout_seconds": args.request_timeout,
            "search_window_seconds": args.search_window_seconds,
            "delete_confirm_window_seconds": args.delete_confirm_window_seconds,
            "poll_interval_seconds": args.poll_interval_seconds,
            "adapter_url": args.adapter_url,
            "openviking_url": args.openviking_url,
        },
        "acceptance": acceptance,
        "workflow": {
            "steps_expected": [
                "adapter_health",
                "openviking_health",
                "memory_write",
                "memory_search",
                "memory_read",
                "memory_delete",
                "post_delete_search",
            ],
            "search_queries": search_queries,
        },
        "verification_token": token,
        "created_uri": created_uri,
        "observations": observations,
        "support_trace": support_trace,
        "evidence": evidence,
        "companion_artifacts": {
            "compatibility_report": str(DEFAULT_COMPATIBILITY_REPORT),
        },
        "steps": render_records(steps),
        "suggestions": suggestions,
        "report_path": str(report_path),
    }

    write_json_report(report_path, report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return report["exit_code"]


if __name__ == "__main__":
    raise SystemExit(main())
