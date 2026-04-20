#!/usr/bin/env python3
"""
Operational Drift Check for Phase 6
====================================
Compares four surfaces: active docs, latest promotion evidence, live running reality,
and deployed revision state.

Exit codes:
    0 = no audit-triggering drift
    1 = audit-triggering drift present
    2 = checker error
"""

import argparse
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional

# Configuration
PROJECT_ROOT = Path(__file__).parent.parent.parent
SERVICE_DIR = Path(os.environ.get("OMNIMEMORA_SERVICE_DIR", str(Path.home() / ".omnimemora/service")))
CURRENT_SERVICE_DIR = SERVICE_DIR / "current"
DRIFT_REGISTER_PATH = PROJECT_ROOT / "docs/phase6/OPERATIONAL_DRIFT_REGISTER.md"
PROMOTION_LOG_DIR = PROJECT_ROOT / "tools/verification/logs"
PHASE6_PLAN_DIR = PROJECT_ROOT / "7_docs/internal/phase6/plan"

RUNTIME_PORT = 8765
ADAPTER_PORT = 18011
UI_PORT = 5173


@dataclass
class DriftSignal:
    signal_id: str
    timestamp: str
    observation: str
    reality_layer: str
    evidence_level: str
    severity: str
    audit_trigger: bool
    source_pointers: list
    recommended_next_action: str
    status: str = "open"


# Paths whose changes genuinely affect the running reality on disk/services.
# Changes to these paths, when marker and repo diverge, mean a real sync gap.
RUNNING_REALITY_RELEVANT_PATHS = [
    "4_core/",
    "5_connectors/",
    "6_console/",
    "start.sh",
    ".omnimemora/",
    "com.omnimemora.",
]

# Paths that are repo-internal only and do NOT affect what's currently
# running on this machine, even when marker and repo disagree.
# Suppress DRA-001 for diffs that touch only these paths.
NON_RUNNING_REALITY_PATHS = [
    "7_docs/",
    "docs/",
    "tools/verification/",
    "README.md",
    ".git/",
    "node_modules/",
]

def _paths_touch_running_reality(paths: list[str]) -> bool:
    """Return True if any path is running-reality-relevant.

    Rules:
    - If the full diff (all files) touches only NON_RUNNING_REALITY_PATHS → False
      (suppress DRA-001; the marker lag is docs/tooling only)
    - If the diff touches any RUNNING_REALITY_RELEVANT_PATHS → True
      (keep DRA-001; there is a genuine sync gap)
    """
    for path in paths:
        for prefix in RUNNING_REALITY_RELEVANT_PATHS:
            if prefix in path:
                return True
    # No running-reality-relevant path found — suppress DRA-001
    return False


class OperationalDriftChecker:
    def __init__(self, write_register: bool = False):
        self.write_register = write_register
        self.signals: list[DriftSignal] = []
        self.has_audit_trigger = False
        self.errors: list[str] = []

    def run_command(self, cmd: list[str], timeout: int = 5) -> tuple[int, str, str]:
        """Run a command and return (returncode, stdout, stderr)."""
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=PROJECT_ROOT
            )
            return result.returncode, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            return -1, "", "timeout"
        except Exception as e:
            return -1, "", str(e)

    def check_curl(self, port: int, path: str = "/health", timeout: int = 3) -> bool:
        """Check if an HTTP endpoint is reachable."""
        cmd = ["curl", "-sf", "--connect-timeout", str(timeout),
               f"http://127.0.0.1:{port}{path}"]
        rc, _, _ = self.run_command(cmd, timeout=timeout + 1)
        return rc == 0

    def check_process(self, pattern: str) -> bool:
        """Check if a process matching pattern is running."""
        rc, stdout, _ = self.run_command(["pgrep", "-f", pattern])
        return rc == 0 and stdout.strip()

    def check_launchd(self, service_name: str) -> bool:
        """Check if a launchd service exists."""
        uid = str(os.getuid())
        rc, _, _ = self.run_command(
            ["launchctl", "print", f"gui/{uid}/{service_name}"],
            timeout=3
        )
        return rc == 0

    # === Signal Family 1: running_reality_status ===

    def check_running_reality_status(self) -> None:
        """Check runtime, adapter, UI health and compare against phase6 declarations."""
        signals = []

        # Runtime health (8765)
        runtime_healthy = self.check_curl(RUNTIME_PORT)
        runtime_declared = self._read_phase6_declaration("runtime")
        if runtime_declared and not runtime_healthy:
            signals.append(DriftSignal(
                signal_id="RRS-001",
                timestamp=datetime.now().isoformat(),
                observation=f"Runtime health check failed on port {RUNTIME_PORT}",
                reality_layer="running reality",
                evidence_level="A",
                severity="P1",
                audit_trigger=True,
                source_pointers=[f"http://127.0.0.1:{RUNTIME_PORT}/health"],
                recommended_next_action="Verify runtime is running and promoted correctly"
            ))
        elif runtime_healthy and not runtime_declared:
            signals.append(DriftSignal(
                signal_id="RRS-002",
                timestamp=datetime.now().isoformat(),
                observation=f"Runtime is healthy but not declared in phase6 docs",
                reality_layer="running reality",
                evidence_level="A",
                severity="P3",
                audit_trigger=False,
                source_pointers=[f"http://127.0.0.1:{RUNTIME_PORT}/health"],
                recommended_next_action="Update phase6 docs if runtime should be declared"
            ))

        # Adapter health (18011)
        adapter_healthy = self.check_curl(ADAPTER_PORT)
        adapter_declared = self._read_phase6_declaration("adapter")
        if adapter_declared and not adapter_healthy:
            signals.append(DriftSignal(
                signal_id="RRS-003",
                timestamp=datetime.now().isoformat(),
                observation=f"Adapter health check failed on port {ADAPTER_PORT}",
                reality_layer="running reality",
                evidence_level="A",
                severity="P1",
                audit_trigger=True,
                source_pointers=[f"http://127.0.0.1:{ADAPTER_PORT}/health"],
                recommended_next_action="Verify adapter is running and promoted correctly"
            ))

        # Adapter plist reality (warning only, per adoption contract)
        adapter_plist = self.check_launchd("com.omnimemora.adapter")
        if adapter_healthy and not adapter_plist:
            # This is the known non-blocking warning from adoption contract
            pass  # Skip - it's contractized

        # UI health (5173)
        ui_healthy = self.check_curl(UI_PORT, path="/", timeout=5)
        if ui_healthy:
            ui_agents = self.check_curl(UI_PORT, path="/agents?tenant=all", timeout=5)
            if not ui_agents:
                signals.append(DriftSignal(
                    signal_id="RRS-004",
                    timestamp=datetime.now().isoformat(),
                    observation=f"UI root accessible but /agents?tenant=all failed on port {UI_PORT}",
                    reality_layer="running reality",
                    evidence_level="A",
                    severity="P2",
                    audit_trigger=False,
                    source_pointers=[f"http://127.0.0.1:{UI_PORT}/", f"http://127.0.0.1:{UI_PORT}/agents?tenant=all"],
                    recommended_next_action="Investigate UI routing or adapter alignment"
                ))

        self.signals.extend(signals)

    def _read_phase6_declaration(self, component: str) -> bool:
        """Check if component is declared as running in phase6 docs."""
        # Look for explicit declarations in phase6 plan
        phase6_readme = PHASE6_PLAN_DIR / "README.md"
        if not phase6_readme.exists():
            return False

        content = phase6_readme.read_text()
        # Look for promotion validation records indicating success
        if f"{component}" in content.lower():
            # Check for successful promotion markers
            return True
        return False

    # === Signal Family 2: active_docs_entry ===

    def check_active_docs_entry(self) -> None:
        """Verify repo root entrypoints and active phase docs point to current phase6 surfaces."""
        signals = []

        # Check root README for stale phase references in "Start here" / active entry section
        readme_path = PROJECT_ROOT / "README.md"
        if readme_path.exists():
            content = readme_path.read_text()
            # Only flag if "Start here" section points to phase5 (active entry drift),
            # not if phase5 only appears in archive/historical references.
            # Active entry lines look like: "- [ ... phase5 ...](.../phase5/...)"
            import re
            # Match lines in the "Start here" or active navigation sections
            # that reference phase5 (not phase5x, not archived paths)
            active_phase5_pattern = re.compile(
                r'^\s*-\s*\[.*phase5[^0-9].*?\]\(.*?/phase5/.*?\)',
                re.IGNORECASE | re.MULTILINE
            )
            matches = active_phase5_pattern.findall(content)
            if matches:
                signals.append(DriftSignal(
                    signal_id="ADE-001",
                    timestamp=datetime.now().isoformat(),
                    observation="Root README 'Start here' section points to phase5 instead of current phase6",
                    reality_layer="doc reality",
                    evidence_level="D",
                    severity="P3",
                    audit_trigger=False,
                    source_pointers=[str(readme_path)],
                    recommended_next_action="Review and update stale phase references"
                ))

        # Check docs/phase6/README.md exists and references current state
        phase6_docs_readme = PROJECT_ROOT / "docs/phase6"
        if not phase6_docs_readme.exists():
            signals.append(DriftSignal(
                signal_id="ADE-002",
                timestamp=datetime.now().isoformat(),
                observation="docs/phase6 directory not found",
                reality_layer="doc reality",
                evidence_level="D",
                severity="P2",
                audit_trigger=False,
                source_pointers=[str(phase6_docs_readme)],
                recommended_next_action="Create or verify docs/phase6 structure"
            ))

        self.signals.extend(signals)

    # === Signal Family 3: promotion_backfill ===

    def check_promotion_backfill(self) -> None:
        """Parse latest promotion log and compare with Layer 2/3 doc state."""
        signals = []

        latest_log = self._get_latest_promotion_log()
        if not latest_log:
            # No promotion log - this is not necessarily a problem
            return

        log_content = latest_log.read_text()

        # Check for Layer 2 backfill
        adoption_record = self._find_adoption_record(latest_log.stem)
        if "adapter:promoted" in log_content or "runtime:promoted" in log_content:
            if not adoption_record:
                signals.append(DriftSignal(
                    signal_id="PBK-001",
                    timestamp=datetime.now().isoformat(),
                    observation="Promotion log shows success but no Layer 2 adoption record found",
                    reality_layer="doc reality",
                    evidence_level="C",
                    severity="P2",
                    audit_trigger=False,
                    source_pointers=[str(latest_log)],
                    recommended_next_action="Create adoption verification record for this promotion"
                ))

        # Check for full-stack success claimed without evidence
        if "ui:promoted" in log_content:
            ui_record = self._check_ui_promotion_record(latest_log.stem)
            if not ui_record:
                signals.append(DriftSignal(
                    signal_id="PBK-002",
                    timestamp=datetime.now().isoformat(),
                    observation="UI promotion claimed but no corresponding verification record",
                    reality_layer="doc reality",
                    evidence_level="C",
                    severity="P2",
                    audit_trigger=False,
                    source_pointers=[str(latest_log)],
                    recommended_next_action="Document UI promotion in adoption verification records"
                ))

        self.signals.extend(signals)

    def _get_latest_promotion_log(self) -> Optional[Path]:
        """Get the most recent promotion log file."""
        if not PROMOTION_LOG_DIR.exists():
            return None

        logs = list(PROMOTION_LOG_DIR.glob("promotion_*.log"))
        if not logs:
            return None

        return max(logs, key=lambda p: p.stat().st_mtime)

    def _find_adoption_record(self, log_stem: str) -> Optional[Path]:
        """Find adoption record matching the promotion log.

        Layer 2 main record lives at:
          7_docs/internal/phase6/plan/OmniMemora_Adoption_Verification_Records_2026-04-20.md
        Per-date per-component records may additionally exist at:
          docs/phase6/adoption_verification/
        """
        # Extract date from log stem (promotion_YYYYMMDD_HHMMSS)
        date_part = log_stem.replace("promotion_", "")
        if len(date_part) < 8:
            return None
        date_prefix = date_part[:8]  # e.g. "20260420"

        # Primary: Layer 2 main record — pick the one whose filename contains the log date.
        layer2_candidates = list(PHASE6_PLAN_DIR.glob("OmniMemora_Adoption_Verification_Records_*.md"))
        for candidate in layer2_candidates:
            if date_prefix in candidate.stem:
                return candidate

        # Secondary: per-component per-date records
        adoption_dir = PROJECT_ROOT / "docs/phase6/adoption_verification"
        if adoption_dir.exists():
            for record in adoption_dir.glob("*.md"):
                if date_prefix in record.stem:
                    return record
        return None

    def _check_ui_promotion_record(self, log_stem: str) -> bool:
        """Check if UI promotion has corresponding verification record.

        Actual record uses 'verified' / 'success' / 'PASSED' terminology,
        not bare 'pass'.
        """
        record = self._find_adoption_record(log_stem)
        if record and record.exists():
            content = record.read_text()
            # Check for UI component entry with positive outcome
            has_ui = "ui" in content.lower()
            has_success = any(kw in content.lower() for kw in ["verified", "success", "passed"])
            return has_ui and has_success
        return False

    # === Signal Family 4: deployed_revision_alignment ===

    def check_deployed_revision_alignment(self) -> None:
        """Compare repo HEAD, latest promotion log, and deployed-state marker."""
        signals = []

        # Get repo HEAD
        rc, stdout, _ = self.run_command(["git", "rev-parse", "--short", "HEAD"])
        repo_head = stdout.strip() if rc == 0 else "unknown"

        # Get latest promotion log revision
        latest_log = self._get_latest_promotion_log()
        log_revision = "unknown"
        if latest_log and latest_log.exists():
            content = latest_log.read_text()
            for line in content.split("\n"):
                if "repo_revision:" in line:
                    log_revision = line.split(":", 1)[1].strip()
                    break

        # Get deployed-state marker
        marker_path = CURRENT_SERVICE_DIR / ".omnimemora_promotion_state.json"
        marker_revision = "unknown"
        marker_exists = False
        if marker_path.exists():
            marker_exists = True
            try:
                marker_data = json.loads(marker_path.read_text())
                marker_revision = marker_data.get("repo_revision", "unknown")
            except json.JSONDecodeError:
                pass

        # Classify alignment
        if marker_exists:
            if repo_head != marker_revision:
                # Get the list of files changed between marker revision and HEAD.
                # This tells us whether the repo drift touches running-reality paths.
                rc_diff, stdout_diff, _ = self.run_command(
                    ["git", "diff", "--name-only",
                     f"{marker_revision}..{repo_head}"],
                    timeout=10
                )
                diff_paths = stdout_diff.strip().split("\n") if rc_diff == 0 else []

                rr_touched = _paths_touch_running_reality(diff_paths)

                if log_revision == marker_revision or log_revision in ("unknown", ""):
                    if rr_touched:
                        # Genuine running-reality drift; marker needs refresh
                        signals.append(DriftSignal(
                            signal_id="DRA-001",
                            timestamp=datetime.now().isoformat(),
                            observation=f"Repo HEAD ({repo_head}) ahead of deployed marker ({marker_revision}); running-reality paths changed since marker",
                            reality_layer="repo reality",
                            evidence_level="C",
                            severity="P2",
                            audit_trigger=False,
                            source_pointers=[str(marker_path), str(latest_log) if latest_log else ""],
                            recommended_next_action="Run promotion to sync marker with current HEAD"
                        ))
                    # else: diff touches only non-running-reality paths → suppress DRA-001
                else:
                    # log_revision is neither marker_revision nor unknown
                    # → check whether all three genuinely diverge
                    if log_revision != marker_revision:
                        signals.append(DriftSignal(
                            signal_id="DRA-002",
                            timestamp=datetime.now().isoformat(),
                            observation=f"Running marker ({marker_revision}) contradicts repo ({repo_head}) and log ({log_revision})",
                            reality_layer="running reality",
                            evidence_level="A",
                            severity="P1",
                            audit_trigger=True,
                            source_pointers=[str(marker_path), str(latest_log) if latest_log else ""],
                            recommended_next_action="Investigate and resolve deployment state inconsistency"
                        ))
        elif log_revision != "unknown" and log_revision != repo_head:
            signals.append(DriftSignal(
                signal_id="DRA-003",
                timestamp=datetime.now().isoformat(),
                observation=f"Promotion log revision ({log_revision}) differs from repo HEAD ({repo_head}), no marker present",
                reality_layer="doc reality",
                evidence_level="C",
                severity="P3",
                audit_trigger=False,
                source_pointers=[str(latest_log) if latest_log else ""],
                recommended_next_action="Verify promotion was completed or marker was written"
            ))

        self.signals.extend(signals)

    # === Main execution ===

    def run_all_checks(self) -> None:
        """Run all four signal family checks."""
        self.check_running_reality_status()
        self.check_active_docs_entry()
        self.check_promotion_backfill()
        self.check_deployed_revision_alignment()

    def has_audit_triggering_drift(self) -> bool:
        """Return True if any signal has audit_trigger=True."""
        return any(s.audit_trigger for s in self.signals)

    def print_summary(self) -> None:
        """Print summary to stdout."""
        print("\n" + "=" * 60)
        print("OPERATIONAL DRIFT CHECK SUMMARY")
        print("=" * 60)
        print(f"Timestamp: {datetime.now().isoformat()}")
        print(f"Total signals: {len(self.signals)}")

        if not self.signals:
            print("\nNo drift signals detected.")
            return

        # Group by severity
        by_severity = {"P0": [], "P1": [], "P2": [], "P3": []}
        for s in self.signals:
            if s.severity in by_severity:
                by_severity[s.severity].append(s)

        print("\nBy Severity:")
        for sev, sigs in by_severity.items():
            if sigs:
                print(f"  {sev}: {len(sigs)} signal(s)")
                for s in sigs:
                    audit_marker = " [AUDIT TRIGGER]" if s.audit_trigger else ""
                    print(f"    - {s.signal_id}: {s.observation[:60]}...{audit_marker}")

        print("\nAudit Triggers:")
        triggers = [s for s in self.signals if s.audit_trigger]
        if triggers:
            for s in triggers:
                print(f"  - {s.signal_id} ({s.severity}): {s.observation}")
        else:
            print("  None")

    def write_register_entry(self) -> None:
        """Append new entries to the drift register, deduplicating by signal_id.

        Only appends signals that are not already present (open/in_progress) in the register.
        """
        if not self.signals:
            return

        register_path = DRIFT_REGISTER_PATH
        is_new = not register_path.exists()

        # Collect already-registered open/in_progress signal_ids to avoid duplicates
        existing_ids = set()
        if register_path.exists():
            content = register_path.read_text()
            for line in content.split("\n"):
                # Parse table rows: | timestamp | signal_id | ... | status |
                # Trailing | means parts[-1] is empty string
                if line.startswith("|") and "signal_id" not in line:
                    parts = [p.strip() for p in line.split("|")]
                    if len(parts) >= 3:
                        sid = parts[2]  # Signal ID column
                        # Status is last non-empty column (parts[-1] is "" due to trailing |)
                        status = ""
                        for p in reversed(parts):
                            if p:
                                status = p
                                break
                        if sid and status in ("open", "in_progress"):
                            existing_ids.add(sid)

        with open(register_path, "a") as f:
            if is_new:
                f.write("# Operational Drift Register\n\n")
                f.write("> **Status**: Active\n")
                f.write("> **Purpose**: Normal sink for warning/P2-P3 drift, audit-triggering drift\n\n")
                f.write("---\n\n")
                f.write("| Timestamp | Signal ID | Observation | Reality Layer | Evidence | Severity | Audit Trigger | Status |\n")
                f.write("|-----------|-----------|-------------|---------------|----------|----------|---------------|--------|\n")

            for s in self.signals:
                if s.signal_id not in existing_ids:
                    f.write(f"| {s.timestamp} | {s.signal_id} | {s.observation[:50]} | {s.reality_layer} | {s.evidence_level} | {s.severity} | {s.audit_trigger} | {s.status} |\n")


def main():
    parser = argparse.ArgumentParser(
        description="Operational Drift Check for Phase 6"
    )
    parser.add_argument(
        "--write-register",
        action="store_true",
        help="Append/update entries in the drift register"
    )
    args = parser.parse_args()

    checker = OperationalDriftChecker(write_register=args.write_register)

    try:
        checker.run_all_checks()
    except Exception as e:
        print(f"ERROR: Checker encountered an error: {e}", file=sys.stderr)
        sys.exit(2)

    checker.print_summary()

    if args.write_register:
        checker.write_register_entry()
        print(f"\nRegister updated: {DRIFT_REGISTER_PATH}")

    if checker.has_audit_triggering_drift():
        print("\nRESULT: Audit-triggering drift present (exit 1)")
        sys.exit(1)
    else:
        print("\nRESULT: No audit-triggering drift (exit 0)")
        sys.exit(0)


if __name__ == "__main__":
    main()
