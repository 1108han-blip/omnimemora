"""Read-only lifecycle health and manual refresh APIs for Data Lifecycle Plane."""

from __future__ import annotations

import importlib

from fastapi import APIRouter, HTTPException

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
