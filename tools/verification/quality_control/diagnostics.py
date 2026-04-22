#!/usr/bin/env python3
"""
QC Diagnostics CLI — V1 Local-First Quality Control Loop
========================================================
Read-only diagnostic report summarizing:
- Current active policy
- Latest golden gate results
- Recent wrapper feedback distribution
- Promotion readiness
"""
import json
import os
import sys
from datetime import datetime, timedelta
from typing import Optional

# Add paths
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "5_connectors"))
sys.path.insert(0, os.path.dirname(__file__))


def _get_reports_dir() -> str:
    return os.path.join(os.path.dirname(__file__), "reports")


def _get_usage_log_path() -> str:
    # diagnostics.py is at tools/verification/quality_control/diagnostics.py
    # usage_logs.jsonl is at tools/usage_logs.jsonl (sibling to verification/)
    return os.path.join(os.path.dirname(__file__), "..", "..", "usage_logs.jsonl")


def load_manifest() -> dict:
    """Load current policy manifest."""
    try:
        import adapter.policy_version_manager as pvm
        manifest = pvm.get_manifest()
        return {
            "active_version": manifest.active_version,
            "candidate_version": manifest.candidate_version,
            "last_verified_report": manifest.last_verified_report,
            "last_promoted_at": manifest.last_promoted_at,
        }
    except Exception as e:
        return {"error": str(e)}


def load_report_by_id(report_id: str) -> Optional[dict]:
    """Load a specific report by report_id."""
    reports_dir = _get_reports_dir()
    filepath = os.path.join(reports_dir, f"{report_id}.json")
    if os.path.exists(filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return None


def load_latest_report() -> Optional[dict]:
    """
    Load golden case comparison report.
    Priority: 1) manifest.last_verified_report, 2) most recent file.
    """
    manifest_data = load_manifest()

    # Try manifest's last_verified_report first
    last_verified = manifest_data.get("last_verified_report")
    if last_verified:
        report = load_report_by_id(last_verified)
        if report:
            return report

    # Fallback to most recent file
    reports_dir = _get_reports_dir()
    if not os.path.exists(reports_dir):
        return None

    reports = []
    for filename in os.listdir(reports_dir):
        if filename.endswith(".json") and filename.startswith("cmp-"):
            filepath = os.path.join(reports_dir, filename)
            try:
                mtime = os.path.getmtime(filepath)
                reports.append((mtime, filepath))
            except Exception:
                pass

    if not reports:
        return None

    # Get most recent
    reports.sort(key=lambda x: x[0], reverse=True)
    _, latest_path = reports[0]

    with open(latest_path, "r", encoding="utf-8") as f:
        return json.load(f)


def analyze_wrapper_feedback(since_days: int = 7) -> dict:
    """
    Analyze wrapper feedback from usage_logs.jsonl.
    Returns distribution of execution_feedback and subjective_score.
    """
    log_path = _get_usage_log_path()
    if not os.path.exists(log_path):
        return {"error": "usage_logs.jsonl not found"}

    cutoff = datetime.utcnow() - timedelta(days=since_days)
    feedback_counts = {
        "better": 0, "same": 0, "worse": 0, "failed": 0, "unknown": 0, "null": 0
    }
    score_values = []
    version_counts = {}

    try:
        with open(log_path, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    entry = json.loads(line.strip())
                    timestamp = entry.get("timestamp", "")
                    if timestamp:
                        try:
                            dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                            if dt.replace(tzinfo=None) < cutoff:
                                continue
                        except Exception:
                            pass

                    # Count feedback
                    fb = entry.get("execution_feedback")
                    if fb is None:
                        feedback_counts["null"] += 1
                    elif fb in feedback_counts:
                        feedback_counts[fb] += 1
                    else:
                        feedback_counts["unknown"] += 1

                    # Collect scores
                    score = entry.get("subjective_score")
                    if score is not None:
                        score_values.append(score)

                    # Count by policy version
                    pv = entry.get("policy_version")
                    if pv:
                        version_counts[pv] = version_counts.get(pv, 0) + 1
                    else:
                        version_counts["(no version)"] = version_counts.get("(no version)", 0) + 1

                except Exception:
                    pass
    except Exception as e:
        return {"error": str(e)}

    # Calculate score statistics
    score_stats = {}
    if score_values:
        score_stats = {
            "count": len(score_values),
            "avg": round(sum(score_values) / len(score_values), 2),
            "min": min(score_values),
            "max": max(score_values),
        }
    else:
        score_stats = {"count": 0}

    return {
        "feedback_distribution": feedback_counts,
        "score_stats": score_stats,
        "policy_version_distribution": version_counts,
        "period_days": since_days,
    }


def check_promotion_readiness() -> dict:
    """
    Check if the system is ready for promotion.
    V1: Promotion readiness requires:
    1. candidate_version exists
    2. last_verified_report exists
    3. The report's evaluated_candidate_version matches current candidate
    4. The report shows promotion_allowed=true
    """
    manifest_data = load_manifest()
    latest_report = load_latest_report()

    status = {
        "has_candidate": manifest_data.get("candidate_version") is not None,
        "candidate_version": manifest_data.get("candidate_version"),
        "has_verification_report": manifest_data.get("last_verified_report") is not None,
        "last_verified_report": manifest_data.get("last_verified_report"),
        "report_candidate_matches": False,
        "promotion_allowed_by_report": False,
        "promotion_ready": False,
        "blockers": [],
    }

    # Gate 1: Candidate must exist
    if not status["has_candidate"]:
        status["blockers"].append("No candidate version set")

    # Gate 2: Verification report must exist
    if status["has_candidate"] and not status["has_verification_report"]:
        status["blockers"].append("No verification report recorded")

    # Gate 3: Report must correspond to current candidate
    if latest_report:
        report_candidate = latest_report.get("evaluated_candidate_version")
        if report_candidate == status["candidate_version"]:
            status["report_candidate_matches"] = True
        else:
            status["blockers"].append(
                f"Report candidate '{report_candidate}' != current candidate '{status['candidate_version']}'"
            )

    # Gate 4: Report must allow promotion
    if latest_report and latest_report.get("promotion_allowed", False):
        status["promotion_allowed_by_report"] = True
    elif latest_report:
        status["blockers"].append(
            f"Report blocks promotion: {latest_report.get('blocked_reason')}"
        )

    # All gates passed
    if not status["blockers"]:
        status["promotion_ready"] = True

    return status


def generate_diagnostics_report() -> dict:
    """Generate a complete diagnostics report."""
    report = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "section_manifest": load_manifest(),
        "section_latest_report": load_latest_report(),
        "section_wrapper_feedback": analyze_wrapper_feedback(),
        "section_promotion_readiness": check_promotion_readiness(),
    }
    return report


def print_diagnostics():
    """Print human-readable diagnostics to stdout."""
    report = generate_diagnostics_report()

    print("=" * 60)
    print("QC DIAGNOSTICS REPORT — V1 Local-First Quality Control Loop")
    print("=" * 60)
    print(f"Generated at: {report['generated_at']}")

    # Manifest section
    print("\n## Policy Manifest")
    manifest = report["section_manifest"]
    if "error" in manifest:
        print(f"  Error loading manifest: {manifest['error']}")
    else:
        print(f"  Active version: {manifest.get('active_version', 'N/A')}")
        print(f"  Candidate version: {manifest.get('candidate_version', 'N/A')}")
        print(f"  Last verified report: {manifest.get('last_verified_report', 'N/A')}")
        print(f"  Last promoted at: {manifest.get('last_promoted_at', 'N/A')}")

    # Latest report section
    print("\n## Latest Golden Case Report")
    latest = report["section_latest_report"]
    if latest is None:
        print("  No golden case reports found")
    else:
        active = latest.get("active_report", {})
        print(f"  Report ID: {latest.get('report_id', 'N/A')}")
        print(f"  Evaluated active: {latest.get('evaluated_active_version', 'N/A')}")
        print(f"  Evaluated candidate: {latest.get('evaluated_candidate_version', 'N/A')}")
        print(f"  Must pass: {active.get('must_pass_passed', 0)}/{active.get('must_pass_cases', 0)}")
        print(f"  Scored: {active.get('scored_passed', 0)}/{active.get('scored_cases', 0)}")
        print(f"  Total score: {active.get('total_score', 0)}")
        print(f"  Promotion allowed: {latest.get('promotion_allowed', False)}")
        if latest.get("blocked_reason"):
            print(f"  Blocked reason: {latest.get('blocked_reason')}")

        if latest.get("candidate_report"):
            cand = latest["candidate_report"]
            print(f"\n  Candidate must_pass: {cand.get('must_pass_passed', 0)}/{cand.get('must_pass_cases', 0)}")
            print(f"  Candidate scored: {cand.get('scored_passed', 0)}/{cand.get('scored_cases', 0)}")
            print(f"  Candidate total_score: {cand.get('total_score', 0)}")

    # Wrapper feedback section
    print("\n## Wrapper Feedback (Last 7 Days)")
    fb = report["section_wrapper_feedback"]
    if "error" in fb:
        print(f"  Error: {fb['error']}")
    else:
        dist = fb.get("feedback_distribution", {})
        total = sum(dist.values())
        print(f"  Total entries: {total}")
        print(f"  Feedback distribution:")
        for k, v in dist.items():
            pct = (v / total * 100) if total > 0 else 0
            print(f"    {k}: {v} ({pct:.1f}%)")

        score_stats = fb.get("score_stats", {})
        if score_stats.get("count", 0) > 0:
            print(f"  Subjective score stats:")
            print(f"    Count: {score_stats.get('count')}")
            print(f"    Avg: {score_stats.get('avg')}")
            print(f"    Min/Max: {score_stats.get('min')}/{score_stats.get('max')}")

        version_dist = fb.get("policy_version_distribution", {})
        if version_dist:
            print(f"  Policy version distribution:")
            for v, c in version_dist.items():
                print(f"    {v}: {c}")

    # Promotion readiness section
    print("\n## Promotion Readiness")
    pr = report["section_promotion_readiness"]
    print(f"  Promotion ready: {pr.get('promotion_ready', False)}")
    print(f"  Candidate: {pr.get('candidate_version', 'N/A')}")
    print(f"  Has verification report: {pr.get('has_verification_report', False)}")
    print(f"  Report matches candidate: {pr.get('report_candidate_matches', False)}")
    print(f"  Report allows promotion: {pr.get('promotion_allowed_by_report', False)}")
    if pr.get("blockers"):
        print("  Blockers:")
        for b in pr["blockers"]:
            print(f"    - {b}")

    print("\n" + "=" * 60)


if __name__ == "__main__":
    # Check for JSON output flag
    if len(sys.argv) > 1 and sys.argv[1] == "--json":
        report = generate_diagnostics_report()
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print_diagnostics()
