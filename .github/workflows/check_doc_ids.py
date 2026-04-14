#!/usr/bin/env python3
"""
check_doc_ids.py — 检查所有 .md 文件中的 doc_id 是否唯一（仅扫描 frontmatter）
"""
import re
import sys
from pathlib import Path

def extract_frontmatter_doc_id(content: str):
    """只从 YAML frontmatter 中提取 doc_id（避免代码块干扰）"""
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
    frontmatter = '\n'.join(lines[1:end])
    m = re.search(r'^doc_id:\s*(\S+)\s*$', frontmatter, re.MULTILINE)
    return m.group(1) if m else None

def scan_docs(root: Path):
    doc_ids = {}
    for md in root.rglob("*.md"):
        if any(x in md.parts for x in [".git", ".pytest_cache", "node_modules", "archive"]):
            continue
        content = md.read_text(encoding="utf-8", errors="ignore")
        doc_id = extract_frontmatter_doc_id(content)
        if doc_id:
            doc_ids[doc_id] = str(md.relative_to(root))
    return doc_ids

def main():
    root = Path(".")
    doc_ids = scan_docs(root)
    by_file = {}
    for doc_id, file in doc_ids.items():
        by_file.setdefault(doc_id, []).append(file)
    errors = [f"DUPLICATE doc_id: '{k}' appears in:\n  " + "\n  ".join(v)
              for k, v in by_file.items() if len(v) > 1]
    if errors:
        print("FAIL: Duplicate doc_ids found:")
        for e in errors:
            print(e)
        sys.exit(1)
    else:
        print(f"PASS: All doc_ids unique ({len(doc_ids)} docs with frontmatter scanned)")
        sys.exit(0)

if __name__ == "__main__":
    main()
