"""Cloudflare candidate pointer fetch entry (skeleton)."""

from __future__ import annotations

from typing import Any, Optional

import httpx

from .models import CandidatePointer


class CloudflareCandidateControlClient:
    def __init__(
        self,
        *,
        base_url: str,
        pointer_path: str,
        token: str = "",
        timeout_ms: float = 800,
    ) -> None:
        self._base_url = (base_url or "").rstrip("/")
        self._pointer_path = pointer_path or ""
        self._token = token or ""
        self._timeout = max(float(timeout_ms), 100.0) / 1000.0

    def fetch_latest_pointer(self) -> Optional[CandidatePointer]:
        if not self._base_url or not self._pointer_path:
            return None
        url = f"{self._base_url}{self._pointer_path}"
        headers: dict[str, str] = {}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        try:
            resp = httpx.get(url, headers=headers, timeout=self._timeout)
            resp.raise_for_status()
            payload = resp.json()
        except Exception:
            return None
        return self._parse_pointer(payload)

    @staticmethod
    def _parse_pointer(payload: Any) -> Optional[CandidatePointer]:
        if not isinstance(payload, dict):
            return None
        source = payload.get("candidate")
        if isinstance(source, dict):
            payload = source
        candidate_id = str(payload.get("candidate_id") or "").strip()
        policy_version = str(payload.get("policy_version") or "").strip()
        snapshot_id = str(payload.get("snapshot_id") or "").strip()
        if not candidate_id or not policy_version or not snapshot_id:
            return None
        meta = payload.get("meta")
        return CandidatePointer(
            candidate_id=candidate_id,
            policy_version=policy_version,
            snapshot_id=snapshot_id,
            snapshot_store=str(payload.get("snapshot_store") or "railway"),
            fetched_at=str(payload.get("fetched_at") or "") or None,
            meta=meta if isinstance(meta, dict) else {},
        )
