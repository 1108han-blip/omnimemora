from __future__ import annotations

from .models import SkillSuggestion


def _confidence_from_hits(hits: int) -> float:
    # deterministic, bounded [0.0, 1.0]
    if hits <= 0:
        return 0.0
    if hits == 1:
        return 0.55
    if hits == 2:
        return 0.72
    return 0.86


def match_skills(query: str, intent: str, catalog: list[dict], limit: int = 3) -> list[SkillSuggestion]:
    q = (query or "").strip().lower()
    if not q or intent in {"none", "implementation"}:
        return []

    ranked: list[tuple[int, int, dict]] = []
    for item in catalog:
        intents = item.get("intents", [])
        if intent not in intents:
            continue
        keywords = item.get("keywords", [])
        hits = sum(1 for kw in keywords if kw in q)
        if hits <= 0:
            continue
        priority = int(item.get("priority", 100))
        ranked.append((-hits, priority, item))

    ranked.sort(key=lambda x: (x[0], x[1], x[2].get("skill_id", "")))

    out: list[SkillSuggestion] = []
    for neg_hits, _priority, item in ranked[:limit]:
        hits = -neg_hits
        out.append(
            SkillSuggestion(
                skill_id=item["skill_id"],
                title=item["title"],
                reason=f"Matched {hits} intent keywords for {intent} task",
                confidence=_confidence_from_hits(hits),
                source=item.get("source", "static_catalog_v1"),
            )
        )
    return out
