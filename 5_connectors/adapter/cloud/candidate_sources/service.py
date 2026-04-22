"""Cloud recommendation candidate source orchestrator (skeleton)."""

from __future__ import annotations

from typing import Optional

from ...config import config
from .cloudflare_control_plane import CloudflareCandidateControlClient
from .railway_state_store import RailwayCandidateStateClient


def load_cloud_candidate_policy() -> Optional[dict]:
    """
    Fetch cloud candidate policy without changing local active policy authority.

    Contract:
    - Cloudflare provides candidate pointer entry.
    - Railway provides candidate snapshot/state.
    - Returned policy is candidate-only and optional.
    """
    cloud_cfg = config.cloud
    if not cloud_cfg.candidate_source_enabled:
        return None

    pointer_client = CloudflareCandidateControlClient(
        base_url=cloud_cfg.control_plane_base_url,
        pointer_path=cloud_cfg.control_plane_candidate_path,
        token=cloud_cfg.control_plane_token,
        timeout_ms=cloud_cfg.candidate_timeout_ms,
    )
    pointer = pointer_client.fetch_latest_pointer()
    if pointer is None:
        return None
    if pointer.snapshot_store != "railway":
        return None

    state_client = RailwayCandidateStateClient(
        base_url=cloud_cfg.railway_state_base_url,
        snapshot_path_template=cloud_cfg.railway_snapshot_path_template,
        timeout_ms=cloud_cfg.candidate_timeout_ms,
    )
    snapshot = state_client.fetch_snapshot(pointer.snapshot_id)
    if snapshot is None:
        return None

    policy = snapshot.policy.copy()
    policy.setdefault("policy_source", "cloud_candidate")
    policy.setdefault("policy_status", "candidate")
    policy.setdefault("candidate_id", pointer.candidate_id)
    policy.setdefault("policy_version", pointer.policy_version)
    policy.setdefault("snapshot_id", pointer.snapshot_id)
    policy.setdefault("snapshot_store", pointer.snapshot_store)
    policy.setdefault("cloud_entry", "cloudflare")
    return policy
