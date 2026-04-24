"""Policy surface for Data Lifecycle Plane defaults and env overrides."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class DataLifecyclePolicy:
    summary_ttl_seconds: float = 30.0
    summary_stale_max_age_seconds: float = 3600.0
    summary_file: str = ""
    maintenance_state_file: str = ""
    maintenance_enabled: bool = True
    maintenance_startup_delay_seconds: float = 5.0
    maintenance_interval_seconds: float = 60.0
    maintenance_budget_seconds: float = 8.0


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
    stale_max_age_seconds = float(
        os.getenv("OMNIMEMORA_DLP_SUMMARY_STALE_MAX_AGE_SECONDS", "3600")
    )
    maintenance_enabled = os.getenv(
        "OMNIMEMORA_DLP_MAINTENANCE_ENABLED", "true"
    ).strip().lower() in {"1", "true", "yes", "on"}
    maintenance_startup_delay_seconds = float(
        os.getenv("OMNIMEMORA_DLP_MAINTENANCE_STARTUP_DELAY_SECONDS", "5")
    )
    maintenance_interval_seconds = float(
        os.getenv("OMNIMEMORA_DLP_MAINTENANCE_INTERVAL_SECONDS", "60")
    )
    maintenance_budget_seconds = float(
        os.getenv("OMNIMEMORA_DLP_MAINTENANCE_BUDGET_SECONDS", "8")
    )
    return DataLifecyclePolicy(
        summary_ttl_seconds=max(1.0, ttl_seconds),
        summary_stale_max_age_seconds=max(1.0, stale_max_age_seconds),
        summary_file=summary_file,
        maintenance_state_file=maintenance_state_file,
        maintenance_enabled=maintenance_enabled,
        maintenance_startup_delay_seconds=max(0.0, maintenance_startup_delay_seconds),
        maintenance_interval_seconds=max(1.0, maintenance_interval_seconds),
        maintenance_budget_seconds=max(0.1, maintenance_budget_seconds),
    )
