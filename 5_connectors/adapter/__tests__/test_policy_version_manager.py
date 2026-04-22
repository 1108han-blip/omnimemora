"""
Unit Tests for Policy Version Manager — V1 QC Loop
==================================================
Uses path injection to avoid polluting the repo manifest.

Run from repo root using -m flag (recommended):
    cd /path/to/repo
    python3 -m 5_connectors.adapter.__tests__.test_policy_version_manager

Or run directly:
    cd /path/to/repo/5_connectors
    python3 adapter/__tests__/test_policy_version_manager.py
"""
import json
import os
import tempfile
import sys

# Ensure adapter is on path for imports
# __file__ is 5_connectors/adapter/__tests__/test_policy_version_manager.py
# dirname is 5_connectors/adapter/__tests__, dirname of that is 5_connectors/adapter/
_adapter_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _adapter_dir not in sys.path:
    sys.path.insert(0, _adapter_dir)

# Also ensure 5_connectors is on path so 'adapter' package is recognized
_connectors_dir = os.path.dirname(_adapter_dir)
if _connectors_dir not in sys.path:
    sys.path.insert(0, _connectors_dir)

from policy_version_manager import (
    PolicyManifest,
    load_active_policy,
    load_candidate_policy,
    load_versioned_policy,
    get_manifest,
    update_manifest,
    promote_candidate,
    _inject_path,
    _clear_injection,
)


def _setup_temp_env():
    """Create a temp directory with a policies subdir and return paths."""
    tmpdir = tempfile.mkdtemp()
    policies_dir = os.path.join(tmpdir, "policies")
    os.makedirs(policies_dir, exist_ok=True)
    manifest_path = os.path.join(policies_dir, "manifest.json")
    fallback_path = os.path.join(tmpdir, "default_policy.json")

    # Create fallback policy
    with open(fallback_path, "w") as f:
        json.dump({
            "version": "local-default-v1",
            "weights": {"relevance": 1.0, "recency": 1.0, "scope": 1.0},
            "compression": {"enabled": True, "mode": "balanced"},
            "selection": {"max_memories": 6}
        }, f)

    # Create initial manifest
    with open(manifest_path, "w") as f:
        json.dump({
            "active_version": "local-default-v1",
            "candidate_version": None,
            "last_verified_report": None,
            "last_promoted_at": None
        }, f)

    return {
        "policies_dir": policies_dir,
        "manifest_path": manifest_path,
        "fallback_policy_path": fallback_path
    }


def run_tests():
    passed = 0
    failed = 0

    # Inject temp paths for all tests
    paths = _setup_temp_env()
    _inject_path(paths)

    try:
        # === TestPolicyManifest ===
        print("\n=== TestPolicyManifest ===")

        # test_manifest_loads_existing
        try:
            manifest = PolicyManifest.load()
            assert manifest.active_version == "local-default-v1", f"got {manifest.active_version}"
            assert manifest.candidate_version is None, f"got {manifest.candidate_version}"
            assert manifest.last_verified_report is None, f"got {manifest.last_verified_report}"
            assert manifest.last_promoted_at is None, f"got {manifest.last_promoted_at}"
            print("PASS: test_manifest_loads_existing")
            passed += 1
        except Exception as e:
            print(f"FAIL: test_manifest_loads_existing - {e}")
            failed += 1

        # test_manifest_save_and_load
        try:
            test_data = {
                "active_version": "test-v1",
                "candidate_version": "test-v2",
                "last_verified_report": "report-001.json",
                "last_promoted_at": "2026-04-22T00:00:00Z",
            }
            with open(paths["manifest_path"], "w") as f:
                json.dump(test_data, f)

            manifest = PolicyManifest.load()
            assert manifest.active_version == "test-v1"
            assert manifest.candidate_version == "test-v2"
            assert manifest.last_verified_report == "report-001.json"
            assert manifest.last_promoted_at == "2026-04-22T00:00:00Z"
            print("PASS: test_manifest_save_and_load")
            passed += 1
        except Exception as e:
            print(f"FAIL: test_manifest_save_and_load - {e}")
            failed += 1

        # === TestLoadVersionedPolicy ===
        print("\n=== TestLoadVersionedPolicy ===")

        # test_load_active_policy_returns_policy
        try:
            policy = load_active_policy()
            assert policy.version == "local-default-v1"
            assert policy.selection.max_memories == 6
            print("PASS: test_load_active_policy_returns_policy")
            passed += 1
        except Exception as e:
            print(f"FAIL: test_load_active_policy_returns_policy - {e}")
            failed += 1

        # test_load_nonexistent_version_falls_back
        try:
            policy = load_versioned_policy("nonexistent-version")
            assert policy.version == "local-default-v1"
            print("PASS: test_load_nonexistent_version_falls_back")
            passed += 1
        except Exception as e:
            print(f"FAIL: test_load_nonexistent_version_falls_back - {e}")
            failed += 1

        # test_load_specific_version
        try:
            policy = load_versioned_policy("local-default-v1")
            assert policy.version == "local-default-v1"
            assert policy.selection.max_memories == 6
            print("PASS: test_load_specific_version")
            passed += 1
        except Exception as e:
            print(f"FAIL: test_load_specific_version - {e}")
            failed += 1

        # === TestUpdateManifest ===
        print("\n=== TestUpdateManifest ===")

        # test_update_manifest_candidate_version
        try:
            manifest = update_manifest(candidate_version="test-candidate-v1")
            assert manifest.candidate_version == "test-candidate-v1"
            # Clear via the proper mechanism
            manifest2 = update_manifest(_clear_candidate=True)
            assert manifest2.candidate_version is None
            print("PASS: test_update_manifest_candidate_version")
            passed += 1
        except Exception as e:
            print(f"FAIL: test_update_manifest_candidate_version - {e}")
            failed += 1

        # test_update_manifest_last_verified_report
        try:
            manifest = update_manifest(last_verified_report="report-002.json")
            assert manifest.last_verified_report == "report-002.json"
            manifest2 = update_manifest(_clear_last_verified_report=True)
            assert manifest2.last_verified_report is None
            print("PASS: test_update_manifest_last_verified_report")
            passed += 1
        except Exception as e:
            print(f"FAIL: test_update_manifest_last_verified_report - {e}")
            failed += 1

        # === TestPromoteCandidate ===
        print("\n=== TestPromoteCandidate ===")

        # test_promote_without_candidate_raises
        try:
            # Ensure no candidate
            update_manifest(_clear_candidate=True)
            try:
                promote_candidate()
                print("FAIL: test_promote_without_candidate_raises - no exception raised")
                failed += 1
            except ValueError as ve:
                if "No candidate version" in str(ve):
                    print("PASS: test_promote_without_candidate_raises")
                    passed += 1
                else:
                    print(f"FAIL: test_promote_without_candidate_raises - wrong message: {ve}")
                    failed += 1
        except Exception as e:
            print(f"FAIL: test_promote_without_candidate_raises - {e}")
            failed += 1

        # test_promote_candidate_switches_active
        try:
            update_manifest(candidate_version="test-promote-v1")
            manifest_before = get_manifest()
            assert manifest_before.candidate_version == "test-promote-v1"

            manifest_after = promote_candidate()
            assert manifest_after.active_version == "test-promote-v1", f"got {manifest_after.active_version}"
            assert manifest_after.candidate_version is None, f"got {manifest_after.candidate_version}"
            assert manifest_after.last_promoted_at is not None

            print("PASS: test_promote_candidate_switches_active")
            passed += 1
        except Exception as e:
            print(f"FAIL: test_promote_candidate_switches_active - {e}")
            failed += 1

        # === TestLocalFallback ===
        print("\n=== TestLocalFallback ===")

        # test_missing_manifest_falls_back_to_default
        try:
            # Remove manifest to trigger fallback
            os.remove(paths["manifest_path"])
            policy = load_active_policy()
            assert policy.version == "local-default-v1"
            print("PASS: test_missing_manifest_falls_back_to_default")
            passed += 1
        except Exception as e:
            print(f"FAIL: test_missing_manifest_falls_back_to_default - {e}")
            failed += 1

    finally:
        # Clean up temp paths
        _clear_injection()
        # Restore manifest to clean state
        with open(paths["manifest_path"], "w") as f:
            json.dump({
                "active_version": "local-default-v1",
                "candidate_version": None,
                "last_verified_report": None,
                "last_promoted_at": None
            }, f)

    print(f"\n{'='*40}")
    print(f"{passed} passed, {failed} failed")
    return failed == 0


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
