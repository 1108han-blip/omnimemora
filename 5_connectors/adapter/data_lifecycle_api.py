"""Read-only lifecycle health and manual refresh APIs for Data Lifecycle Plane."""

from __future__ import annotations

import asyncio
import importlib

from fastapi import APIRouter, HTTPException, Query

router = APIRouter(tags=["data-lifecycle"])

_health = importlib.import_module("5_connectors.adapter.data_lifecycle.health")
_policy_mod = importlib.import_module("5_connectors.adapter.data_lifecycle.policy")
_maintenance_manager_mod = importlib.import_module("5_connectors.adapter.data_lifecycle.maintenance_manager")
_retention_mod = importlib.import_module("5_connectors.adapter.data_lifecycle.retention")
_traceability_mod = importlib.import_module("5_connectors.adapter.data_lifecycle.traceability")
_archive_plan_mod = importlib.import_module("5_connectors.adapter.data_lifecycle.archive_plan")
_archive_txn_mod = importlib.import_module("5_connectors.adapter.data_lifecycle.archive_transaction")
_archive_restore_mod = importlib.import_module("5_connectors.adapter.data_lifecycle.archive_restore_contract")
_archive_gate_mod = importlib.import_module("5_connectors.adapter.data_lifecycle.archive_execution_gate")
_archive_approval_mod = importlib.import_module("5_connectors.adapter.data_lifecycle.archive_approval")
_archive_pilot_mod = importlib.import_module("5_connectors.adapter.data_lifecycle.archive_pilot")
_archive_readthrough_mod = importlib.import_module("5_connectors.adapter.data_lifecycle.archive_readthrough")
_archive_fallback_mod = importlib.import_module("5_connectors.adapter.data_lifecycle.archive_fallback_contract")
_archive_quarantine_mod = importlib.import_module("5_connectors.adapter.data_lifecycle.archive_quarantine_readiness")
_archive_quarantine_exec_mod = importlib.import_module("5_connectors.adapter.data_lifecycle.archive_quarantine")
_archive_restore_pilot_mod = importlib.import_module("5_connectors.adapter.data_lifecycle.archive_restore_pilot")
_archive_non_active_candidates_mod = importlib.import_module("5_connectors.adapter.data_lifecycle.archive_non_active_candidates")
_archive_non_active_quarantine_mod = importlib.import_module("5_connectors.adapter.data_lifecycle.archive_non_active_quarantine_readiness")
_archive_non_active_gate_mod = importlib.import_module("5_connectors.adapter.data_lifecycle.archive_non_active_execution_gate")
_archive_non_active_quarantine_exec_mod = importlib.import_module(
    "5_connectors.adapter.data_lifecycle.archive_non_active_quarantine"
)
_raw_evidence_segments_mod = importlib.import_module("5_connectors.adapter.data_lifecycle.raw_evidence_segments")
_meter_storage_v2_mod = importlib.import_module("5_connectors.adapter.data_lifecycle.meter_storage_v2")
_meter_cleanup_preview_mod = importlib.import_module("5_connectors.adapter.data_lifecycle.meter_cleanup_preview")
_meter_cleanup_execution_gate_mod = importlib.import_module(
    "5_connectors.adapter.data_lifecycle.meter_cleanup_execution_gate"
)
_meter_cleanup_transaction_preview_mod = importlib.import_module(
    "5_connectors.adapter.data_lifecycle.meter_cleanup_transaction_preview"
)
_meter_cleanup_rollback_drill_mod = importlib.import_module(
    "5_connectors.adapter.data_lifecycle.meter_cleanup_rollback_drill"
)
_meter_cleanup_pilot_mod = importlib.import_module(
    "5_connectors.adapter.data_lifecycle.meter_cleanup_quarantine_pilot"
)
_meter_cleanup_stability_window_mod = importlib.import_module(
    "5_connectors.adapter.data_lifecycle.meter_cleanup_stability_window"
)
try:
    _meter_cleanup_scaleup_readiness_mod = importlib.import_module(
        "5_connectors.adapter.data_lifecycle.meter_cleanup_scaleup_readiness"
    )
except Exception:
    class _MissingMeterCleanupScaleupReadinessModule:
        METER_CLEANUP_SCALEUP_READINESS_SCHEMA_VERSION = "res-legacy-meter-cleanup-scaleup-readiness-v1"
        METER_CLEANUP_SCALEUP_READINESS_REBUILD_SCHEMA_VERSION = (
            "res-legacy-meter-cleanup-scaleup-readiness-rebuild-v1"
        )
        METER_CLEANUP_SCALEUP_READINESS_MODE = "scaleup_readiness_only"

        @staticmethod
        def read_readiness_report(policy=None):
            return None

        @staticmethod
        def rebuild_readiness_report(policy=None):
            raise RuntimeError("meter cleanup scaleup readiness module unavailable")

    _meter_cleanup_scaleup_readiness_mod = _MissingMeterCleanupScaleupReadinessModule()
try:
    _meter_cleanup_repeatable_pilot_protocol_mod = importlib.import_module(
        "5_connectors.adapter.data_lifecycle.meter_cleanup_repeatable_pilot_protocol"
    )
except Exception:
    class _MissingMeterCleanupRepeatablePilotProtocolModule:
        METER_CLEANUP_REPEATABLE_PILOT_PROTOCOL_SCHEMA_VERSION = "res-repeatable-cleanup-pilot-protocol-v1"
        METER_CLEANUP_REPEATABLE_PILOT_PROTOCOL_REBUILD_SCHEMA_VERSION = (
            "res-repeatable-cleanup-pilot-protocol-rebuild-v1"
        )
        METER_CLEANUP_REPEATABLE_PILOT_PROTOCOL_MODE = "proposal_only"

        @staticmethod
        def read_protocol(policy=None):
            return None

        @staticmethod
        def rebuild_protocol(policy=None):
            raise RuntimeError("meter cleanup repeatable pilot protocol module unavailable")

    _meter_cleanup_repeatable_pilot_protocol_mod = _MissingMeterCleanupRepeatablePilotProtocolModule()
try:
    _meter_cleanup_second_file_pilot_proposal_mod = importlib.import_module(
        "5_connectors.adapter.data_lifecycle.meter_cleanup_second_file_pilot_proposal"
    )
except Exception:
    class _MissingMeterCleanupSecondFilePilotProposalModule:
        METER_CLEANUP_SECOND_FILE_PILOT_PROPOSAL_SCHEMA_VERSION = "res-second-file-cleanup-pilot-proposal-v1"
        METER_CLEANUP_SECOND_FILE_PILOT_PROPOSAL_REBUILD_SCHEMA_VERSION = (
            "res-second-file-cleanup-pilot-proposal-rebuild-v1"
        )
        METER_CLEANUP_SECOND_FILE_PILOT_PROPOSAL_MODE = "proposal_only"

        @staticmethod
        def read_proposal(policy=None):
            return None

        @staticmethod
        def rebuild_proposal(policy=None):
            raise RuntimeError("meter cleanup second-file pilot proposal module unavailable")

    _meter_cleanup_second_file_pilot_proposal_mod = _MissingMeterCleanupSecondFilePilotProposalModule()
try:
    _meter_cleanup_second_file_pilot_approval_readiness_mod = importlib.import_module(
        "5_connectors.adapter.data_lifecycle.meter_cleanup_second_file_pilot_approval_readiness"
    )
except Exception:
    class _MissingMeterCleanupSecondFilePilotApprovalReadinessModule:
        METER_CLEANUP_SECOND_FILE_PILOT_APPROVAL_READINESS_SCHEMA_VERSION = (
            "res-second-file-cleanup-pilot-approval-readiness-v1"
        )
        METER_CLEANUP_SECOND_FILE_PILOT_APPROVAL_READINESS_REBUILD_SCHEMA_VERSION = (
            "res-second-file-cleanup-pilot-approval-readiness-rebuild-v1"
        )
        METER_CLEANUP_SECOND_FILE_PILOT_APPROVAL_READINESS_MODE = "approval_readiness_only"

        @staticmethod
        def read_approval_readiness(policy=None):
            return None

        @staticmethod
        def rebuild_approval_readiness(policy=None):
            raise RuntimeError("meter cleanup second-file pilot approval readiness module unavailable")

    _meter_cleanup_second_file_pilot_approval_readiness_mod = (
        _MissingMeterCleanupSecondFilePilotApprovalReadinessModule()
    )
_meter_backup_export_readiness_mod = importlib.import_module(
    "5_connectors.adapter.data_lifecycle.meter_backup_export_readiness"
)
_meter_backup_export_plan_mod = importlib.import_module(
    "5_connectors.adapter.data_lifecycle.meter_backup_export_plan"
)
_meter_backup_export_package_manifest_mod = importlib.import_module(
    "5_connectors.adapter.data_lifecycle.meter_backup_export_package_manifest"
)
_meter_backup_export_approval_template_mod = importlib.import_module(
    "5_connectors.adapter.data_lifecycle.meter_backup_export_approval_template"
)
_meter_backup_export_execution_gate_mod = importlib.import_module(
    "5_connectors.adapter.data_lifecycle.meter_backup_export_execution_gate"
)
_meter_backup_export_operator_approval_mod = importlib.import_module(
    "5_connectors.adapter.data_lifecycle.meter_backup_export_operator_approval"
)
_meter_backup_export_execution_proposal_mod = importlib.import_module(
    "5_connectors.adapter.data_lifecycle.meter_backup_export_execution_proposal"
)
_meter_backup_export_copy_pilot_mod = importlib.import_module(
    "5_connectors.adapter.data_lifecycle.meter_backup_export_copy_pilot"
)
_meter_backup_export_restore_readback_mod = importlib.import_module(
    "5_connectors.adapter.data_lifecycle.meter_backup_export_restore_readback"
)
_snapshot_cache = importlib.import_module("5_connectors.adapter.application.control_snapshot_cache")


@router.get("/data-lifecycle/status")
async def get_data_lifecycle_status():
    policy = _policy_mod.load_policy()
    return _health.build_health_payload(policy=policy)


@router.post("/data-lifecycle/maintenance/refresh")
async def post_data_lifecycle_manual_refresh():
    policy = _policy_mod.load_policy()
    manager = _maintenance_manager_mod.MaintenanceManager(policy=policy)
    record = manager.run_once("manual_refresh")
    if str(record.get("status") or "").lower() == "success":
        _snapshot_cache.invalidate_agents_control_snapshot()
        return {"schema_version": "dlp-manual-refresh-v1", "record": record}
    raise HTTPException(
        status_code=503,
        detail={
            "schema_version": "dlp-manual-refresh-v1",
            "message": "manual refresh failed",
            "record": record,
        },
    )


@router.get("/data-lifecycle/meter-storage/status")
async def get_data_lifecycle_meter_storage_status():
    return _meter_storage_v2_mod.get_status_payload()


@router.post("/data-lifecycle/meter-storage/rebuild")
async def post_data_lifecycle_meter_storage_rebuild():
    try:
        record, parity = _meter_storage_v2_mod.rebuild_from_legacy()
    except Exception as exc:
        latest_status = _meter_storage_v2_mod.get_status_payload()
        raise HTTPException(
            status_code=503,
            detail={
                "schema_version": _meter_storage_v2_mod.METER_STORAGE_REBUILD_SCHEMA_VERSION,
                "message": "meter storage rebuild failed",
                "error": str(exc),
                "status": latest_status,
            },
        ) from exc
    return {
        "schema_version": _meter_storage_v2_mod.METER_STORAGE_REBUILD_SCHEMA_VERSION,
        "record": record,
        "parity": parity,
    }


@router.get("/data-lifecycle/meter-storage/parity")
async def get_data_lifecycle_meter_storage_parity(fresh: bool = Query(False)):
    if fresh:
        return _meter_storage_v2_mod.build_parity_report()
    return _meter_storage_v2_mod.read_parity_snapshot()


@router.post("/data-lifecycle/meter-storage/parity/rebuild")
async def post_data_lifecycle_meter_storage_parity_rebuild():
    try:
        payload = _meter_storage_v2_mod.parity_with_rebuild()
    except Exception as exc:
        latest_parity = _meter_storage_v2_mod.read_parity_snapshot()
        raise HTTPException(
            status_code=503,
            detail={
                "schema_version": _meter_storage_v2_mod.METER_STORAGE_PARITY_REBUILD_SCHEMA_VERSION,
                "message": "meter storage parity rebuild failed",
                "error": str(exc),
                "parity": latest_parity,
            },
        ) from exc
    return payload


@router.get("/data-lifecycle/meter-storage/cleanup/preview")
async def get_data_lifecycle_meter_storage_cleanup_preview():
    policy = _policy_mod.load_policy()
    preview = _meter_cleanup_preview_mod.read_preview(policy=policy)
    if preview is None:
        return {
            "schema_version": _meter_cleanup_preview_mod.METER_CLEANUP_PREVIEW_SCHEMA_VERSION,
            "status": "missing",
            "mode": _meter_cleanup_preview_mod.METER_CLEANUP_PREVIEW_MODE,
            "cleanup_allowed": False,
        }
    return preview


@router.post("/data-lifecycle/meter-storage/cleanup/preview/rebuild")
async def post_data_lifecycle_meter_storage_cleanup_preview_rebuild():
    policy = _policy_mod.load_policy()
    try:
        record, preview = _meter_cleanup_preview_mod.rebuild_preview(policy=policy)
    except Exception as exc:
        latest_preview = _meter_cleanup_preview_mod.read_preview(policy=policy)
        raise HTTPException(
            status_code=503,
            detail={
                "schema_version": _meter_cleanup_preview_mod.METER_CLEANUP_PREVIEW_REBUILD_SCHEMA_VERSION,
                "message": "meter cleanup preview rebuild failed",
                "error": str(exc),
                "preview": latest_preview,
            },
        ) from exc
    return {
        "schema_version": _meter_cleanup_preview_mod.METER_CLEANUP_PREVIEW_REBUILD_SCHEMA_VERSION,
        "record": record,
        "preview": preview,
    }


@router.get("/data-lifecycle/meter-storage/cleanup/gate")
async def get_data_lifecycle_meter_storage_cleanup_gate():
    policy = _policy_mod.load_policy()
    gate = _meter_cleanup_execution_gate_mod.read_gate(policy=policy)
    if gate is None:
        return {
            "schema_version": _meter_cleanup_execution_gate_mod.METER_CLEANUP_EXECUTION_GATE_SCHEMA_VERSION,
            "status": "missing",
            "mode": _meter_cleanup_execution_gate_mod.METER_CLEANUP_EXECUTION_GATE_MODE,
            "cleanup_gate_status": "blocked",
            "cleanup_allowed": False,
            "rollback_required": True,
        }
    return gate


@router.post("/data-lifecycle/meter-storage/cleanup/gate/rebuild")
async def post_data_lifecycle_meter_storage_cleanup_gate_rebuild():
    policy = _policy_mod.load_policy()
    try:
        record, gate = _meter_cleanup_execution_gate_mod.rebuild_gate(policy=policy)
    except Exception as exc:
        latest = _meter_cleanup_execution_gate_mod.read_gate(policy=policy)
        raise HTTPException(
            status_code=503,
            detail={
                "schema_version": _meter_cleanup_execution_gate_mod.METER_CLEANUP_EXECUTION_GATE_REBUILD_SCHEMA_VERSION,
                "message": "meter cleanup execution gate rebuild failed",
                "error": str(exc),
                "cleanup_gate": latest,
            },
        ) from exc
    return {
        "schema_version": _meter_cleanup_execution_gate_mod.METER_CLEANUP_EXECUTION_GATE_REBUILD_SCHEMA_VERSION,
        "record": record,
        "cleanup_gate": gate,
    }


@router.get("/data-lifecycle/meter-storage/cleanup/transaction-preview")
async def get_data_lifecycle_meter_storage_cleanup_transaction_preview():
    policy = _policy_mod.load_policy()
    preview = _meter_cleanup_transaction_preview_mod.read_preview(policy=policy)
    if preview is None:
        return {
            "schema_version": _meter_cleanup_transaction_preview_mod.METER_CLEANUP_TRANSACTION_PREVIEW_SCHEMA_VERSION,
            "status": "missing",
            "mode": _meter_cleanup_transaction_preview_mod.METER_CLEANUP_TRANSACTION_PREVIEW_MODE,
            "execution_allowed": False,
        }
    return preview


@router.post("/data-lifecycle/meter-storage/cleanup/transaction-preview/rebuild")
async def post_data_lifecycle_meter_storage_cleanup_transaction_preview_rebuild():
    policy = _policy_mod.load_policy()
    try:
        record, preview = _meter_cleanup_transaction_preview_mod.rebuild_preview(policy=policy)
    except Exception as exc:
        latest = _meter_cleanup_transaction_preview_mod.read_preview(policy=policy)
        raise HTTPException(
            status_code=503,
            detail={
                "schema_version": _meter_cleanup_transaction_preview_mod.METER_CLEANUP_TRANSACTION_PREVIEW_REBUILD_SCHEMA_VERSION,
                "message": "meter cleanup transaction preview rebuild failed",
                "error": str(exc),
                "transaction_preview": latest,
            },
        ) from exc
    return {
        "schema_version": _meter_cleanup_transaction_preview_mod.METER_CLEANUP_TRANSACTION_PREVIEW_REBUILD_SCHEMA_VERSION,
        "record": record,
        "transaction_preview": preview,
    }


@router.get("/data-lifecycle/meter-storage/cleanup/rollback-drill")
async def get_data_lifecycle_meter_storage_cleanup_rollback_drill():
    policy = _policy_mod.load_policy()
    report = _meter_cleanup_rollback_drill_mod.read_rollback_drill_report(policy=policy)
    if report is None:
        return {
            "schema_version": _meter_cleanup_rollback_drill_mod.METER_CLEANUP_ROLLBACK_DRILL_SCHEMA_VERSION,
            "status": "missing",
            "mode": _meter_cleanup_rollback_drill_mod.METER_CLEANUP_ROLLBACK_DRILL_MODE,
            "staging_restore_readable": False,
            "checksum_match": False,
            "source_retained": True,
            "production_restore_started": False,
            "cleanup_started": False,
        }
    return report


@router.post("/data-lifecycle/meter-storage/cleanup/rollback-drill/rebuild")
async def post_data_lifecycle_meter_storage_cleanup_rollback_drill_rebuild():
    policy = _policy_mod.load_policy()
    try:
        record, report = _meter_cleanup_rollback_drill_mod.rebuild_rollback_drill_report(policy=policy)
    except Exception as exc:
        latest = _meter_cleanup_rollback_drill_mod.read_rollback_drill_report(policy=policy)
        raise HTTPException(
            status_code=503,
            detail={
                "schema_version": _meter_cleanup_rollback_drill_mod.METER_CLEANUP_ROLLBACK_DRILL_REBUILD_SCHEMA_VERSION,
                "message": "meter cleanup rollback drill rebuild failed",
                "error": str(exc),
                "rollback_drill": latest,
            },
        ) from exc
    return {
        "schema_version": _meter_cleanup_rollback_drill_mod.METER_CLEANUP_ROLLBACK_DRILL_REBUILD_SCHEMA_VERSION,
        "record": record,
        "rollback_drill": report,
    }


@router.get("/data-lifecycle/meter-storage/cleanup/pilot/latest")
async def get_data_lifecycle_meter_storage_cleanup_pilot_latest():
    policy = _policy_mod.load_policy()
    pilot = _meter_cleanup_pilot_mod.read_latest_pilot(policy=policy)
    if pilot is None:
        return {
            "schema_version": _meter_cleanup_pilot_mod.METER_CLEANUP_PILOT_SCHEMA_VERSION,
            "status": "missing",
            "mode": _meter_cleanup_pilot_mod.METER_CLEANUP_PILOT_MODE,
            "source_move_executed": False,
            "delete_executed": False,
            "compress_executed": False,
            "truncate_executed": False,
            "batch_cleanup_executed": False,
        }
    return pilot


@router.post("/data-lifecycle/meter-storage/cleanup/pilot/quarantine-one")
async def post_data_lifecycle_meter_storage_cleanup_pilot_quarantine_one():
    policy = _policy_mod.load_policy()
    try:
        record, pilot = _meter_cleanup_pilot_mod.execute_single_file_quarantine(policy=policy)
    except Exception as exc:
        latest = _meter_cleanup_pilot_mod.read_latest_pilot(policy=policy)
        raise HTTPException(
            status_code=503,
            detail={
                "schema_version": _meter_cleanup_pilot_mod.METER_CLEANUP_PILOT_SCHEMA_VERSION,
                "message": "meter cleanup pilot quarantine-one failed",
                "error": str(exc),
                "pilot": latest,
            },
        ) from exc
    return {
        "schema_version": _meter_cleanup_pilot_mod.METER_CLEANUP_PILOT_SCHEMA_VERSION,
        "record": record,
        "pilot": pilot,
    }


@router.get("/data-lifecycle/meter-storage/cleanup/stability-window")
async def get_data_lifecycle_meter_storage_cleanup_stability_window():
    policy = _policy_mod.load_policy()
    report = _meter_cleanup_stability_window_mod.read_stability_window_report(policy=policy)
    if report is None:
        return {
            "schema_version": _meter_cleanup_stability_window_mod.METER_CLEANUP_STABILITY_WINDOW_SCHEMA_VERSION,
            "status": "missing",
            "mode": _meter_cleanup_stability_window_mod.METER_CLEANUP_STABILITY_WINDOW_MODE,
            "observed_pilot_status": "missing",
            "cleanup_scope_expansion_started": False,
        }
    return report


@router.post("/data-lifecycle/meter-storage/cleanup/stability-window/rebuild")
async def post_data_lifecycle_meter_storage_cleanup_stability_window_rebuild():
    policy = _policy_mod.load_policy()
    try:
        record, report = await asyncio.to_thread(
            _meter_cleanup_stability_window_mod.rebuild_stability_window_report,
            policy=policy,
        )
    except Exception as exc:
        latest = _meter_cleanup_stability_window_mod.read_stability_window_report(policy=policy)
        raise HTTPException(
            status_code=503,
            detail={
                "schema_version": _meter_cleanup_stability_window_mod.METER_CLEANUP_STABILITY_WINDOW_REBUILD_SCHEMA_VERSION,
                "message": "meter cleanup stability-window rebuild failed",
                "error": str(exc),
                "stability_window": latest,
            },
        ) from exc
    return {
        "schema_version": _meter_cleanup_stability_window_mod.METER_CLEANUP_STABILITY_WINDOW_REBUILD_SCHEMA_VERSION,
        "record": record,
        "stability_window": report,
    }


@router.get("/data-lifecycle/meter-storage/cleanup/scaleup-readiness")
async def get_data_lifecycle_meter_storage_cleanup_scaleup_readiness():
    policy = _policy_mod.load_policy()
    report = _meter_cleanup_scaleup_readiness_mod.read_readiness_report(policy=policy)
    if report is None:
        return {
            "schema_version": _meter_cleanup_scaleup_readiness_mod.METER_CLEANUP_SCALEUP_READINESS_SCHEMA_VERSION,
            "status": "missing",
            "mode": _meter_cleanup_scaleup_readiness_mod.METER_CLEANUP_SCALEUP_READINESS_MODE,
            "ready_for_scaleup": False,
            "cleanup_scope_expansion_started": False,
        }
    return report


@router.post("/data-lifecycle/meter-storage/cleanup/scaleup-readiness/rebuild")
async def post_data_lifecycle_meter_storage_cleanup_scaleup_readiness_rebuild():
    policy = _policy_mod.load_policy()
    try:
        record, report = await asyncio.to_thread(
            _meter_cleanup_scaleup_readiness_mod.rebuild_readiness_report,
            policy=policy,
        )
    except Exception as exc:
        latest = _meter_cleanup_scaleup_readiness_mod.read_readiness_report(policy=policy)
        raise HTTPException(
            status_code=503,
            detail={
                "schema_version": _meter_cleanup_scaleup_readiness_mod.METER_CLEANUP_SCALEUP_READINESS_REBUILD_SCHEMA_VERSION,
                "message": "meter cleanup scaleup-readiness rebuild failed",
                "error": str(exc),
                "scaleup_readiness": latest,
            },
        ) from exc
    return {
        "schema_version": _meter_cleanup_scaleup_readiness_mod.METER_CLEANUP_SCALEUP_READINESS_REBUILD_SCHEMA_VERSION,
        "record": record,
        "scaleup_readiness": report,
    }


@router.get("/data-lifecycle/meter-storage/cleanup/repeatable-pilot-protocol")
async def get_data_lifecycle_meter_storage_cleanup_repeatable_pilot_protocol():
    policy = _policy_mod.load_policy()
    report = _meter_cleanup_repeatable_pilot_protocol_mod.read_protocol(policy=policy)
    if report is None:
        return {
            "schema_version": _meter_cleanup_repeatable_pilot_protocol_mod.METER_CLEANUP_REPEATABLE_PILOT_PROTOCOL_SCHEMA_VERSION,
            "status": "missing",
            "mode": _meter_cleanup_repeatable_pilot_protocol_mod.METER_CLEANUP_REPEATABLE_PILOT_PROTOCOL_MODE,
            "second_file_pilot_allowed": False,
            "execution_started": False,
            "cleanup_scope_expansion_started": False,
        }
    return report


@router.post("/data-lifecycle/meter-storage/cleanup/repeatable-pilot-protocol/rebuild")
async def post_data_lifecycle_meter_storage_cleanup_repeatable_pilot_protocol_rebuild():
    policy = _policy_mod.load_policy()
    try:
        record, report = await asyncio.to_thread(
            _meter_cleanup_repeatable_pilot_protocol_mod.rebuild_protocol,
            policy=policy,
        )
    except Exception as exc:
        latest = _meter_cleanup_repeatable_pilot_protocol_mod.read_protocol(policy=policy)
        raise HTTPException(
            status_code=503,
            detail={
                "schema_version": _meter_cleanup_repeatable_pilot_protocol_mod.METER_CLEANUP_REPEATABLE_PILOT_PROTOCOL_REBUILD_SCHEMA_VERSION,
                "message": "meter cleanup repeatable pilot protocol rebuild failed",
                "error": str(exc),
                "repeatable_pilot_protocol": latest,
            },
        ) from exc
    return {
        "schema_version": _meter_cleanup_repeatable_pilot_protocol_mod.METER_CLEANUP_REPEATABLE_PILOT_PROTOCOL_REBUILD_SCHEMA_VERSION,
        "record": record,
        "repeatable_pilot_protocol": report,
    }


@router.get("/data-lifecycle/meter-storage/cleanup/second-file-pilot/proposal")
async def get_data_lifecycle_meter_storage_cleanup_second_file_pilot_proposal():
    policy = _policy_mod.load_policy()
    report = _meter_cleanup_second_file_pilot_proposal_mod.read_proposal(policy=policy)
    if report is None:
        return {
            "schema_version": _meter_cleanup_second_file_pilot_proposal_mod.METER_CLEANUP_SECOND_FILE_PILOT_PROPOSAL_SCHEMA_VERSION,
            "status": "missing",
            "mode": _meter_cleanup_second_file_pilot_proposal_mod.METER_CLEANUP_SECOND_FILE_PILOT_PROPOSAL_MODE,
            "second_file_pilot_allowed": False,
            "execution_started": False,
            "cleanup_scope_expansion_started": False,
        }
    return report


@router.post("/data-lifecycle/meter-storage/cleanup/second-file-pilot/proposal/rebuild")
async def post_data_lifecycle_meter_storage_cleanup_second_file_pilot_proposal_rebuild():
    policy = _policy_mod.load_policy()
    try:
        record, report = await asyncio.to_thread(
            _meter_cleanup_second_file_pilot_proposal_mod.rebuild_proposal,
            policy=policy,
        )
    except Exception as exc:
        latest = _meter_cleanup_second_file_pilot_proposal_mod.read_proposal(policy=policy)
        raise HTTPException(
            status_code=503,
            detail={
                "schema_version": _meter_cleanup_second_file_pilot_proposal_mod.METER_CLEANUP_SECOND_FILE_PILOT_PROPOSAL_REBUILD_SCHEMA_VERSION,
                "message": "meter cleanup second-file pilot proposal rebuild failed",
                "error": str(exc),
                "second_file_pilot_proposal": latest,
            },
        ) from exc
    return {
        "schema_version": _meter_cleanup_second_file_pilot_proposal_mod.METER_CLEANUP_SECOND_FILE_PILOT_PROPOSAL_REBUILD_SCHEMA_VERSION,
        "record": record,
        "second_file_pilot_proposal": report,
    }


@router.get("/data-lifecycle/meter-storage/cleanup/second-file-pilot/approval-readiness")
async def get_data_lifecycle_meter_storage_cleanup_second_file_pilot_approval_readiness():
    policy = _policy_mod.load_policy()
    report = _meter_cleanup_second_file_pilot_approval_readiness_mod.read_approval_readiness(policy=policy)
    if report is None:
        return {
            "schema_version": _meter_cleanup_second_file_pilot_approval_readiness_mod.METER_CLEANUP_SECOND_FILE_PILOT_APPROVAL_READINESS_SCHEMA_VERSION,
            "status": "missing",
            "mode": _meter_cleanup_second_file_pilot_approval_readiness_mod.METER_CLEANUP_SECOND_FILE_PILOT_APPROVAL_READINESS_MODE,
            "required_operator_approval": True,
            "operator_approval_written": False,
            "second_file_pilot_allowed": False,
            "execution_started": False,
            "cleanup_scope_expansion_started": False,
        }
    return report


@router.post("/data-lifecycle/meter-storage/cleanup/second-file-pilot/approval-readiness/rebuild")
async def post_data_lifecycle_meter_storage_cleanup_second_file_pilot_approval_readiness_rebuild():
    policy = _policy_mod.load_policy()
    try:
        record, report = await asyncio.to_thread(
            _meter_cleanup_second_file_pilot_approval_readiness_mod.rebuild_approval_readiness,
            policy=policy,
        )
    except Exception as exc:
        latest = _meter_cleanup_second_file_pilot_approval_readiness_mod.read_approval_readiness(policy=policy)
        raise HTTPException(
            status_code=503,
            detail={
                "schema_version": _meter_cleanup_second_file_pilot_approval_readiness_mod.METER_CLEANUP_SECOND_FILE_PILOT_APPROVAL_READINESS_REBUILD_SCHEMA_VERSION,
                "message": "meter cleanup second-file pilot approval readiness rebuild failed",
                "error": str(exc),
                "second_file_pilot_approval_readiness": latest,
            },
        ) from exc
    return {
        "schema_version": _meter_cleanup_second_file_pilot_approval_readiness_mod.METER_CLEANUP_SECOND_FILE_PILOT_APPROVAL_READINESS_REBUILD_SCHEMA_VERSION,
        "record": record,
        "second_file_pilot_approval_readiness": report,
    }


@router.get("/data-lifecycle/meter-storage/backup-export/readiness")
async def get_data_lifecycle_meter_storage_backup_export_readiness():
    policy = _policy_mod.load_policy()
    readiness = _meter_backup_export_readiness_mod.read_readiness(policy=policy)
    if readiness is None:
        return {
            "schema_version": _meter_backup_export_readiness_mod.METER_BACKUP_EXPORT_READINESS_SCHEMA_VERSION,
            "status": "missing",
            "mode": _meter_backup_export_readiness_mod.METER_BACKUP_EXPORT_READINESS_MODE,
            "backup_export_allowed": False,
            "cleanup_allowed": False,
        }
    return readiness


@router.post("/data-lifecycle/meter-storage/backup-export/readiness/rebuild")
async def post_data_lifecycle_meter_storage_backup_export_readiness_rebuild():
    policy = _policy_mod.load_policy()
    try:
        record, readiness = _meter_backup_export_readiness_mod.rebuild_readiness(policy=policy)
    except Exception as exc:
        latest = _meter_backup_export_readiness_mod.read_readiness(policy=policy)
        raise HTTPException(
            status_code=503,
            detail={
                "schema_version": _meter_backup_export_readiness_mod.METER_BACKUP_EXPORT_READINESS_REBUILD_SCHEMA_VERSION,
                "message": "meter backup export readiness rebuild failed",
                "error": str(exc),
                "readiness": latest,
            },
        ) from exc
    return {
        "schema_version": _meter_backup_export_readiness_mod.METER_BACKUP_EXPORT_READINESS_REBUILD_SCHEMA_VERSION,
        "record": record,
        "readiness": readiness,
    }


@router.get("/data-lifecycle/meter-storage/backup-export/plan")
async def get_data_lifecycle_meter_storage_backup_export_plan():
    policy = _policy_mod.load_policy()
    plan = _meter_backup_export_plan_mod.read_plan(policy=policy)
    if plan is None:
        return {
            "schema_version": _meter_backup_export_plan_mod.METER_BACKUP_EXPORT_PLAN_SCHEMA_VERSION,
            "status": "missing",
            "mode": _meter_backup_export_plan_mod.METER_BACKUP_EXPORT_PLAN_MODE,
            "backup_export_allowed": False,
            "cleanup_allowed": False,
            "execution_allowed": False,
        }
    return plan


@router.post("/data-lifecycle/meter-storage/backup-export/plan/rebuild")
async def post_data_lifecycle_meter_storage_backup_export_plan_rebuild():
    policy = _policy_mod.load_policy()
    try:
        record, plan = _meter_backup_export_plan_mod.rebuild_plan(policy=policy)
    except Exception as exc:
        latest = _meter_backup_export_plan_mod.read_plan(policy=policy)
        raise HTTPException(
            status_code=503,
            detail={
                "schema_version": _meter_backup_export_plan_mod.METER_BACKUP_EXPORT_PLAN_REBUILD_SCHEMA_VERSION,
                "message": "meter backup export plan rebuild failed",
                "error": str(exc),
                "plan": latest,
            },
        ) from exc
    return {
        "schema_version": _meter_backup_export_plan_mod.METER_BACKUP_EXPORT_PLAN_REBUILD_SCHEMA_VERSION,
        "record": record,
        "plan": plan,
    }


@router.get("/data-lifecycle/meter-storage/backup-export/package-manifest")
async def get_data_lifecycle_meter_storage_backup_export_package_manifest():
    policy = _policy_mod.load_policy()
    manifest = _meter_backup_export_package_manifest_mod.read_package_manifest(policy=policy)
    if manifest is None:
        return {
            "schema_version": _meter_backup_export_package_manifest_mod.METER_BACKUP_EXPORT_PACKAGE_MANIFEST_SCHEMA_VERSION,
            "status": "missing",
            "mode": _meter_backup_export_package_manifest_mod.METER_BACKUP_EXPORT_PACKAGE_MANIFEST_MODE,
            "backup_export_allowed": False,
            "cleanup_allowed": False,
            "execution_allowed": False,
        }
    return manifest


@router.post("/data-lifecycle/meter-storage/backup-export/package-manifest/rebuild")
async def post_data_lifecycle_meter_storage_backup_export_package_manifest_rebuild():
    policy = _policy_mod.load_policy()
    try:
        record, manifest = _meter_backup_export_package_manifest_mod.rebuild_package_manifest(policy=policy)
    except Exception as exc:
        latest = _meter_backup_export_package_manifest_mod.read_package_manifest(policy=policy)
        raise HTTPException(
            status_code=503,
            detail={
                "schema_version": _meter_backup_export_package_manifest_mod.METER_BACKUP_EXPORT_PACKAGE_MANIFEST_REBUILD_SCHEMA_VERSION,
                "message": "meter backup export package manifest rebuild failed",
                "error": str(exc),
                "package_manifest": latest,
            },
        ) from exc
    return {
        "schema_version": _meter_backup_export_package_manifest_mod.METER_BACKUP_EXPORT_PACKAGE_MANIFEST_REBUILD_SCHEMA_VERSION,
        "record": record,
        "package_manifest": manifest,
    }


@router.get("/data-lifecycle/meter-storage/backup-export/approval-template")
async def get_data_lifecycle_meter_storage_backup_export_approval_template():
    policy = _policy_mod.load_policy()
    template = _meter_backup_export_approval_template_mod.read_approval_template(policy=policy)
    if template is None:
        return {
            "schema_version": _meter_backup_export_approval_template_mod.METER_BACKUP_EXPORT_APPROVAL_TEMPLATE_SCHEMA_VERSION,
            "status": "missing",
            "mode": _meter_backup_export_approval_template_mod.METER_BACKUP_EXPORT_APPROVAL_TEMPLATE_MODE,
            "approval_valid": False,
            "backup_export_allowed": False,
            "cleanup_allowed": False,
            "execution_allowed": False,
        }
    return template


@router.post("/data-lifecycle/meter-storage/backup-export/approval-template/rebuild")
async def post_data_lifecycle_meter_storage_backup_export_approval_template_rebuild():
    policy = _policy_mod.load_policy()
    try:
        record, template = _meter_backup_export_approval_template_mod.rebuild_approval_template(policy=policy)
    except Exception as exc:
        latest = _meter_backup_export_approval_template_mod.read_approval_template(policy=policy)
        raise HTTPException(
            status_code=503,
            detail={
                "schema_version": _meter_backup_export_approval_template_mod.METER_BACKUP_EXPORT_APPROVAL_TEMPLATE_REBUILD_SCHEMA_VERSION,
                "message": "meter backup export approval template rebuild failed",
                "error": str(exc),
                "approval_template": latest,
            },
        ) from exc
    return {
        "schema_version": _meter_backup_export_approval_template_mod.METER_BACKUP_EXPORT_APPROVAL_TEMPLATE_REBUILD_SCHEMA_VERSION,
        "record": record,
        "approval_template": template,
    }


@router.get("/data-lifecycle/meter-storage/backup-export/execution/gate")
async def get_data_lifecycle_meter_storage_backup_export_execution_gate():
    policy = _policy_mod.load_policy()
    gate = _meter_backup_export_execution_gate_mod.read_gate(policy=policy)
    if gate is None:
        return {
            "schema_version": _meter_backup_export_execution_gate_mod.METER_BACKUP_EXPORT_EXECUTION_GATE_SCHEMA_VERSION,
            "status": "missing",
            "mode": _meter_backup_export_execution_gate_mod.METER_BACKUP_EXPORT_EXECUTION_GATE_MODE,
            "allowed": False,
            "backup_export_execution_started": False,
            "cleanup_execution_started": False,
        }
    return gate


@router.post("/data-lifecycle/meter-storage/backup-export/execution/gate/rebuild")
async def post_data_lifecycle_meter_storage_backup_export_execution_gate_rebuild():
    policy = _policy_mod.load_policy()
    try:
        record, gate = _meter_backup_export_execution_gate_mod.rebuild_gate(policy=policy)
    except Exception as exc:
        latest = _meter_backup_export_execution_gate_mod.read_gate(policy=policy)
        raise HTTPException(
            status_code=503,
            detail={
                "schema_version": _meter_backup_export_execution_gate_mod.METER_BACKUP_EXPORT_EXECUTION_GATE_REBUILD_SCHEMA_VERSION,
                "message": "meter backup export execution gate rebuild failed",
                "error": str(exc),
                "execution_gate": latest,
            },
        ) from exc
    return {
        "schema_version": _meter_backup_export_execution_gate_mod.METER_BACKUP_EXPORT_EXECUTION_GATE_REBUILD_SCHEMA_VERSION,
        "record": record,
        "execution_gate": gate,
    }


@router.get("/data-lifecycle/meter-storage/backup-export/operator-approval")
async def get_data_lifecycle_meter_storage_backup_export_operator_approval():
    policy = _policy_mod.load_policy()
    approval = _meter_backup_export_operator_approval_mod.read_operator_approval(policy=policy)
    if approval is None:
        return {
            "schema_version": _meter_backup_export_operator_approval_mod.METER_BACKUP_EXPORT_OPERATOR_APPROVAL_SCHEMA_VERSION,
            "status": "missing",
        }
    return approval


@router.get("/data-lifecycle/meter-storage/backup-export/execution/proposal")
async def get_data_lifecycle_meter_storage_backup_export_execution_proposal():
    policy = _policy_mod.load_policy()
    proposal = _meter_backup_export_execution_proposal_mod.read_execution_proposal(policy=policy)
    if proposal is None:
        return {
            "schema_version": _meter_backup_export_execution_proposal_mod.METER_BACKUP_EXPORT_EXECUTION_PROPOSAL_SCHEMA_VERSION,
            "status": "missing",
            "mode": _meter_backup_export_execution_proposal_mod.METER_BACKUP_EXPORT_EXECUTION_PROPOSAL_MODE,
            "proposal_status": "blocked",
            "execution_started": False,
            "cleanup_started": False,
            "operator_decision_required": True,
        }
    return proposal


@router.post("/data-lifecycle/meter-storage/backup-export/execution/proposal/rebuild")
async def post_data_lifecycle_meter_storage_backup_export_execution_proposal_rebuild():
    policy = _policy_mod.load_policy()
    try:
        record, proposal = _meter_backup_export_execution_proposal_mod.rebuild_execution_proposal(policy=policy)
    except Exception as exc:
        latest = _meter_backup_export_execution_proposal_mod.read_execution_proposal(policy=policy)
        raise HTTPException(
            status_code=503,
            detail={
                "schema_version": _meter_backup_export_execution_proposal_mod.METER_BACKUP_EXPORT_EXECUTION_PROPOSAL_REBUILD_SCHEMA_VERSION,
                "message": "meter backup export execution proposal rebuild failed",
                "error": str(exc),
                "execution_proposal": latest,
            },
        ) from exc
    return {
        "schema_version": _meter_backup_export_execution_proposal_mod.METER_BACKUP_EXPORT_EXECUTION_PROPOSAL_REBUILD_SCHEMA_VERSION,
        "record": record,
        "execution_proposal": proposal,
    }


@router.post("/data-lifecycle/meter-storage/backup-export/copy-pilot/run-one")
async def post_data_lifecycle_meter_storage_backup_export_copy_pilot_run_one():
    policy = _policy_mod.load_policy()
    try:
        record, pilot = _meter_backup_export_copy_pilot_mod.run_one_copy_pilot(policy=policy)
    except Exception as exc:
        latest = _meter_backup_export_copy_pilot_mod.read_latest_copy_pilot(policy=policy)
        raise HTTPException(
            status_code=503,
            detail={
                "schema_version": _meter_backup_export_copy_pilot_mod.METER_BACKUP_EXPORT_COPY_PILOT_SCHEMA_VERSION,
                "message": "meter backup export copy pilot run-one failed",
                "error": str(exc),
                "copy_pilot": latest,
            },
        ) from exc
    return {
        "schema_version": _meter_backup_export_copy_pilot_mod.METER_BACKUP_EXPORT_COPY_PILOT_SCHEMA_VERSION,
        "record": record,
        "copy_pilot": pilot,
    }


@router.get("/data-lifecycle/meter-storage/backup-export/copy-pilot/latest")
async def get_data_lifecycle_meter_storage_backup_export_copy_pilot_latest():
    policy = _policy_mod.load_policy()
    pilot = _meter_backup_export_copy_pilot_mod.read_latest_copy_pilot(policy=policy)
    if pilot is None:
        return {
            "schema_version": _meter_backup_export_copy_pilot_mod.METER_BACKUP_EXPORT_COPY_PILOT_SCHEMA_VERSION,
            "status": "missing",
            "mode": _meter_backup_export_copy_pilot_mod.METER_BACKUP_EXPORT_COPY_PILOT_MODE,
            "source_retained": True,
            "checksum_match": False,
            "cleanup_started": False,
            "read_path_unchanged": True,
        }
    return pilot


@router.get("/data-lifecycle/meter-storage/backup-export/restore-readback")
async def get_data_lifecycle_meter_storage_backup_export_restore_readback():
    policy = _policy_mod.load_policy()
    report = _meter_backup_export_restore_readback_mod.read_restore_readback_report(policy=policy)
    if report is None:
        return {
            "schema_version": _meter_backup_export_restore_readback_mod.METER_BACKUP_EXPORT_RESTORE_READBACK_SCHEMA_VERSION,
            "status": "missing",
            "mode": _meter_backup_export_restore_readback_mod.METER_BACKUP_EXPORT_RESTORE_READBACK_MODE,
            "source_retained": True,
            "backup_copy_readable": False,
            "checksum_match": False,
            "production_restore_started": False,
            "cleanup_started": False,
        }
    return report


@router.post("/data-lifecycle/meter-storage/backup-export/restore-readback/rebuild")
async def post_data_lifecycle_meter_storage_backup_export_restore_readback_rebuild():
    policy = _policy_mod.load_policy()
    try:
        record, report = _meter_backup_export_restore_readback_mod.rebuild_restore_readback_report(policy=policy)
    except Exception as exc:
        latest = _meter_backup_export_restore_readback_mod.read_restore_readback_report(policy=policy)
        raise HTTPException(
            status_code=503,
            detail={
                "schema_version": _meter_backup_export_restore_readback_mod.METER_BACKUP_EXPORT_RESTORE_READBACK_REBUILD_SCHEMA_VERSION,
                "message": "meter backup export restore/readback rebuild failed",
                "error": str(exc),
                "restore_readback": latest,
            },
        ) from exc
    return {
        "schema_version": _meter_backup_export_restore_readback_mod.METER_BACKUP_EXPORT_RESTORE_READBACK_REBUILD_SCHEMA_VERSION,
        "record": record,
        "restore_readback": report,
    }


@router.get("/data-lifecycle/retention/manifest")
async def get_data_lifecycle_retention_manifest():
    policy = _policy_mod.load_policy()
    manifest = _retention_mod.read_manifest(policy=policy)
    if manifest is None:
        return {"schema_version": _retention_mod.RETENTION_MANIFEST_SCHEMA_VERSION, "status": "missing"}
    return manifest


@router.post("/data-lifecycle/retention/manifest/rebuild")
async def post_data_lifecycle_retention_manifest_rebuild():
    policy = _policy_mod.load_policy()
    try:
        record, manifest = _retention_mod.rebuild_manifest(policy=policy)
    except Exception as exc:
        latest_manifest = _retention_mod.read_manifest(policy=policy)
        raise HTTPException(
            status_code=503,
            detail={
                "schema_version": _retention_mod.RETENTION_REBUILD_SCHEMA_VERSION,
                "message": "retention manifest rebuild failed",
                "error": str(exc),
                "manifest": latest_manifest,
            },
        ) from exc
    return {
        "schema_version": _retention_mod.RETENTION_REBUILD_SCHEMA_VERSION,
        "record": record,
        "manifest": manifest,
    }


@router.get("/data-lifecycle/raw-evidence/segments")
async def get_data_lifecycle_raw_evidence_segments():
    policy = _policy_mod.load_policy()
    manifest = _raw_evidence_segments_mod.read_manifest(policy=policy)
    if manifest is None:
        return {
            "schema_version": _raw_evidence_segments_mod.RAW_EVIDENCE_SEGMENTS_MANIFEST_SCHEMA_VERSION,
            "status": "missing",
        }
    return manifest


@router.post("/data-lifecycle/raw-evidence/segments/manifest/rebuild")
async def post_data_lifecycle_raw_evidence_segments_manifest_rebuild():
    policy = _policy_mod.load_policy()
    try:
        record, manifest = _raw_evidence_segments_mod.rebuild_manifest(policy=policy)
    except Exception as exc:
        latest_manifest = _raw_evidence_segments_mod.read_manifest(policy=policy)
        raise HTTPException(
            status_code=503,
            detail={
                "schema_version": _raw_evidence_segments_mod.RAW_EVIDENCE_SEGMENTS_REBUILD_SCHEMA_VERSION,
                "message": "raw evidence segments manifest rebuild failed",
                "error": str(exc),
                "manifest": latest_manifest,
            },
        ) from exc
    return {
        "schema_version": _raw_evidence_segments_mod.RAW_EVIDENCE_SEGMENTS_REBUILD_SCHEMA_VERSION,
        "record": record,
        "manifest": manifest,
    }


@router.get("/data-lifecycle/traceability/report")
async def get_data_lifecycle_traceability_report():
    policy = _policy_mod.load_policy()
    report = _traceability_mod.read_report(policy=policy)
    if report is None:
        return {"schema_version": _traceability_mod.TRACEABILITY_REPORT_SCHEMA_VERSION, "status": "missing"}
    return report


@router.post("/data-lifecycle/traceability/report/rebuild")
async def post_data_lifecycle_traceability_report_rebuild():
    policy = _policy_mod.load_policy()
    try:
        record, report = _traceability_mod.rebuild_report(policy=policy)
    except Exception as exc:
        latest_report = _traceability_mod.read_report(policy=policy)
        raise HTTPException(
            status_code=503,
            detail={
                "schema_version": _traceability_mod.TRACEABILITY_REBUILD_SCHEMA_VERSION,
                "message": "traceability report rebuild failed",
                "error": str(exc),
                "report": latest_report,
            },
        ) from exc
    return {
        "schema_version": _traceability_mod.TRACEABILITY_REBUILD_SCHEMA_VERSION,
        "record": record,
        "report": report,
    }


@router.get("/data-lifecycle/archive/plan")
async def get_data_lifecycle_archive_plan():
    policy = _policy_mod.load_policy()
    plan = _archive_plan_mod.read_plan(policy=policy)
    if plan is None:
        return {"schema_version": _archive_plan_mod.ARCHIVE_CANDIDATE_PLAN_SCHEMA_VERSION, "status": "missing"}
    return plan


@router.post("/data-lifecycle/archive/plan/rebuild")
async def post_data_lifecycle_archive_plan_rebuild():
    policy = _policy_mod.load_policy()
    try:
        record, plan = _archive_plan_mod.rebuild_plan(policy=policy)
    except Exception as exc:
        latest_plan = _archive_plan_mod.read_plan(policy=policy)
        raise HTTPException(
            status_code=503,
            detail={
                "schema_version": _archive_plan_mod.ARCHIVE_CANDIDATE_PLAN_REBUILD_SCHEMA_VERSION,
                "message": "archive candidate plan rebuild failed",
                "error": str(exc),
                "plan": latest_plan,
            },
        ) from exc
    return {
        "schema_version": _archive_plan_mod.ARCHIVE_CANDIDATE_PLAN_REBUILD_SCHEMA_VERSION,
        "record": record,
        "plan": plan,
    }


@router.get("/data-lifecycle/archive/transaction/preview")
async def get_data_lifecycle_archive_transaction_preview():
    policy = _policy_mod.load_policy()
    preview = _archive_txn_mod.read_preview(policy=policy)
    if preview is None:
        return {"schema_version": _archive_txn_mod.ARCHIVE_TRANSACTION_PREVIEW_SCHEMA_VERSION, "status": "missing"}
    return preview


@router.post("/data-lifecycle/archive/transaction/preview/rebuild")
async def post_data_lifecycle_archive_transaction_preview_rebuild():
    policy = _policy_mod.load_policy()
    try:
        record, preview = _archive_txn_mod.rebuild_preview(policy=policy)
    except Exception as exc:
        latest_preview = _archive_txn_mod.read_preview(policy=policy)
        raise HTTPException(
            status_code=503,
            detail={
                "schema_version": _archive_txn_mod.ARCHIVE_TRANSACTION_PREVIEW_REBUILD_SCHEMA_VERSION,
                "message": "archive transaction preview rebuild failed",
                "error": str(exc),
                "preview": latest_preview,
            },
        ) from exc
    return {
        "schema_version": _archive_txn_mod.ARCHIVE_TRANSACTION_PREVIEW_REBUILD_SCHEMA_VERSION,
        "record": record,
        "preview": preview,
    }


@router.get("/data-lifecycle/archive/restore/readiness")
async def get_data_lifecycle_archive_restore_readiness():
    policy = _policy_mod.load_policy()
    readiness = _archive_restore_mod.read_readiness_report(policy=policy)
    if readiness is None:
        return {"schema_version": _archive_restore_mod.ARCHIVE_RESTORE_READINESS_SCHEMA_VERSION, "status": "missing"}
    return readiness


@router.post("/data-lifecycle/archive/restore/readiness/rebuild")
async def post_data_lifecycle_archive_restore_readiness_rebuild():
    policy = _policy_mod.load_policy()
    try:
        record, readiness = _archive_restore_mod.rebuild_readiness_report(policy=policy)
    except Exception as exc:
        latest_readiness = _archive_restore_mod.read_readiness_report(policy=policy)
        raise HTTPException(
            status_code=503,
            detail={
                "schema_version": _archive_restore_mod.ARCHIVE_RESTORE_READINESS_REBUILD_SCHEMA_VERSION,
                "message": "archive restore readiness rebuild failed",
                "error": str(exc),
                "readiness": latest_readiness,
            },
        ) from exc
    return {
        "schema_version": _archive_restore_mod.ARCHIVE_RESTORE_READINESS_REBUILD_SCHEMA_VERSION,
        "record": record,
        "readiness": readiness,
    }


@router.get("/data-lifecycle/archive/execution/gate")
async def get_data_lifecycle_archive_execution_gate():
    policy = _policy_mod.load_policy()
    gate = _archive_gate_mod.read_gate(policy=policy)
    if gate is None:
        return {"schema_version": _archive_gate_mod.ARCHIVE_EXECUTION_GATE_SCHEMA_VERSION, "status": "missing"}
    return gate


@router.post("/data-lifecycle/archive/execution/gate/rebuild")
async def post_data_lifecycle_archive_execution_gate_rebuild():
    policy = _policy_mod.load_policy()
    try:
        record, gate = _archive_gate_mod.rebuild_gate(policy=policy)
    except Exception as exc:
        latest_gate = _archive_gate_mod.read_gate(policy=policy)
        raise HTTPException(
            status_code=503,
            detail={
                "schema_version": _archive_gate_mod.ARCHIVE_EXECUTION_GATE_REBUILD_SCHEMA_VERSION,
                "message": "archive execution gate rebuild failed",
                "error": str(exc),
                "gate": latest_gate,
            },
        ) from exc
    return {
        "schema_version": _archive_gate_mod.ARCHIVE_EXECUTION_GATE_REBUILD_SCHEMA_VERSION,
        "record": record,
        "gate": gate,
    }


@router.get("/data-lifecycle/archive/approval")
async def get_data_lifecycle_archive_approval():
    policy = _policy_mod.load_policy()
    approval = _archive_approval_mod.read_approval(policy=policy)
    if approval is None:
        return {"schema_version": _archive_approval_mod.ARCHIVE_OPERATOR_APPROVAL_SCHEMA_VERSION, "status": "missing"}
    return approval


@router.post("/data-lifecycle/archive/pilot/copy-one")
async def post_data_lifecycle_archive_pilot_copy_one():
    policy = _policy_mod.load_policy()
    try:
        record, pilot = _archive_pilot_mod.copy_one_pilot(policy=policy)
    except Exception as exc:
        latest = _archive_pilot_mod.read_latest_pilot_record(policy=policy)
        raise HTTPException(
            status_code=503,
            detail={
                "schema_version": _archive_pilot_mod.ARCHIVE_PILOT_RECORD_SCHEMA_VERSION,
                "message": "archive pilot copy-one failed",
                "error": str(exc),
                "pilot": latest,
            },
        ) from exc
    return {
        "schema_version": _archive_pilot_mod.ARCHIVE_PILOT_RECORD_SCHEMA_VERSION,
        "record": record,
        "pilot": pilot,
    }


@router.get("/data-lifecycle/archive/pilot/latest")
async def get_data_lifecycle_archive_pilot_latest():
    policy = _policy_mod.load_policy()
    latest = _archive_pilot_mod.read_latest_pilot_record(policy=policy)
    if latest is None:
        return {"schema_version": _archive_pilot_mod.ARCHIVE_PILOT_RECORD_SCHEMA_VERSION, "status": "missing"}
    return latest


@router.get("/data-lifecycle/archive/readthrough/report")
async def get_data_lifecycle_archive_readthrough_report():
    policy = _policy_mod.load_policy()
    report = _archive_readthrough_mod.read_report(policy=policy)
    if report is None:
        return {
            "schema_version": _archive_readthrough_mod.ARCHIVE_READTHROUGH_REPORT_SCHEMA_VERSION,
            "status": "missing",
        }
    return report


@router.post("/data-lifecycle/archive/readthrough/report/rebuild")
async def post_data_lifecycle_archive_readthrough_report_rebuild():
    policy = _policy_mod.load_policy()
    try:
        record, report = _archive_readthrough_mod.rebuild_report(policy=policy)
    except Exception as exc:
        latest = _archive_readthrough_mod.read_report(policy=policy)
        raise HTTPException(
            status_code=503,
            detail={
                "schema_version": _archive_readthrough_mod.ARCHIVE_READTHROUGH_REPORT_REBUILD_SCHEMA_VERSION,
                "message": "archive readthrough report rebuild failed",
                "error": str(exc),
                "report": latest,
            },
        ) from exc
    return {
        "schema_version": _archive_readthrough_mod.ARCHIVE_READTHROUGH_REPORT_REBUILD_SCHEMA_VERSION,
        "record": record,
        "report": report,
    }


@router.get("/data-lifecycle/archive/fallback/simulation")
async def get_data_lifecycle_archive_fallback_simulation():
    policy = _policy_mod.load_policy()
    report = _archive_fallback_mod.read_report(policy=policy)
    if report is None:
        return {
            "schema_version": _archive_fallback_mod.ARCHIVE_FALLBACK_SIMULATION_SCHEMA_VERSION,
            "status": "missing",
        }
    return report


@router.post("/data-lifecycle/archive/fallback/simulation/rebuild")
async def post_data_lifecycle_archive_fallback_simulation_rebuild():
    policy = _policy_mod.load_policy()
    try:
        record, report = _archive_fallback_mod.rebuild_report(policy=policy)
    except Exception as exc:
        latest = _archive_fallback_mod.read_report(policy=policy)
        raise HTTPException(
            status_code=503,
            detail={
                "schema_version": _archive_fallback_mod.ARCHIVE_FALLBACK_SIMULATION_REBUILD_SCHEMA_VERSION,
                "message": "archive fallback simulation rebuild failed",
                "error": str(exc),
                "report": latest,
            },
        ) from exc
    return {
        "schema_version": _archive_fallback_mod.ARCHIVE_FALLBACK_SIMULATION_REBUILD_SCHEMA_VERSION,
        "record": record,
        "report": report,
    }


@router.get("/data-lifecycle/archive/quarantine/readiness")
async def get_data_lifecycle_archive_quarantine_readiness():
    policy = _policy_mod.load_policy()
    plan = _archive_quarantine_mod.read_plan(policy=policy)
    if plan is None:
        return {
            "schema_version": _archive_quarantine_mod.ARCHIVE_QUARANTINE_READINESS_SCHEMA_VERSION,
            "status": "missing",
        }
    return plan


@router.post("/data-lifecycle/archive/quarantine/readiness/rebuild")
async def post_data_lifecycle_archive_quarantine_readiness_rebuild():
    policy = _policy_mod.load_policy()
    try:
        record, plan = _archive_quarantine_mod.rebuild_plan(policy=policy)
    except Exception as exc:
        latest = _archive_quarantine_mod.read_plan(policy=policy)
        raise HTTPException(
            status_code=503,
            detail={
                "schema_version": _archive_quarantine_mod.ARCHIVE_QUARANTINE_READINESS_REBUILD_SCHEMA_VERSION,
                "message": "archive quarantine readiness rebuild failed",
                "error": str(exc),
                "plan": latest,
            },
        ) from exc
    return {
        "schema_version": _archive_quarantine_mod.ARCHIVE_QUARANTINE_READINESS_REBUILD_SCHEMA_VERSION,
        "record": record,
        "plan": plan,
    }


@router.get("/data-lifecycle/archive/quarantine/latest")
async def get_data_lifecycle_archive_quarantine_latest():
    policy = _policy_mod.load_policy()
    latest = _archive_quarantine_exec_mod.read_record(policy=policy)
    if latest is None:
        return {
            "schema_version": _archive_quarantine_exec_mod.ARCHIVE_SOURCE_QUARANTINE_RECORD_SCHEMA_VERSION,
            "status": "missing",
        }
    return latest


@router.post("/data-lifecycle/archive/quarantine/move-one")
async def post_data_lifecycle_archive_quarantine_move_one():
    policy = _policy_mod.load_policy()
    try:
        record, quarantine = _archive_quarantine_exec_mod.execute_single_artifact_quarantine(policy=policy)
    except Exception as exc:
        latest = _archive_quarantine_exec_mod.read_record(policy=policy)
        raise HTTPException(
            status_code=503,
            detail={
                "schema_version": _archive_quarantine_exec_mod.ARCHIVE_SOURCE_QUARANTINE_RECORD_SCHEMA_VERSION,
                "message": "archive quarantine move-one failed",
                "error": str(exc),
                "quarantine": latest,
            },
        ) from exc
    return {
        "schema_version": _archive_quarantine_exec_mod.ARCHIVE_SOURCE_QUARANTINE_RECORD_SCHEMA_VERSION,
        "record": record,
        "quarantine": quarantine,
    }


@router.get("/data-lifecycle/archive/restore/pilot/latest")
async def get_data_lifecycle_archive_restore_pilot_latest():
    policy = _policy_mod.load_policy()
    latest = _archive_restore_pilot_mod.read_latest_restore_pilot_record(policy=policy)
    if latest is None:
        return {
            "schema_version": _archive_restore_pilot_mod.ARCHIVE_RESTORE_PILOT_SCHEMA_VERSION,
            "status": "missing",
        }
    return latest


@router.post("/data-lifecycle/archive/restore/pilot/run")
async def post_data_lifecycle_archive_restore_pilot_run():
    policy = _policy_mod.load_policy()
    try:
        record, restore = _archive_restore_pilot_mod.execute_restore_pilot(policy=policy)
    except Exception as exc:
        latest = _archive_restore_pilot_mod.read_latest_restore_pilot_record(policy=policy)
        raise HTTPException(
            status_code=503,
            detail={
                "schema_version": _archive_restore_pilot_mod.ARCHIVE_RESTORE_PILOT_SCHEMA_VERSION,
                "message": "archive restore pilot failed",
                "error": str(exc),
                "restore": latest,
            },
        ) from exc
    return {
        "schema_version": _archive_restore_pilot_mod.ARCHIVE_RESTORE_PILOT_SCHEMA_VERSION,
        "record": record,
        "restore": restore,
    }


@router.get("/data-lifecycle/archive/non-active-candidates/report")
async def get_data_lifecycle_archive_non_active_candidates_report():
    policy = _policy_mod.load_policy()
    report = _archive_non_active_candidates_mod.read_report(policy=policy)
    if report is None:
        return {
            "schema_version": _archive_non_active_candidates_mod.NON_ACTIVE_CANDIDATE_REPORT_SCHEMA_VERSION,
            "status": "missing",
        }
    return report


@router.post("/data-lifecycle/archive/non-active-candidates/report/rebuild")
async def post_data_lifecycle_archive_non_active_candidates_report_rebuild():
    policy = _policy_mod.load_policy()
    try:
        record, report = _archive_non_active_candidates_mod.rebuild_report(policy=policy)
    except Exception as exc:
        latest = _archive_non_active_candidates_mod.read_report(policy=policy)
        raise HTTPException(
            status_code=503,
            detail={
                "schema_version": _archive_non_active_candidates_mod.NON_ACTIVE_CANDIDATE_REBUILD_SCHEMA_VERSION,
                "message": "archive non-active candidate report rebuild failed",
                "error": str(exc),
                "report": latest,
            },
        ) from exc
    return {
        "schema_version": _archive_non_active_candidates_mod.NON_ACTIVE_CANDIDATE_REBUILD_SCHEMA_VERSION,
        "record": record,
        "report": report,
    }


@router.get("/data-lifecycle/archive/non-active-quarantine/readiness")
async def get_data_lifecycle_archive_non_active_quarantine_readiness():
    policy = _policy_mod.load_policy()
    plan = _archive_non_active_quarantine_mod.read_plan(policy=policy)
    if plan is None:
        return {
            "schema_version": _archive_non_active_quarantine_mod.NON_ACTIVE_QUARANTINE_READINESS_SCHEMA_VERSION,
            "status": "missing",
        }
    return plan


@router.post("/data-lifecycle/archive/non-active-quarantine/readiness/rebuild")
async def post_data_lifecycle_archive_non_active_quarantine_readiness_rebuild():
    policy = _policy_mod.load_policy()
    try:
        record, plan = _archive_non_active_quarantine_mod.rebuild_plan(policy=policy)
    except Exception as exc:
        latest = _archive_non_active_quarantine_mod.read_plan(policy=policy)
        raise HTTPException(
            status_code=503,
            detail={
                "schema_version": _archive_non_active_quarantine_mod.NON_ACTIVE_QUARANTINE_READINESS_REBUILD_SCHEMA_VERSION,
                "message": "archive non-active quarantine readiness rebuild failed",
                "error": str(exc),
                "plan": latest,
            },
        ) from exc
    return {
        "schema_version": _archive_non_active_quarantine_mod.NON_ACTIVE_QUARANTINE_READINESS_REBUILD_SCHEMA_VERSION,
        "record": record,
        "plan": plan,
    }


@router.get("/data-lifecycle/archive/non-active-quarantine/execution/gate")
async def get_data_lifecycle_archive_non_active_quarantine_execution_gate():
    policy = _policy_mod.load_policy()
    gate = _archive_non_active_gate_mod.read_gate(policy=policy)
    if gate is None:
        return {
            "schema_version": _archive_non_active_gate_mod.NON_ACTIVE_EXECUTION_GATE_SCHEMA_VERSION,
            "status": "missing",
        }
    return gate


@router.post("/data-lifecycle/archive/non-active-quarantine/execution/gate/rebuild")
async def post_data_lifecycle_archive_non_active_quarantine_execution_gate_rebuild():
    policy = _policy_mod.load_policy()
    try:
        record, gate = _archive_non_active_gate_mod.rebuild_gate(policy=policy)
    except Exception as exc:
        latest = _archive_non_active_gate_mod.read_gate(policy=policy)
        raise HTTPException(
            status_code=503,
            detail={
                "schema_version": _archive_non_active_gate_mod.NON_ACTIVE_EXECUTION_GATE_REBUILD_SCHEMA_VERSION,
                "message": "archive non-active execution gate rebuild failed",
                "error": str(exc),
                "gate": latest,
            },
        ) from exc
    return {
        "schema_version": _archive_non_active_gate_mod.NON_ACTIVE_EXECUTION_GATE_REBUILD_SCHEMA_VERSION,
        "record": record,
        "gate": gate,
    }


@router.get("/data-lifecycle/archive/non-active-quarantine/latest")
async def get_data_lifecycle_archive_non_active_quarantine_latest():
    policy = _policy_mod.load_policy()
    latest = _archive_non_active_quarantine_exec_mod.read_record(policy=policy)
    if latest is None:
        return {
            "schema_version": _archive_non_active_quarantine_exec_mod.NON_ACTIVE_QUARANTINE_RECORD_SCHEMA_VERSION,
            "status": "missing",
        }
    return latest


@router.post("/data-lifecycle/archive/non-active-quarantine/move-one")
async def post_data_lifecycle_archive_non_active_quarantine_move_one():
    policy = _policy_mod.load_policy()
    try:
        record, quarantine = _archive_non_active_quarantine_exec_mod.execute_single_non_active_copy_quarantine(
            policy=policy
        )
    except Exception as exc:
        latest = _archive_non_active_quarantine_exec_mod.read_record(policy=policy)
        raise HTTPException(
            status_code=500,
            detail={
                "schema_version": _archive_non_active_quarantine_exec_mod.NON_ACTIVE_QUARANTINE_RECORD_SCHEMA_VERSION,
                "message": "archive non-active quarantine move-one failed",
                "error": str(exc),
                "quarantine": latest,
            },
        ) from exc
    return {
        "schema_version": _archive_non_active_quarantine_exec_mod.NON_ACTIVE_QUARANTINE_RECORD_SCHEMA_VERSION,
        "record": record,
        "quarantine": quarantine,
    }
