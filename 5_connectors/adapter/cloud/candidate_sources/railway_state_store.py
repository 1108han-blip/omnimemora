"""Railway candidate snapshot/state fetch client (skeleton)."""

from __future__ import annotations

from typing import Any, Optional

import httpx

from .models import CandidateSnapshot


class RailwayCandidateStateClient:
    def __init__(
        self,
        *,
        base_url: str,
        snapshot_path_template: str,
        timeout_ms: float = 800,
    ) -> None:
        self._base_url = (base_url or "").rstrip("/")
        self._snapshot_path_template = snapshot_path_template or ""
        self._timeout = max(float(timeout_ms), 100.0) / 1000.0

    def fetch_snapshot(self, snapshot_id: str) -> Optional[CandidateSnapshot]:
        snapshot_id = (snapshot_id or "").strip()
        if not self._base_url or not self._snapshot_path_template or not snapshot_id:
            return None
        path = self._snapshot_path_template.format(snapshot_id=snapshot_id)
        url = f"{self._base_url}{path}"
        try:
            resp = httpx.get(url, timeout=self._timeout)
            resp.raise_for_status()
            payload = resp.json()
        except Exception:
            return None
        return self._parse_snapshot(snapshot_id, payload)

    @staticmethod
    def _parse_snapshot(snapshot_id: str, payload: Any) -> Optional[CandidateSnapshot]:
        if not isinstance(payload, dict):
            return None
        policy = payload.get("policy")
        if policy is None and isinstance(payload.get("snapshot"), dict):
            policy = payload["snapshot"].get("policy")
        if not isinstance(policy, dict):
            return None
        meta = payload.get("meta")
        policy_version = payload.get("policy_version") or payload.get("version")
        return CandidateSnapshot(
            snapshot_id=snapshot_id,
            policy=policy,
            policy_version=str(policy_version) if policy_version else None,
            source="railway_snapshot",
            meta=meta if isinstance(meta, dict) else {},
        )
