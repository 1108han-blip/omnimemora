from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SkillSuggestion:
    skill_id: str
    title: str
    reason: str
    confidence: float
    source: str

    def to_dict(self) -> dict:
        return {
            "skill_id": self.skill_id,
            "title": self.title,
            "reason": self.reason,
            "confidence": self.confidence,
            "source": self.source,
        }
