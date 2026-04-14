#!/usr/bin/env python3
"""
check_links.py — 检查 markdown 链接是否指向存在的文件
"""
import re
import sys
from pathlib import Path

MD_LINK = re.compile(r'\[([^\]]+)\]\(([^\)]+)\)')

def main():
    root = Path(".")
    errors = []
    checked = 0
    for md in root.rglob("*.md"):
        if any(x in md.parts for x in [".git", ".pytest_cache", "node_modules"]):
            continue
        checked += 1
        content = md.read_text(encoding="utf-8", errors="ignore")
        fdir = md.parent
        for _, link in MD_LINK.findall(content):
            # skip external URLs, anchors, mailto
            if re.match(r'^(http|https|mailto|#):', link):
                continue
            target = (fdir / link).resolve()
            try:
                rel = target.relative_to(root)
                if not rel.exists():
                    errors.append(f"BROKEN LINK in '{md}': '{link}'")
            except (ValueError, OSError):
                # outside repo or invalid path - skip
                pass
    if errors:
        print("FAIL: Broken links found:")
        for e in errors[:20]:
            print(e)
        if len(errors) > 20:
            print(f"  ... and {len(errors) - 20} more")
        sys.exit(1)
    else:
        print(f"PASS: All links valid ({checked} docs checked)")
        sys.exit(0)

if __name__ == "__main__":
    main()
