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
    retention_manifest_file: str = ""
    traceability_report_file: str = ""
    archive_plan_file: str = ""
    archive_transaction_preview_file: str = ""
    archive_restore_readiness_file: str = ""
    archive_execution_gate_file: str = ""
    archive_operator_approval_file: str = ""
    archive_pilot_root: str = ""
    archive_pilot_record_file: str = ""
    archive_readthrough_report_file: str = ""
    archive_fallback_simulation_file: str = ""
    archive_quarantine_root: str = ""
    archive_quarantine_readiness_file: str = ""
    archive_quarantine_record_file: str = ""
    archive_restore_pilot_record_file: str = ""
    archive_restore_staging_root: str = ""
    archive_non_active_candidate_report_file: str = ""
    archive_non_active_quarantine_readiness_file: str = ""
    archive_non_active_execution_gate_file: str = ""
    meter_cleanup_preview_file: str = ""
    meter_cleanup_execution_gate_file: str = ""
    meter_cleanup_transaction_preview_file: str = ""
    meter_cleanup_rollback_drill_file: str = ""
    meter_cleanup_rollback_staging_root: str = ""
    meter_cleanup_selected_candidate_file: str = ""
    meter_cleanup_pilot_approval_template_file: str = ""
    meter_cleanup_pilot_operator_approval_file: str = ""
    meter_cleanup_quarantine_root: str = ""
    meter_cleanup_pilot_record_file: str = ""
    meter_backup_export_readiness_file: str = ""
    meter_backup_export_plan_file: str = ""
    meter_backup_export_package_manifest_file: str = ""
    meter_backup_export_approval_template_file: str = ""
    meter_backup_export_execution_gate_file: str = ""
    meter_backup_export_operator_approval_file: str = ""
    meter_backup_export_execution_proposal_file: str = ""
    meter_backup_export_copy_pilot_root: str = ""
    meter_backup_export_copy_pilot_record_file: str = ""
    meter_backup_export_restore_readback_file: str = ""
    meter_backup_export_copy_pilot_allow_override: bool = True
    meter_backup_export_destination: str = ""
    raw_evidence_segments_manifest_file: str = ""
    raw_evidence_segments_root: str = ""
    raw_evidence_segments_mode: str = "dual_write_observe_only"
    raw_evidence_segment_max_bytes: int = 32 * 1024 * 1024
    raw_evidence_segment_max_age_seconds: int = 6 * 60 * 60
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
    retention_manifest_file = os.getenv(
        "OMNIMEMORA_DLP_RETENTION_MANIFEST_FILE",
        str(base_dir / "retention_manifest.json"),
    )
    traceability_report_file = os.getenv(
        "OMNIMEMORA_DLP_TRACEABILITY_REPORT_FILE",
        str(base_dir / "traceability_report.json"),
    )
    archive_plan_file = os.getenv(
        "OMNIMEMORA_DLP_ARCHIVE_PLAN_FILE",
        str(base_dir / "archive_candidate_plan.json"),
    )
    archive_transaction_preview_file = os.getenv(
        "OMNIMEMORA_DLP_ARCHIVE_TRANSACTION_PREVIEW_FILE",
        str(base_dir / "archive_transaction_preview.json"),
    )
    archive_restore_readiness_file = os.getenv(
        "OMNIMEMORA_DLP_ARCHIVE_RESTORE_READINESS_FILE",
        str(base_dir / "archive_restore_readiness_report.json"),
    )
    archive_execution_gate_file = os.getenv(
        "OMNIMEMORA_DLP_ARCHIVE_EXECUTION_GATE_FILE",
        str(base_dir / "archive_execution_gate.json"),
    )
    archive_operator_approval_file = os.getenv(
        "OMNIMEMORA_DLP_ARCHIVE_OPERATOR_APPROVAL_FILE",
        str(base_dir / "archive_operator_approval.json"),
    )
    archive_pilot_root = os.getenv(
        "OMNIMEMORA_DLP_ARCHIVE_PILOT_ROOT",
        str(base_dir / "archive" / "pilot"),
    )
    archive_pilot_record_file = os.getenv(
        "OMNIMEMORA_DLP_ARCHIVE_PILOT_RECORD_FILE",
        str(base_dir / "archive_pilot_record.json"),
    )
    archive_readthrough_report_file = os.getenv(
        "OMNIMEMORA_DLP_ARCHIVE_READTHROUGH_REPORT_FILE",
        str(base_dir / "archive_readthrough_report.json"),
    )
    archive_fallback_simulation_file = os.getenv(
        "OMNIMEMORA_DLP_ARCHIVE_FALLBACK_SIMULATION_FILE",
        str(base_dir / "archive_fallback_simulation_report.json"),
    )
    archive_quarantine_root = os.getenv(
        "OMNIMEMORA_DLP_ARCHIVE_QUARANTINE_ROOT",
        str(base_dir / "quarantine" / "source"),
    )
    archive_quarantine_readiness_file = os.getenv(
        "OMNIMEMORA_DLP_ARCHIVE_QUARANTINE_READINESS_FILE",
        str(base_dir / "archive_quarantine_readiness_plan.json"),
    )
    archive_quarantine_record_file = os.getenv(
        "OMNIMEMORA_DLP_ARCHIVE_QUARANTINE_RECORD_FILE",
        str(base_dir / "archive_quarantine_record.json"),
    )
    archive_restore_pilot_record_file = os.getenv(
        "OMNIMEMORA_DLP_ARCHIVE_RESTORE_PILOT_RECORD_FILE",
        str(base_dir / "archive_restore_pilot_record.json"),
    )
    archive_restore_staging_root = os.getenv(
        "OMNIMEMORA_DLP_ARCHIVE_RESTORE_STAGING_ROOT",
        str(base_dir / "restore" / "staging"),
    )
    archive_non_active_candidate_report_file = os.getenv(
        "OMNIMEMORA_DLP_ARCHIVE_NON_ACTIVE_CANDIDATE_REPORT_FILE",
        str(base_dir / "archive_non_active_candidate_report.json"),
    )
    archive_non_active_quarantine_readiness_file = os.getenv(
        "OMNIMEMORA_DLP_ARCHIVE_NON_ACTIVE_QUARANTINE_READINESS_FILE",
        str(base_dir / "archive_non_active_quarantine_readiness_plan.json"),
    )
    archive_non_active_execution_gate_file = os.getenv(
        "OMNIMEMORA_DLP_ARCHIVE_NON_ACTIVE_EXECUTION_GATE_FILE",
        str(base_dir / "archive_non_active_execution_gate.json"),
    )
    meter_cleanup_preview_file = os.getenv(
        "OMNIMEMORA_DLP_METER_CLEANUP_PREVIEW_FILE",
        str(base_dir / "meter_cleanup_preview.json"),
    )
    meter_cleanup_execution_gate_file = os.getenv(
        "OMNIMEMORA_DLP_METER_CLEANUP_EXECUTION_GATE_FILE",
        str(base_dir / "meter_cleanup_execution_gate.json"),
    )
    meter_cleanup_transaction_preview_file = os.getenv(
        "OMNIMEMORA_DLP_METER_CLEANUP_TRANSACTION_PREVIEW_FILE",
        str(base_dir / "meter_cleanup_transaction_preview.json"),
    )
    meter_cleanup_rollback_drill_file = os.getenv(
        "OMNIMEMORA_DLP_METER_CLEANUP_ROLLBACK_DRILL_FILE",
        str(base_dir / "meter_cleanup_rollback_drill.json"),
    )
    meter_cleanup_rollback_staging_root = os.getenv(
        "OMNIMEMORA_DLP_METER_CLEANUP_ROLLBACK_STAGING_ROOT",
        str(base_dir / "cleanup_rollback" / "staging"),
    )
    meter_cleanup_selected_candidate_file = os.getenv(
        "OMNIMEMORA_DLP_METER_CLEANUP_SELECTED_CANDIDATE_FILE",
        str(base_dir / "meter_cleanup_selected_candidate.json"),
    )
    meter_cleanup_pilot_approval_template_file = os.getenv(
        "OMNIMEMORA_DLP_METER_CLEANUP_PILOT_APPROVAL_TEMPLATE_FILE",
        str(base_dir / "meter_cleanup_pilot_approval_template.json"),
    )
    meter_cleanup_pilot_operator_approval_file = os.getenv(
        "OMNIMEMORA_DLP_METER_CLEANUP_PILOT_OPERATOR_APPROVAL_FILE",
        str(base_dir / "meter_cleanup_pilot_operator_approval.json"),
    )
    meter_cleanup_quarantine_root = os.getenv(
        "OMNIMEMORA_DLP_METER_CLEANUP_QUARANTINE_ROOT",
        str(base_dir / "quarantine" / "meter_cleanup"),
    )
    meter_cleanup_pilot_record_file = os.getenv(
        "OMNIMEMORA_DLP_METER_CLEANUP_PILOT_RECORD_FILE",
        str(base_dir / "meter_cleanup_pilot_record.json"),
    )
    meter_backup_export_readiness_file = os.getenv(
        "OMNIMEMORA_DLP_METER_BACKUP_EXPORT_READINESS_FILE",
        str(base_dir / "meter_backup_export_readiness.json"),
    )
    meter_backup_export_plan_file = os.getenv(
        "OMNIMEMORA_DLP_METER_BACKUP_EXPORT_PLAN_FILE",
        str(base_dir / "meter_backup_export_plan.json"),
    )
    meter_backup_export_package_manifest_file = os.getenv(
        "OMNIMEMORA_DLP_METER_BACKUP_EXPORT_PACKAGE_MANIFEST_FILE",
        str(base_dir / "meter_backup_export_package_manifest.json"),
    )
    meter_backup_export_approval_template_file = os.getenv(
        "OMNIMEMORA_DLP_METER_BACKUP_EXPORT_APPROVAL_TEMPLATE_FILE",
        str(base_dir / "meter_backup_export_approval_template.json"),
    )
    meter_backup_export_execution_gate_file = os.getenv(
        "OMNIMEMORA_DLP_METER_BACKUP_EXPORT_EXECUTION_GATE_FILE",
        str(base_dir / "meter_backup_export_execution_gate.json"),
    )
    meter_backup_export_operator_approval_file = os.getenv(
        "OMNIMEMORA_DLP_METER_BACKUP_EXPORT_OPERATOR_APPROVAL_FILE",
        str(base_dir / "meter_backup_export_operator_approval.json"),
    )
    meter_backup_export_execution_proposal_file = os.getenv(
        "OMNIMEMORA_DLP_METER_BACKUP_EXPORT_EXECUTION_PROPOSAL_FILE",
        str(base_dir / "meter_backup_export_execution_proposal.json"),
    )
    meter_backup_export_copy_pilot_root = os.getenv(
        "OMNIMEMORA_DLP_METER_BACKUP_EXPORT_COPY_PILOT_ROOT",
        str(base_dir / "backup_export" / "pilot"),
    )
    meter_backup_export_copy_pilot_record_file = os.getenv(
        "OMNIMEMORA_DLP_METER_BACKUP_EXPORT_COPY_PILOT_RECORD_FILE",
        str(base_dir / "meter_backup_export_copy_pilot_record.json"),
    )
    meter_backup_export_restore_readback_file = os.getenv(
        "OMNIMEMORA_DLP_METER_BACKUP_EXPORT_RESTORE_READBACK_FILE",
        str(base_dir / "meter_backup_export_restore_readback.json"),
    )
    meter_backup_export_copy_pilot_allow_override = os.getenv(
        "OMNIMEMORA_DLP_METER_BACKUP_EXPORT_COPY_PILOT_ALLOW_OVERRIDE",
        "true",
    ).strip().lower() in {"1", "true", "yes", "on"}
    meter_backup_export_destination = os.getenv(
        "OMNIMEMORA_DLP_METER_BACKUP_EXPORT_DESTINATION",
        "",
    ).strip()
    raw_evidence_segments_manifest_file = os.getenv(
        "OMNIMEMORA_DLP_RAW_EVIDENCE_SEGMENTS_MANIFEST_FILE",
        str(base_dir / "raw_evidence_segments_manifest.json"),
    )
    raw_evidence_segments_root = os.getenv(
        "OMNIMEMORA_DLP_RAW_EVIDENCE_SEGMENTS_ROOT",
        str(base_dir / "raw_evidence_segments"),
    )
    raw_evidence_segments_mode = os.getenv(
        "OMNIMEMORA_DLP_RAW_EVIDENCE_SEGMENTS_MODE",
        "dual_write_observe_only",
    ).strip()
    raw_evidence_segment_max_bytes = int(
        os.getenv(
            "OMNIMEMORA_DLP_RAW_EVIDENCE_SEGMENT_MAX_BYTES",
            str(32 * 1024 * 1024),
        )
    )
    raw_evidence_segment_max_age_seconds = int(
        os.getenv(
            "OMNIMEMORA_DLP_RAW_EVIDENCE_SEGMENT_MAX_AGE_SECONDS",
            str(6 * 60 * 60),
        )
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
        retention_manifest_file=retention_manifest_file,
        traceability_report_file=traceability_report_file,
        archive_plan_file=archive_plan_file,
        archive_transaction_preview_file=archive_transaction_preview_file,
        archive_restore_readiness_file=archive_restore_readiness_file,
        archive_execution_gate_file=archive_execution_gate_file,
        archive_operator_approval_file=archive_operator_approval_file,
        archive_pilot_root=archive_pilot_root,
        archive_pilot_record_file=archive_pilot_record_file,
        archive_readthrough_report_file=archive_readthrough_report_file,
        archive_fallback_simulation_file=archive_fallback_simulation_file,
        archive_quarantine_root=archive_quarantine_root,
        archive_quarantine_readiness_file=archive_quarantine_readiness_file,
        archive_quarantine_record_file=archive_quarantine_record_file,
        archive_restore_pilot_record_file=archive_restore_pilot_record_file,
        archive_restore_staging_root=archive_restore_staging_root,
        archive_non_active_candidate_report_file=archive_non_active_candidate_report_file,
        archive_non_active_quarantine_readiness_file=archive_non_active_quarantine_readiness_file,
        archive_non_active_execution_gate_file=archive_non_active_execution_gate_file,
        meter_cleanup_preview_file=meter_cleanup_preview_file,
        meter_cleanup_execution_gate_file=meter_cleanup_execution_gate_file,
        meter_cleanup_transaction_preview_file=meter_cleanup_transaction_preview_file,
        meter_cleanup_rollback_drill_file=meter_cleanup_rollback_drill_file,
        meter_cleanup_rollback_staging_root=meter_cleanup_rollback_staging_root,
        meter_cleanup_selected_candidate_file=meter_cleanup_selected_candidate_file,
        meter_cleanup_pilot_approval_template_file=meter_cleanup_pilot_approval_template_file,
        meter_cleanup_pilot_operator_approval_file=meter_cleanup_pilot_operator_approval_file,
        meter_cleanup_quarantine_root=meter_cleanup_quarantine_root,
        meter_cleanup_pilot_record_file=meter_cleanup_pilot_record_file,
        meter_backup_export_readiness_file=meter_backup_export_readiness_file,
        meter_backup_export_plan_file=meter_backup_export_plan_file,
        meter_backup_export_package_manifest_file=meter_backup_export_package_manifest_file,
        meter_backup_export_approval_template_file=meter_backup_export_approval_template_file,
        meter_backup_export_execution_gate_file=meter_backup_export_execution_gate_file,
        meter_backup_export_operator_approval_file=meter_backup_export_operator_approval_file,
        meter_backup_export_execution_proposal_file=meter_backup_export_execution_proposal_file,
        meter_backup_export_copy_pilot_root=meter_backup_export_copy_pilot_root,
        meter_backup_export_copy_pilot_record_file=meter_backup_export_copy_pilot_record_file,
        meter_backup_export_restore_readback_file=meter_backup_export_restore_readback_file,
        meter_backup_export_copy_pilot_allow_override=meter_backup_export_copy_pilot_allow_override,
        meter_backup_export_destination=meter_backup_export_destination,
        raw_evidence_segments_manifest_file=raw_evidence_segments_manifest_file,
        raw_evidence_segments_root=raw_evidence_segments_root,
        raw_evidence_segments_mode=raw_evidence_segments_mode or "dual_write_observe_only",
        raw_evidence_segment_max_bytes=max(1, raw_evidence_segment_max_bytes),
        raw_evidence_segment_max_age_seconds=max(60, raw_evidence_segment_max_age_seconds),
        maintenance_enabled=maintenance_enabled,
        maintenance_startup_delay_seconds=max(0.0, maintenance_startup_delay_seconds),
        maintenance_interval_seconds=max(1.0, maintenance_interval_seconds),
        maintenance_budget_seconds=max(0.1, maintenance_budget_seconds),
    )
