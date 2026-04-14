#!/usr/bin/env python3
"""
check_metadata.py — 检查文档是否包含必填元数据字段（仅扫描 frontmatter）
Required: doc_id, title, status, version
Excludes: archive/, .pytest_cache/, node_modules/, workspace config files
"""
import re
import sys
from pathlib import Path

REQUIRED_FIELDS = ["doc_id", "title", "status", "version"]
EXEMPT_FILES = {
    "AGENTS.md", "SOUL.md", "USER.md", "TOOLS.md", "HEARTBEAT.md",
}
EXEMPT_PATHS = {".git", ".pytest_cache", "node_modules", "archive"}

def parse_fm(content: str):
    if not content.startswith('---'):
        return None
    lines = content.split('\n')
    end = -1
    for i, line in enumerate(lines[1:], 1):
        if line.strip() == '---':
            end = i
            break
    if end <= 0:
        return None
    meta = {}
    for ln in lines[1:end]:
        if ': ' in ln:
            k, v = ln.split(': ', 1)
            meta[k.strip()] = v.strip()
    return meta

def main():
    root = Path(".")
    errors = []
    checked = 0
    for md in root.rglob("*.md"):
        if any(x in md.parts for x in EXEMPT_PATHS):
            continue
        if md.name in EXEMPT_FILES:
            continue
        content = md.read_text(encoding="utf-8", errors="ignore")
        meta = parse_fm(content)
        if meta is None:
            continue
        checked += 1
        missing = [f for f in REQUIRED_FIELDS if f not in meta]
        if missing:
            errors.append(f"MISSING FIELDS in '{md}': {missing}")
    if errors:
        print("FAIL: Documents with missing required fields:")
        for e in errors:
            print(e)
        sys.exit(1)
    print(f"PASS: All {checked} docs with frontmatter have required fields")
    sys.exit(0)

if __name__ == "__main__":
    main()
