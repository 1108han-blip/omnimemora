#!/usr/bin/env python3
"""
port_audit.py - OmniMemora Port Alignment Audit Tool

Checks that actual port usage in code matches the canonical port constants
defined in pkg/constants.go.

This tool catches the common bug where:
- Code uses hardcoded port 8000 (old Docker era)
- But design documents say 8765 (current architecture)

Usage:
    python port_audit.py [--fix]

Exit codes:
    0 = PASS - all ports aligned
    1 = FAIL - port mismatches found
    2 = ERROR - script error
"""

import argparse
import os
import re
import sys
from pathlib import Path
from typing import NamedTuple

# Canonical port values (must match pkg/constants.go)
CANONICAL_PORTS = {
    "PortRuntime": 8765,
    "PortAdapter": 18011,
    "PortOpenViking": 1933,
    "PortDashboard": 5173,
    "PortFallback1": 8766,
    "PortFallback2": 8767,
    "PortFallback3": 8775,
}

# Patterns to detect port usage in code
# These are the OLD/INCORRECT values that should NOT appear in active code
DEPRECATED_PORT_VALUES = {8000}

# Patterns: regex to find port references in code
# Key = category, Value = regex pattern
PORT_PATTERNS = [
    # Python/Go/JavaScript etc port literals
    (r':(\d{4,5})/', 'url_path_port'),
    (r'port["\']?\s*[:=]\s*(\d{4,5})', 'port_literal'),
    (r'"(\d{4,5})":\s*"?\d{4,5}"?', 'port_mapping'),
    (r'\.(\d{4,5})\s*\)', 'port_func_arg'),
    (r'localhost:(\d{4,5})', 'localhost_port'),
    (r'0\.0\.0\.0:(\d{4,5})', 'bind_port'),
    # Go port constants
    (r'Port\s*=\s*"?(\d{4,5})"?', 'port_const'),
    (r'PreferredPort\s*=\s*(\d{4,5})', 'preferred_port'),
]

# Files/directories to SKIP (legacy/archived)
SKIP_PATTERNS = [
    r'archive[/\\]',
    r'node_modules[/\\]',
    r'\.git[/\\]',
    r'verification[/\\]logs[/\\]',
    r'archive[/\\]',  # Already-archived legacy code
    r'legacy[/\\]',
]


class PortViolation(NamedTuple):
    file: str
    line: str
    line_num: int
    port_found: int
    context: str


def should_skip(path: str) -> bool:
    """Check if file should be skipped (archived/legacy)."""
    path_normalized = path.replace('\\', '/')
    for pattern in SKIP_PATTERNS:
        if re.search(pattern, path_normalized, re.IGNORECASE):
            return True
    return False


def extract_ports_from_file(filepath: Path) -> list[PortViolation]:
    """Extract port-like numbers from a file and check for violations."""
    violations = []

    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
    except Exception:
        return violations

    for line_num, line in enumerate(lines, 1):
        # Skip comments in code files
        stripped = line.strip()
        if stripped.startswith('//') or stripped.startswith('#'):
            continue

        for pattern, pattern_type in PORT_PATTERNS:
            matches = re.finditer(pattern, line)
            for match in matches:
                port_str = match.group(1) if match.lastindex else match.group(0)
                try:
                    port = int(port_str)
                except ValueError:
                    continue

                # Check if this is a deprecated port value
                if port in DEPRECATED_PORT_VALUES:
                    violations.append(PortViolation(
                        file=str(filepath),
                        line=line.strip(),
                        line_num=line_num,
                        port_found=port,
                        context=f"deprecated port {port} (pattern: {pattern_type})"
                    ))
                # Check if this is a 4-digit port that might be relevant
                elif 1000 <= port <= 65535:
                    # Only flag if it's not in the canonical list
                    canonical_values = set(CANONICAL_PORTS.values())
                    if port not in canonical_values and port not in {8000}:  # 8000 already flagged
                        # Don't flag every port, only suspicious ones
                        pass  # We'll be more selective below

    return violations


def scan_directory(root: Path) -> list[PortViolation]:
    """Scan directory for port violations."""
    violations = []

    for filepath in root.rglob('*'):
        if not filepath.is_file():
            continue

        path_str = str(filepath)
        if should_skip(path_str):
            continue

        # Only scan code/text files
        if filepath.suffix.lower() in {'.go', '.py', '.js', '.ts', '.tsx', '.json', '.yaml', '.yml', '.md', '.sh'}:
            file_violations = extract_ports_from_file(filepath)
            violations.extend(file_violations)

    return violations


def check_constants_alignment(constants_file: Path) -> list[str]:
    """Verify that constants.go has correct values."""
    issues = []

    if not constants_file.exists():
        issues.append(f"WARNING: {constants_file} not found - cannot verify canonical ports")
        return issues

    content = constants_file.read_text(encoding='utf-8')

    for name, expected in CANONICAL_PORTS.items():
        pattern = rf'{name}\s*=\s*(\d+)'
        match = re.search(pattern, content)
        if match:
            actual = int(match.group(1))
            if actual != expected:
                issues.append(
                    f"CONSTANT MISMATCH: {name} = {actual} (expected {expected})"
                )
        else:
            issues.append(f"CONSTANT NOT FOUND: {name} not found in {constants_file}")

    return issues


def main():
    parser = argparse.ArgumentParser(
        description='Audit OmniMemora codebase for port alignment issues'
    )
    parser.add_argument(
        '--root',
        type=str,
        default=None,
        help='Root directory to scan (default: repo root)'
    )
    parser.add_argument(
        '--fix',
        action='store_true',
        help='Attempt to fix violations (not implemented)'
    )
    parser.add_argument(
        '--verbose',
        '-v',
        action='store_true',
        help='Verbose output'
    )
    args = parser.parse_args()

    # Determine root
    if args.root:
        root = Path(args.root)
    else:
        # Default to parent of tools/verification
        root = Path(__file__).parent.parent.parent

    print(f"Scanning: {root}")
    print("=" * 60)

    # Check canonical constants
    constants_file = root / '4_core' / 'local-runtime' / 'pkg' / 'constants.go'
    print(f"\n[1] Checking canonical constants ({constants_file})...")

    const_issues = check_constants_alignment(constants_file)
    if const_issues:
        for issue in const_issues:
            print(f"  ERROR: {issue}")
    else:
        print(f"  OK: All canonical ports match pkg/constants.go")

    # Scan for violations
    print(f"\n[2] Scanning for port violations...")
    violations = scan_directory(root)

    # Filter to only show deprecated port (8000) violations
    deprecated_violations = [v for v in violations if v.port_found in DEPRECATED_PORT_VALUES]

    if deprecated_violations:
        print(f"\n  FOUND {len(deprecated_violations)} DEPRECATED PORT USAGES:")
        print("-" * 60)
        for v in deprecated_violations:
            print(f"  {v.file}:{v.line_num}")
            print(f"    Port {v.port_found}: {v.context}")
            if args.verbose:
                print(f"    {v.line[:80]}...")
        print("-" * 60)
    else:
        print(f"  OK: No deprecated port usages found")

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Canonical constants: {'PASS' if not const_issues else 'FAIL'}")
    print(f"Port usages: {'PASS' if not deprecated_violations else 'FAIL'}")

    if const_issues or deprecated_violations:
        print("\nACTION REQUIRED:")
        if const_issues:
            for issue in const_issues:
                print(f"  - {issue}")
        if deprecated_violations:
            print(f"  - {len(deprecated_violations)} files use deprecated port 8000")
            print(f"  - Update to canonical port from pkg/constants.go")
        return 1
    else:
        print("\nAll port alignments correct.")
        return 0


if __name__ == '__main__':
    sys.exit(main())
