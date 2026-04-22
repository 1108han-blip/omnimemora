# SPEC-SKILL-SUGGESTION-MODULE-001

## Goal

Define the Batch 1 module contract for Skill Suggestion as a pure-logic advisory sidecar.

## Module Location

`4_core/logic/skill_suggestion/`

## Files

- `models.py`
- `intent_classifier.py`
- `skill_catalog.py`
- `skill_matcher.py`
- `skill_suggester.py`
- `__init__.py`

## Data Model

`SkillSuggestion` fields:

- `skill_id`
- `title`
- `reason`
- `confidence`
- `source`

## Public Entry

`suggest_skills(query, task_type, agent, client) -> List[SkillSuggestion]`

## Batch 1 Rules

- rule-based intent classification only
- static in-module catalog only
- deterministic output for same input
- empty query => empty suggestions
- `implementation` => empty suggestions
- `decision` / `continuation` => eligible for suggestions

## Engine Integration

- `OptimizationResult.skill_suggestions` (optional sidecar, default empty list)
- suggestions never alter:
  - `packed_context`
  - `selected_memories`
  - meter/quota semantics
