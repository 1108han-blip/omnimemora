#!/usr/bin/env python3
"""
check_deprecated.py — 检查 deprecated 文档是否有 supersedes 字段（仅扫描 frontmatter）
"""
import re
import sys
from pathlib import Path

_FRONT_EXEMPT = {".git", ".pytest_cache", "node_modules", "archive"}

def parse_fm(content: str):
    if not content.startswith('---'):
        return {}
    lines = content.split('\n')
    end = -1
    for i, line in enumerate(lines[1:], 1):
        if line.strip() == '---':
            end = i
            break
    if end <= 0:
        return {}
    fm = '\n'.join(lines[1:end])
    meta = {}
    for ln in fm.split('\n'):
        if ': ' in ln:
            k, v = ln.split(': ', 1)
            meta[k.strip()] = v.strip()
    return meta

def main():
    root = Path(".")
    errors = []
    for md in root.rglob("*.md"):
        if any(x in md.parts for x in _FRONT_EXEMPT):
            continue
        content = md.read_text(encoding="utf-8", errors="ignore")
        meta = parse_fm(content)
        if not meta:
            continue
        if meta.get("status") == "deprecated":
            # supersedes 字段内容（可能在同一行或多行）
            raw = meta.get("supersedes", "[]")
            m = re.search(r'^\[(.*?)\]$', raw, re.DOTALL)
            val = m.group(1).strip() if m else ""
            vals = [x.strip() for x in val.replace('\n', '').split(',') if x.strip()]
            if not any(vals):
                errors.append(f"MISSING supersedes: '{md}' is deprecated but has no supersedes")
    if errors:
        print("FAIL: Deprecated docs missing supersedes:")
        for e in errors:
            print(e)
        sys.exit(1)
    print("PASS: All deprecated docs have supersedes")
    sys.exit(0)

if __name__ == "__main__":
    main()
