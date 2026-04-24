"""Policy surface for Data Lifecycle Plane defaults and env overrides."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class DataLifecyclePolicy:
    summary_ttl_seconds: float
    summary_file: str
    maintenance_state_file: str


def _default_data_lifecycle_dir() -> Path:
    return Path.home() / ".omnimemora" / "adapter" / "data_lifecycle"


def load_policy() -> DataLifecyclePolicy:
    base_dir = Path(
        os.getenv("OMNIMEMORA_DLP_DIR", str(_default_data_lifecycle_dir()))
    ).expanduser()
    summary_file = os.getenv(
        "OMNIMEMORA_DLP_SUMMARY_FILE",
        str(base_dir / "family_window_summary.json"),
    )
    maintenance_state_file = os.getenv(
        "OMNIMEMORA_DLP_MAINTENANCE_STATE_FILE",
        str(base_dir / "maintenance_state.jsonl"),
    )
    ttl_seconds = float(os.getenv("OMNIMEMORA_DLP_SUMMARY_TTL_SECONDS", "30"))
    return DataLifecyclePolicy(
        summary_ttl_seconds=max(1.0, ttl_seconds),
        summary_file=summary_file,
        maintenance_state_file=maintenance_state_file,
    )
