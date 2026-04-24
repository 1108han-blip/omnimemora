"""Hot summary store with atomic write/read and freshness checks."""

from __future__ import annotations

import json
import os
import tempfile
import time
from pathlib import Path
from typing import Any, Optional

from .policy import DataLifecyclePolicy, load_policy


def _summary_path(policy: Optional[DataLifecyclePolicy] = None) -> Path:
    current = policy or load_policy()
    return Path(current.summary_file).expanduser()


def write_summary_atomic(summary_payload: dict[str, Any], policy: Optional[DataLifecyclePolicy] = None) -> None:
    path = _summary_path(policy)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix="dlp_summary_", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(summary_payload, fh, ensure_ascii=False, indent=2)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, str(path))
    except Exception:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise


def read_summary(policy: Optional[DataLifecyclePolicy] = None) -> Optional[dict[str, Any]]:
    path = _summary_path(policy)
    if not path.exists():
        return None
    try:
        with path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
            if isinstance(data, dict):
                return data
    except Exception:
        return None
    return None


def is_summary_fresh(
    payload: Optional[dict[str, Any]],
    *,
    policy: Optional[DataLifecyclePolicy] = None,
    now_ts: Optional[float] = None,
) -> bool:
    if not isinstance(payload, dict):
        return False
    generated_at = payload.get("generated_at")
    if not isinstance(generated_at, (int, float)):
        return False
    current = policy or load_policy()
    now = float(now_ts if now_ts is not None else time.time())
    return (now - float(generated_at)) <= float(current.summary_ttl_seconds)


def read_fresh_summary(
    policy: Optional[DataLifecyclePolicy] = None,
    *,
    now_ts: Optional[float] = None,
) -> Optional[dict[str, Any]]:
    payload = read_summary(policy)
    if not is_summary_fresh(payload, policy=policy, now_ts=now_ts):
        return None
    return payload
