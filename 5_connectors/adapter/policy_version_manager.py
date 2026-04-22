"""
Policy Version Manager — V1 Local-First Quality Control Loop
==============================================================
Loads policies from versioned directory (5_connectors/adapter/config/policies/).
- Primary: manifest.json → active_version → {version}.json
- Fallback: default_policy.json (only when manifest/version file is missing)
- V1: cloud policy cannot override local active selection

Testing support: Use _inject_path() to override paths for unit tests.
"""
import json
import os
from typing import Optional
from datetime import datetime

try:
    from adapter.cloud.models import Policy
except ImportError:
    try:
        from cloud.models import Policy
    except ImportError:
        from .cloud.models import Policy


# Path injection for testing — set to a dict with keys:
# "policies_dir", "manifest_path", "fallback_policy_path"
_injected_path: Optional[dict] = None


def _inject_path(paths: dict) -> None:
    """Inject custom paths for testing. Pass None to clear."""
    global _injected_path
    _injected_path = paths


def _clear_injection() -> None:
    """Clear any injected paths."""
    global _injected_path
    _injected_path = None


def _get_policies_dir() -> str:
    if _injected_path and "policies_dir" in _injected_path:
        return _injected_path["policies_dir"]
    return os.path.abspath(
        os.path.join(os.path.dirname(__file__), "config", "policies")
    )


def _get_manifest_path() -> str:
    if _injected_path and "manifest_path" in _injected_path:
        return _injected_path["manifest_path"]
    return os.path.join(_get_policies_dir(), "manifest.json")


def _get_fallback_policy_path() -> str:
    if _injected_path and "fallback_policy_path" in _injected_path:
        return _injected_path["fallback_policy_path"]
    return os.path.abspath(
        os.path.join(os.path.dirname(__file__), "config", "default_policy.json")
    )


class PolicyManifest:
    """Represents the policy manifest."""

    def __init__(
        self,
        active_version: Optional[str] = None,
        candidate_version: Optional[str] = None,
        last_verified_report: Optional[str] = None,
        last_promoted_at: Optional[str] = None,
    ):
        self.active_version = active_version
        self.candidate_version = candidate_version
        self.last_verified_report = last_verified_report
        self.last_promoted_at = last_promoted_at

    @classmethod
    def load(cls) -> "PolicyManifest":
        manifest_path = _get_manifest_path()
        try:
            if os.path.exists(manifest_path):
                with open(manifest_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return cls(
                        active_version=data.get("active_version"),
                        candidate_version=data.get("candidate_version"),
                        last_verified_report=data.get("last_verified_report"),
                        last_promoted_at=data.get("last_promoted_at"),
                    )
        except Exception:
            pass
        return cls()

    def save(self) -> None:
        manifest_path = _get_manifest_path()
        os.makedirs(os.path.dirname(manifest_path), exist_ok=True)
        data = {
            "active_version": self.active_version,
            "candidate_version": self.candidate_version,
            "last_verified_report": self.last_verified_report,
            "last_promoted_at": self.last_promoted_at,
        }
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)


def load_versioned_policy(version: Optional[str] = None) -> Policy:
    """
    Load a specific policy version from the versioned directory.
    If version is None, loads the active version from manifest.
    Falls back to default_policy.json if manifest or version file is missing.
    """
    manifest = PolicyManifest.load()

    if version is None:
        version = manifest.active_version

    if version:
        version_path = os.path.join(_get_policies_dir(), f"{version}.json")
        if os.path.exists(version_path):
            try:
                with open(version_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return Policy(**data)
            except Exception:
                pass

    # Fallback to legacy default_policy.json
    return _load_fallback_policy()


def _load_fallback_policy() -> Policy:
    """Load the legacy default_policy.json as fallback."""
    fallback_path = _get_fallback_policy_path()
    try:
        with open(fallback_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return Policy(**data)
    except Exception:
        return Policy()


def load_active_policy() -> Policy:
    """Load the currently active policy (local-first, V1)."""
    return load_versioned_policy(None)


def load_candidate_policy() -> Optional[Policy]:
    """Load the candidate policy if one exists."""
    manifest = PolicyManifest.load()
    if manifest.candidate_version:
        return load_versioned_policy(manifest.candidate_version)
    return None


def get_manifest() -> PolicyManifest:
    """Get the current policy manifest."""
    return PolicyManifest.load()


def update_manifest(
    candidate_version: Optional[str] = None,
    last_verified_report: Optional[str] = None,
    last_promoted_at: Optional[str] = None,
    _clear_candidate: bool = False,
    _clear_last_verified_report: bool = False,
) -> PolicyManifest:
    """
    Update manifest fields.
    Use this to record verification results and promotion timestamps.
    Use _clear_*=True to explicitly clear fields.
    NOTE: Only promote_candidate() sets last_promoted_at. This function
    only updates last_verified_report to record QC verification results.
    """
    manifest = PolicyManifest.load()
    if _clear_candidate:
        manifest.candidate_version = None
    elif candidate_version is not None:
        manifest.candidate_version = candidate_version
    if _clear_last_verified_report:
        manifest.last_verified_report = None
    elif last_verified_report is not None:
        manifest.last_verified_report = last_verified_report
    if last_promoted_at is not None:
        manifest.last_promoted_at = last_promoted_at
    manifest.save()
    return manifest


def record_verification(report_id: str) -> PolicyManifest:
    """
    Record that a verification report was generated.
    This updates last_verified_report but does NOT change active_version.
    Only promote_candidate() changes active_version.
    """
    return update_manifest(last_verified_report=report_id)


def promote_candidate() -> PolicyManifest:
    """
    Promote candidate to active (manual promotion only).
    Updates manifest: active_version ← candidate_version, clears candidate.
    Sets last_promoted_at to current timestamp.
    """
    manifest = PolicyManifest.load()
    if not manifest.candidate_version:
        raise ValueError("No candidate version to promote")

    manifest.active_version = manifest.candidate_version
    manifest.last_promoted_at = datetime.utcnow().isoformat() + "Z"
    manifest.candidate_version = None
    manifest.save()
    return manifest
