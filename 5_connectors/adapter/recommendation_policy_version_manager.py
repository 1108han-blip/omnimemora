"""
Recommendation Policy Version Manager
=====================================
Local-first recommendation policy manifest management.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional


_injected_path: Optional[dict] = None


def _inject_path(paths: dict) -> None:
    global _injected_path
    _injected_path = paths


def _clear_injection() -> None:
    global _injected_path
    _injected_path = None


def _get_policies_dir() -> str:
    if _injected_path and "policies_dir" in _injected_path:
        return _injected_path["policies_dir"]
    return os.path.abspath(
        os.path.join(os.path.dirname(__file__), "config", "recommendation_policies")
    )


def _get_manifest_path() -> str:
    if _injected_path and "manifest_path" in _injected_path:
        return _injected_path["manifest_path"]
    return os.path.join(_get_policies_dir(), "manifest.json")


@dataclass
class RecommendationPolicyManifest:
    active_version: Optional[str] = None
    candidate_version: Optional[str] = None
    last_verified_report: Optional[str] = None
    last_promoted_at: Optional[str] = None

    @classmethod
    def load(cls) -> "RecommendationPolicyManifest":
        path = _get_manifest_path()
        try:
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
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
        path = _get_manifest_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "active_version": self.active_version,
                    "candidate_version": self.candidate_version,
                    "last_verified_report": self.last_verified_report,
                    "last_promoted_at": self.last_promoted_at,
                },
                f,
                ensure_ascii=False,
                indent=2,
            )


def _load_version(version: Optional[str]) -> Optional[dict[str, Any]]:
    if not version:
        return None
    path = os.path.join(_get_policies_dir(), f"{version}.json")
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            return data
    except Exception:
        return None
    return None


def load_active_recommendation_policy() -> Optional[dict[str, Any]]:
    manifest = RecommendationPolicyManifest.load()
    return _load_version(manifest.active_version)


def load_candidate_recommendation_policy() -> Optional[dict[str, Any]]:
    manifest = RecommendationPolicyManifest.load()
    return _load_version(manifest.candidate_version)


def get_recommendation_manifest() -> RecommendationPolicyManifest:
    return RecommendationPolicyManifest.load()


def update_recommendation_manifest(
    candidate_version: Optional[str] = None,
    last_verified_report: Optional[str] = None,
    _clear_candidate: bool = False,
    _clear_last_verified_report: bool = False,
) -> RecommendationPolicyManifest:
    manifest = RecommendationPolicyManifest.load()
    if _clear_candidate:
        manifest.candidate_version = None
    elif candidate_version is not None:
        manifest.candidate_version = candidate_version

    if _clear_last_verified_report:
        manifest.last_verified_report = None
    elif last_verified_report is not None:
        manifest.last_verified_report = last_verified_report

    manifest.save()
    return manifest


def promote_recommendation_candidate() -> RecommendationPolicyManifest:
    manifest = RecommendationPolicyManifest.load()
    if not manifest.candidate_version:
        raise ValueError("No candidate recommendation policy to promote")
    manifest.active_version = manifest.candidate_version
    manifest.candidate_version = None
    manifest.last_promoted_at = datetime.utcnow().isoformat() + "Z"
    manifest.save()
    return manifest
