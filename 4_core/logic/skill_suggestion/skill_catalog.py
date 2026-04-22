from __future__ import annotations

SKILL_CATALOG: list[dict] = [
    {
        "skill_id": "checks",
        "title": "Checks And Validation",
        "intents": ["decision", "continuation"],
        "keywords": ["verify", "validation", "check", "regression", "test", "assert"],
        "source": "static_catalog_v1",
        "priority": 1,
    },
    {
        "skill_id": "refactor",
        "title": "Refactor Guidance",
        "intents": ["decision", "continuation"],
        "keywords": ["refactor", "restructure", "cleanup", "boundary", "layer"],
        "source": "static_catalog_v1",
        "priority": 2,
    },
    {
        "skill_id": "architecture-review",
        "title": "Architecture Review",
        "intents": ["decision"],
        "keywords": ["architecture", "tradeoff", "boundary", "governance", "adr"],
        "source": "static_catalog_v1",
        "priority": 3,
    },
    {
        "skill_id": "handoff-summary",
        "title": "Handoff Summary",
        "intents": ["continuation"],
        "keywords": ["continue", "next", "batch", "handoff", "summary", "status"],
        "source": "static_catalog_v1",
        "priority": 4,
    },
    {
        "skill_id": "risk-triage",
        "title": "Risk Triage",
        "intents": ["decision", "continuation"],
        "keywords": ["risk", "impact", "scope", "warning", "gate"],
        "source": "static_catalog_v1",
        "priority": 5,
    },
]
