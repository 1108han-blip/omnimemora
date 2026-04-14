#!/usr/bin/env python3
"""
check_depends_on.py — 检查 depends_on 引用的 doc_id 是否存在（仅扫描 frontmatter）
Phase 0: warn. Phase 1: block.
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

def scan_all_ids(root: Path):
    """先扫描所有 doc_id，构建 id -> file 映射"""
    ids = {}
    for md in root.rglob("*.md"):
        if any(x in md.parts for x in _FRONT_EXEMPT):
            continue
        content = md.read_text(encoding="utf-8", errors="ignore")
        meta = parse_fm(content)
        did = meta.get("doc_id")
        if did:
            ids[did] = str(md)
    return ids

def scan_deps(root: Path):
    """收集所有 (file, [deps]) 对"""
    deps = []
    for md in root.rglob("*.md"):
        if any(x in md.parts for x in _FRONT_EXEMPT):
            continue
        content = md.read_text(encoding="utf-8", errors="ignore")
        meta = parse_fm(content)
        raw = meta.get("depends_on", "[]")
        # raw is the VALUE of depends_on key (e.g. '[A, B]'), not the YAML line
        # just extract the bracket contents directly
        m = re.search(r'\[(.*?)\]', raw, re.DOTALL)
        if not m:
            deps.append((str(md), []))
            continue
        inner = m.group(1)
        parsed = [x.strip() for x in inner.replace('\n', '').split(',') if x.strip()]
        deps.append((str(md), parsed))
    return deps

def main():
    root = Path(".")
    all_ids = scan_all_ids(root)
    all_deps = scan_deps(root)
    errors = []
    for file, deps in all_deps:
        for dep in deps:
            if dep and dep not in all_ids:
                errors.append(f"MISSING REF: '{file}' depends_on '{dep}' but it does not exist")
    if errors:
        print("FAIL: Broken depends_on references:")
        for e in errors:
            print(e)
        sys.exit(1)
    print(f"PASS: All depends_on references valid ({len(all_ids)} doc_ids, {len(all_deps)} files checked)")
    sys.exit(0)

if __name__ == "__main__":
    main()
