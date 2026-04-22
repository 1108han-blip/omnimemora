"""
Golden Case Loader — V1 QC Loop
==============================
Loads golden cases from the golden_cases directory.
"""
import json
import os
import sys
from typing import List, Optional

try:
    from .models import GoldenCase, GateClass, MemoryEntry
except ImportError:
    from models import GoldenCase, GateClass, MemoryEntry


def _get_golden_cases_dir() -> str:
    return os.path.join(
        os.path.dirname(__file__),
        "golden_cases"
    )


def load_golden_cases() -> List[GoldenCase]:
    """
    Load all golden cases from the golden_cases directory.
    Each JSON file in the directory is treated as a case or a collection.
    """
    cases_dir = _get_golden_cases_dir()
    all_cases = []

    if not os.path.exists(cases_dir):
        return all_cases

    for filename in os.listdir(cases_dir):
        if filename.endswith(".json"):
            filepath = os.path.join(cases_dir, filename)
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)

                # Handle both single case and array of cases
                if isinstance(data, list):
                    for item in data:
                        case = _parse_case(item)
                        if case:
                            all_cases.append(case)
                else:
                    case = _parse_case(data)
                    if case:
                        all_cases.append(case)
            except Exception as e:
                print(f"[golden_case_loader] Warning: failed to load {filename}: {e}")

    return all_cases


def _parse_case(data: dict) -> Optional[GoldenCase]:
    """Parse a single golden case from dict data."""
    if "case_id" not in data:
        return None

    # Handle legacy format (only "input" field) - convert to new format
    query = data.get("query") or data.get("input", "")

    # Parse candidate_memories
    candidate_memories = []
    for mem_data in data.get("candidate_memories", []):
        if isinstance(mem_data, dict):
            candidate_memories.append(MemoryEntry(**mem_data))
        elif isinstance(mem_data, str):
            # Legacy format: just a term string
            candidate_memories.append(MemoryEntry(memory_id=mem_data, term=mem_data))

    try:
        gate_class = GateClass(data.get("gate_class", "scored"))
    except ValueError:
        gate_class = GateClass.SCORED

    return GoldenCase(
        case_id=data["case_id"],
        gate_class=gate_class,
        query=query,
        candidate_memories=candidate_memories,
        agent=data.get("agent", "test-agent"),
        client=data.get("client", "test-client"),
        max_local_cards=data.get("max_local_cards", 999),
        candidate_limit=data.get("candidate_limit", 999),
        expected_task_type=data.get("expected_task_type"),
        expected_context_bypass=data.get("expected_context_bypass"),
        required_memory_refs_or_terms=data.get("required_memory_refs_or_terms", []),
        forbidden_memory_refs_or_terms=data.get("forbidden_memory_refs_or_terms", []),
        min_selected=data.get("min_selected", 0),
        max_selected=data.get("max_selected", 999),
    )


def get_golden_cases_summary() -> dict:
    """Get a summary of loaded golden cases."""
    cases = load_golden_cases()
    must_pass = [c for c in cases if c.gate_class == GateClass.MUST_PASS]
    scored = [c for c in cases if c.gate_class == GateClass.SCORED]
    return {
        "total": len(cases),
        "must_pass": len(must_pass),
        "scored": len(scored),
        "case_ids": [c.case_id for c in cases],
    }
