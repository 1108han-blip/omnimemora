from __future__ import annotations


def classify_intent(query: str, task_type: str | None) -> str:
    q = (query or "").strip().lower()
    if not q:
        return "none"

    t = (task_type or "").strip().lower()
    if t == "implementation":
        return "implementation"
    if t == "decision":
        return "decision"
    if t in {"continuation", ""}:
        return "continuation"
    return "continuation"
