#!/usr/bin/env python3
"""
doc-metrics.py — OmniMemora 文档一致性指标量化脚本
运行方式: python tools/docs/doc-metrics.py
输出: SLO 仪表板 + 详细指标
"""
import re
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(".")
DATE_FMT = "%Y-%m-%d"

EXEMPT_PATHS = {".git", ".pytest_cache", "node_modules", "archive"}
EXEMPT_FILES = {"AGENTS.md","SOUL.md","USER.md","TOOLS.md","HEARTBEAT.md",".github/pull_request_template.md"}

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
    for line in fm.split('\n'):
        if ': ' in line:
            k, v = line.split(': ', 1)
            meta[k.strip()] = v.strip()
    return meta

def parse_date(s: str):
    try:
        return datetime.strptime(s, DATE_FMT).replace(tzinfo=timezone.utc)
    except:
        return None

def main():
    # ---- PASS 1: 扫描所有 frontmatter，建立 doc_id 索引 ----
    all_ids = {}
    docs_with_fm = []
    for md in ROOT.rglob("*.md"):
        if any(x in md.parts for x in EXEMPT_PATHS):
            continue
        if md.name in EXEMPT_FILES:
            continue
        content = md.read_text(encoding="utf-8", errors="ignore")
        meta = parse_fm(content)
        if not meta:
            continue
        doc_id = meta.get("doc_id", "?")
        status = meta.get("status", "?")
        effective = meta.get("effective_date", "")
        if doc_id and doc_id != "?":
            all_ids[doc_id] = str(md)
        docs_with_fm.append({
            'id': doc_id,
            'status': status,
            'effective_date': effective,
            'path': str(md),
            'meta': meta,
        })

    # ---- PASS 2: 检查 broken depends_on ----
    orphan_deps = []
    deprecated_no_supersedes = []
    for d in docs_with_fm:
        meta = d['meta']
        status = meta.get("status", "?")
        # deprecated check
        if status == "deprecated":
            raw_sup = meta.get("supersedes", "[]").strip()
            if not raw_sup or raw_sup == "[]":
                deprecated_no_supersedes.append(d['path'])
        # depends_on check
        raw = meta.get("depends_on", "[]")
        m = re.search(r'\[(.*?)\]', raw, re.DOTALL)
        if m:
            inner = m.group(1)
            deps = [x.strip() for x in inner.replace('\n', '').split(',') if x.strip()]
            for dep in deps:
                if dep and dep not in all_ids:
                    orphan_deps.append((d['path'], dep))

    # ---- Metric 1: Alignment Rate ----
    aligned = [d for d in docs_with_fm if d['status'] not in ('draft', '?')]
    alignment_rate = len(aligned) / len(docs_with_fm) * 100 if docs_with_fm else 0

    # ---- Metric 2: Stale Doc Age ----
    now = datetime.now(timezone.utc)
    stale_docs = []
    for d in docs_with_fm:
        if d['effective_date']:
            eff = parse_date(d['effective_date'])
            if eff:
                age = (now - eff).days
                if age > 60:
                    stale_docs.append((d['path'], age))
    stale_age = max(
        [(now - parse_date(d['effective_date'])).days
         for d in docs_with_fm if d['effective_date'] and parse_date(d['effective_date'])]
        or [0]
    )

    # ---- Metric 3: Orphan Doc Rate ----
    no_deps = [d for d in docs_with_fm
               if d['id'] not in ('?',) and 'depends_on' not in
               open(d['path'], encoding='utf-8', errors='ignore').read()]
    orphan_rate = len(no_deps) / len(docs_with_fm) * 100 if docs_with_fm else 0

    # ---- Output ----
    print("=" * 60)
    print("OmniMemora 文档一致性指标")
    print(f"扫描时间: {datetime.now().strftime('%Y-%m-%d %H:%M UTC')}")
    print("=" * 60)
    print()
    print(f"📊 Doc-Code Alignment Rate: {alignment_rate:.1f}%  (目标: ≥ 95%)")
    print(f"   有 frontmatter 文档: {len(docs_with_fm)}")
    print(f"   其中 active/deprecated: {len(aligned)}")
    print()
    print(f"📅 Stale Doc Age: {stale_age} 天  (目标: ≤ 60 天)")
    if stale_docs:
        print(f"   ⚠️  超过 60 天未更新:")
        for p, days in stale_docs[:5]:
            print(f"      {days} 天: {p}")
    else:
        print(f"   ✅ 所有文档在 60 天窗口内")
    print()
    print(f"🔗 Orphan Doc Rate: {orphan_rate:.1f}%  (目标: ≤ 5%)")
    if no_deps:
        print(f"   无 depends_on 的 active 文档:")
        for d in no_deps[:5]:
            print(f"      {d['path']}")
    print()
    print(f"⚠️  Deprecated 无 supersedes: {len(deprecated_no_supersedes)}  (目标: 0)")
    if deprecated_no_supersedes:
        for p in deprecated_no_supersedes:
            print(f"      {p}")
    print()
    print(f"🔍 Broken depends_on 引用: {len(orphan_deps)}  (目标: 0)")
    if orphan_deps:
        for doc, dep in orphan_deps:
            print(f"      {doc} → depends_on:'{dep}'")
    print()
    print("-" * 60)
    print("SLO 总结:")
    slos = [
        ("Alignment Rate ≥ 95%", alignment_rate >= 95, f"{alignment_rate:.1f}%"),
        ("Stale Age ≤ 60 天", stale_age <= 60, f"{stale_age} 天"),
        ("Deprecated 有 supersedes", len(deprecated_no_supersedes) == 0, f"{len(deprecated_no_supersedes)} 项违规"),
        ("Broken depends_on = 0", len(orphan_deps) == 0, f"{len(orphan_deps)} 项"),
    ]
    all_pass = True
    for name, passed, val in slos:
        icon = "✅" if passed else "❌"
        print(f"  {icon} {name}: {val}")
        if not passed:
            all_pass = False
    print()
    print(f"总体: {'✅ 全部 SLO 达标' if all_pass else '❌ 存在违规项，请优先修复'}")

if __name__ == "__main__":
    main()
