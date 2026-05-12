# Phase 6 Plan

## Current Status

## Current Product Compile Target

Added 2026-05-13 after the Claude Code/OpenClaw compile semantics investigation:

- Current highest-value product target: upgrade from narrow memory-context compile to protocol-aware structured context compilation.
- The next compile line must optimize for real token/cost saving without breaking agent tool workflows.
- File-count growth is acceptable when it creates focused compiler modules and replaces single-file accumulation.
- Single-file growth is not acceptable as the default path; keep ingress, orchestration, provider IR, tool graph validation, compression, rebuild, and validation responsibilities separated.
- Runtime blocking is not acceptable: upstream-critical paths must not depend on LLM summarization, cloud policy fetch, historical file scans, or slow persistence.
- Strategy policy can control rollout and budgets only after local protocol-preservation invariants exist.
- This is no longer a Phase6 tail item. Active engineering continues in [Structured Compile Mainline](../../structured_compile/README.md); Phase6 remains the historical governance and promotion index.

### Sub-Workstreams

| Workstream | Status | 文档位置 |
|------------|--------|----------|
| Promotion Workflow Adoption | **已收口 ✓** | 本目录 |
| Promotion Evidence Routing | **已收口 ✓** | 本目录 |
| Promotion Workflow Usage Governance | **已收口 ✓** | `docs/phase6/PROMOTION_USAGE_GOVERNANCE.md` |
| Operational Drift Detection | **已收口 ✓** | `OmniMemora_Operational_Drift_Detection.md` |
| **Promotion Outcome Reporting** | **已收口 ✓** | `OmniMemora_Promotion_Outcome_Reporting_Contract.md` |

---

## Post-Phase6 Governance Records

以下记录属于 **phase6 收口后的 roadmap 外治理增强线**，用于固定后续架构治理与结构迁移结论。

它们不是新的 roadmap phase，也不改变本 README 上方 phase6 子线已收口的事实。

| Record | Status | 文档位置 |
|--------|--------|----------|
| Architecture Governance Batch 2 Closeout | **已收口 ✓** | [OmniMemora_Architecture_Governance_Batch2_Closeout_2026-04-22.md](./OmniMemora_Architecture_Governance_Batch2_Closeout_2026-04-22.md) |
| Architecture Governance Next Mainline | **已收口 ✓（可进入 Skill Suggestion 工程）** | [OmniMemora_Architecture_Governance_Next_Mainline_2026-04-22.md](./OmniMemora_Architecture_Governance_Next_Mainline_2026-04-22.md) |
| Skill Suggestion v1 Closeout | **已收口 ✓（running reality verified）** | [OmniMemora_Skill_Suggestion_v1_Closeout_2026-04-22.md](./OmniMemora_Skill_Suggestion_v1_Closeout_2026-04-22.md) |
| Cloud Reset Batch 1 Spec | **进行中（边界已固定）** | [OmniMemora_Cloud_Reset_Batch1_Spec_2026-04-22.md](./OmniMemora_Cloud_Reset_Batch1_Spec_2026-04-22.md) |
| Cloud Reset Batch 3 Inventory | **已收口 ✓（inventory complete）** | [OmniMemora_Cloud_Reset_Batch3_Inventory_2026-04-23.md](./OmniMemora_Cloud_Reset_Batch3_Inventory_2026-04-23.md) |
| Cloud Reset Batch 4 Cutover Prep | **已收口 ✓（prep complete）** | [OmniMemora_Cloud_Reset_Batch4_Cutover_Prep_2026-04-23.md](./OmniMemora_Cloud_Reset_Batch4_Cutover_Prep_2026-04-23.md) |
| Cloud Reset Batch 5 Cutover Execution | **已收口 ✓（Railway rationalization complete; Cloudflare continuity hold）** | [OmniMemora_Cloud_Reset_Batch5_Cutover_Execution_2026-04-23.md](./OmniMemora_Cloud_Reset_Batch5_Cutover_Execution_2026-04-23.md) |
| Cloud Reset Batch 6 Control Project Cutover | **已收口 ✓（replacement control entry + domain rebind complete）** | [OmniMemora_Cloud_Reset_Batch6_Control_Project_Cutover_2026-04-23.md](./OmniMemora_Cloud_Reset_Batch6_Control_Project_Cutover_2026-04-23.md) |
| Cloud Reset Closeout | **已收口 ✓（mainline complete; legacy api hostname withdrawn from Railway edge）** | [OmniMemora_Cloud_Reset_Closeout_2026-04-23.md](./OmniMemora_Cloud_Reset_Closeout_2026-04-23.md) |
| Controlled Beta Release v1 | **已收口 ✓（closed beta download flow live）** | [OmniMemora_Controlled_Beta_Release_v1_2026-04-23.md](./OmniMemora_Controlled_Beta_Release_v1_2026-04-23.md) |
| Desktop Beta16 Structured Compile Release | **已收口 ✓（local install + cloud download path verified）** | [OmniMemora_Desktop_Beta16_Structured_Compile_Release_Closeout_2026-05-13.md](./OmniMemora_Desktop_Beta16_Structured_Compile_Release_Closeout_2026-05-13.md) |
| **CSP-001 Policy Bundle Promotion Path** | **已收口 ✓（bundle promoted; evidence verified; worktree clean）** | [OmniMemora_CSP001_Policy_Bundle_Promotion_Path_2026-04-24.md](./OmniMemora_CSP001_Policy_Bundle_Promotion_Path_2026-04-24.md) |
| **CSP-001 Candidate Pack Local Import** | **已收口 ✓（repo-validated; worktree clean）** | [CSP-001-CANDIDATE-PACK-LOCAL-IMPORT-CLOSEOUT-2026-04-24.md](../../../../3_governance/CSP-001-CANDIDATE-PACK-LOCAL-IMPORT-CLOSEOUT-2026-04-24.md) |
| **CSP-001 Real Cloud Candidate Source** | **已收口 ✓（repo-validated; running-validated; worktree clean）** | [OmniMemora_CSP001_Real_Cloud_Candidate_Source_Running_Validation_2026-04-24.md](./OmniMemora_CSP001_Real_Cloud_Candidate_Source_Running_Validation_2026-04-24.md) |
| **CSP-001 Real Cloud Candidate Source Running Validation** | **已收口 ✓（running-validated; worktree clean）** | [OmniMemora_CSP001_Real_Cloud_Candidate_Source_Running_Validation_2026-04-24.md](./OmniMemora_CSP001_Real_Cloud_Candidate_Source_Running_Validation_2026-04-24.md) |
| **5173 Agents-Control Polling Relief Closeout** | **已收口 ✓（UI pressure reduced; backend root cause not claimed）** | [OmniMemora_5173_Agents_Control_Polling_Relief_Closeout_2026-04-24.md](./OmniMemora_5173_Agents_Control_Polling_Relief_Closeout_2026-04-24.md) |
| **18011 Agents-Control Performance Diagnosis** | **已收口 ✓（diagnosis-only; implementation deferred）** | [OmniMemora_18011_Agents_Control_Performance_Diagnosis_2026-04-24.md](./OmniMemora_18011_Agents_Control_Performance_Diagnosis_2026-04-24.md) |
| **/agents/control Snapshot Cache Closeout** | **已收口 ✓（agents-control timeout tail stabilized; CPU p95 residual remains）** | [OmniMemora_Agents_Control_Snapshot_Cache_Closeout_2026-04-24.md](./OmniMemora_Agents_Control_Snapshot_Cache_Closeout_2026-04-24.md) |
| **Data Lifecycle Plane Mainline Launch** | **已收口 ✓（Stage 0-19 closed; single non-active copy quarantine baseline frozen; destructive/archive-at-scale not started）** | [OmniMemora_Data_Lifecycle_Plane_Mainline_Launch_2026-04-25.md](./OmniMemora_Data_Lifecycle_Plane_Mainline_Launch_2026-04-25.md) |
| **DLP Batch 1 - Skeleton and First Extraction** | **已收口 ✓（summary/maintenance skeleton complete; destructive maintenance deferred）** | [OmniMemora_DLP_Batch1_Skeleton_First_Extraction_Closeout_2026-04-25.md](./OmniMemora_DLP_Batch1_Skeleton_First_Extraction_Closeout_2026-04-25.md) |
| **DLP Batch 2 - Non-Destructive Auto Maintenance and Summary Warming** | **已收口 ✓（startup warm + interval refresh + singleflight + stale-usable summary read; destructive maintenance deferred）** | [OmniMemora_DLP_Batch2_Non_Destructive_Auto_Maintenance_Closeout_2026-04-25.md](./OmniMemora_DLP_Batch2_Non_Destructive_Auto_Maintenance_Closeout_2026-04-25.md) |
| **DLP Batch 3 - Running Validation for Non-Destructive Maintenance** | **已收口 ✓（scheduler run observed; summary/ledger traceable; /agents/control schema stable; stale/fallback path verified）** | [OmniMemora_DLP_Batch3_Running_Validation_Non_Destructive_Maintenance_2026-04-25.md](./OmniMemora_DLP_Batch3_Running_Validation_Non_Destructive_Maintenance_2026-04-25.md) |
| **DLP Batch 4 - Legacy Read-Path Thinning and Summary Contract Hardening** | **已收口 ✓（summary contract metadata hardened; fresh/stale/legacy degraded path explicit; duplicated read logic reduced）** | [OmniMemora_DLP_Batch4_Legacy_Read_Path_Thinning_Summary_Contract_Hardening_Closeout_2026-04-25.md](./OmniMemora_DLP_Batch4_Legacy_Read_Path_Thinning_Summary_Contract_Hardening_Closeout_2026-04-25.md) |
| **DLP Batch 4.1 - Family Alias Contract Repair** | **已收口 ✓（cc-haha and known Claude profile aliases normalized to claude_code in summary contract）** | [OmniMemora_DLP_Batch4_1_Family_Alias_Contract_Repair_Closeout_2026-04-25.md](./OmniMemora_DLP_Batch4_1_Family_Alias_Contract_Repair_Closeout_2026-04-25.md) |
| **DLP Batch 5 - Running Validation After Summary Contract + Alias Repair** | **已收口 ✓（summary contract active in running reality; cc-haha not independent family/card; fresh path stable without degraded increments）** | [OmniMemora_DLP_Batch5_Running_Validation_After_Summary_Contract_Alias_Repair_2026-04-25.md](./OmniMemora_DLP_Batch5_Running_Validation_After_Summary_Contract_Alias_Repair_2026-04-25.md) |
| **DLP Batch 6 - Lifecycle Health Surface + Non-Destructive Manual Refresh** | **已收口 ✓（18011 lifecycle health surface + manual refresh endpoint + control snapshot cache extraction; /agents/control schema unchanged）** | [OmniMemora_DLP_Batch6_Lifecycle_Health_Surface_Non_Destructive_Manual_Refresh_Closeout_2026-04-25.md](./OmniMemora_DLP_Batch6_Lifecycle_Health_Surface_Non_Destructive_Manual_Refresh_Closeout_2026-04-25.md) |
| **DLP Batch 7 - KPI Summary-First Hot-Read Detachment** | **已收口 ✓（/metrics/summary, /metrics/summary_24h, /metrics/core_capabilities switched to summary-first; legacy fallback writes metrics_read_degraded ledger）** | [OmniMemora_DLP_Batch7_KPI_Summary_First_Hot_Read_Detachment_Closeout_2026-04-25.md](./OmniMemora_DLP_Batch7_KPI_Summary_First_Hot_Read_Detachment_Closeout_2026-04-25.md) |
| **DLP Batch 8 - Running Validation for KPI Summary-First** | **已收口 ✓（adapter+ui promotion; schema stable; fresh summary window did not increase metrics_read_degraded; timeout/error no regression）** | [OmniMemora_DLP_Batch8_Running_Validation_KPI_Summary_First_2026-04-25.md](./OmniMemora_DLP_Batch8_Running_Validation_KPI_Summary_First_2026-04-25.md) |
| **DLP Batch 9 - Storage Pressure Readiness (Inventory-Only)** | **已收口 ✓（health surface adds storage_pressure + recommendation; no destructive cleanup/compression/archive action）** | [OmniMemora_DLP_Batch9_Storage_Pressure_Readiness_Inventory_Only_2026-04-25.md](./OmniMemora_DLP_Batch9_Storage_Pressure_Readiness_Inventory_Only_2026-04-25.md) |
| **DLP Batch 10 - Retention Manifest Skeleton** | **已收口 ✓（inventory-only retention manifest with checksum/line_count/traceability metadata and atomic write）** | [OmniMemora_DLP_Batch10_Retention_Manifest_Skeleton_Closeout_2026-04-25.md](./OmniMemora_DLP_Batch10_Retention_Manifest_Skeleton_Closeout_2026-04-25.md) |
| **DLP Batch 11 - Retention API + Health Integration** | **已收口 ✓（retention manifest read/rebuild endpoints + status surface retention summary; no schema expansion for /agents/control or KPI endpoints）** | [OmniMemora_DLP_Batch11_Retention_API_Health_Integration_Closeout_2026-04-25.md](./OmniMemora_DLP_Batch11_Retention_API_Health_Integration_Closeout_2026-04-25.md) |
| **DLP Batch 12 - Running Validation and Stage 3 Closeout** | **已收口 ✓（adapter+ui promoted; manifest rebuild validated; inventory-only retained; archive execution not started）** | [OmniMemora_DLP_Batch12_Retention_Manifest_Running_Validation_Closeout_2026-04-25.md](./OmniMemora_DLP_Batch12_Retention_Manifest_Running_Validation_Closeout_2026-04-25.md) |
| **DLP Batch 13 - Traceability Report Skeleton** | **已收口 ✓（traceability report inventory/check layer added with request-level pass/partial/fail sampling and atomic write）** | [OmniMemora_DLP_Batch13_Traceability_Report_Skeleton_Closeout_2026-04-25.md](./OmniMemora_DLP_Batch13_Traceability_Report_Skeleton_Closeout_2026-04-25.md) |
| **DLP Batch 14 - Traceability API + Health Integration** | **已收口 ✓（traceability report read/rebuild endpoints + health summary projection; no control/metrics/ingress schema expansion）** | [OmniMemora_DLP_Batch14_Traceability_API_Health_Integration_Closeout_2026-04-25.md](./OmniMemora_DLP_Batch14_Traceability_API_Health_Integration_Closeout_2026-04-25.md) |
| **DLP Batch 15 - Traceability Running Validation + Stage 4 Closeout** | **已收口 ✓（running validation completed; traceability verification = conditional due to partial samples; archive execution not started）** | [OmniMemora_DLP_Batch15_Traceability_Running_Validation_Closeout_2026-04-25.md](./OmniMemora_DLP_Batch15_Traceability_Running_Validation_Closeout_2026-04-25.md) |
| **DLP Batch 16 - Traceability Partial Reason Taxonomy** | **已收口 ✓（partial reason taxonomy + expected/optional sources + evidence epoch + recent-first sampling; report schema append-only compatible）** | [OmniMemora_DLP_Batch16_Traceability_Partial_Reason_Taxonomy_Closeout_2026-04-25.md](./OmniMemora_DLP_Batch16_Traceability_Partial_Reason_Taxonomy_Closeout_2026-04-25.md) |
| **DLP Batch 17 - Traceability Minimal Repair and Chain Completion** | **已收口 ✓（proxy source downgraded to protocol-optional; request_evidence_unbuildable remains fail; health adds unexplained partial + current epoch pass rate）** | [OmniMemora_DLP_Batch17_Traceability_Minimal_Repair_Chain_Completion_Closeout_2026-04-25.md](./OmniMemora_DLP_Batch17_Traceability_Minimal_Repair_Chain_Completion_Closeout_2026-04-25.md) |
| **DLP Batch 18 - Traceability Running Revalidation and Stage 5 Closeout** | **已收口 ✓（adapter+ui promoted; report rebuilt; fail=0 and unexplained_partial=0; traceability verification = passed; archive execution not started）** | [OmniMemora_DLP_Batch18_Traceability_Running_Revalidation_Closeout_2026-04-25.md](./OmniMemora_DLP_Batch18_Traceability_Running_Revalidation_Closeout_2026-04-25.md) |
| **DLP Batch 19 - Archive Candidate Plan Skeleton** | **已收口 ✓（dry-run-only archive candidate planner + policy path + core tests; no archive execution path）** | [OmniMemora_DLP_Batch19_Archive_Candidate_Plan_Skeleton_Closeout_2026-04-25.md](./OmniMemora_DLP_Batch19_Archive_Candidate_Plan_Skeleton_Closeout_2026-04-25.md) |
| **DLP Batch 20 - Archive Plan API + Health Integration** | **已收口 ✓（archive plan read/rebuild endpoints + status archive_plan projection; no execute/archive/delete/move endpoint）** | [OmniMemora_DLP_Batch20_Archive_Plan_API_Health_Integration_Closeout_2026-04-25.md](./OmniMemora_DLP_Batch20_Archive_Plan_API_Health_Integration_Closeout_2026-04-25.md) |
| **DLP Batch 21 - Archive Candidate Running Dry-Run Validation** | **已收口 ✓（adapter+ui promoted; retention/traceability/archive plan rebuild validated; mode=dry_run_only; raw evidence archive side effect absent）** | [OmniMemora_DLP_Batch21_Archive_Candidate_Running_Dry_Run_Validation_Closeout_2026-04-25.md](./OmniMemora_DLP_Batch21_Archive_Candidate_Running_Dry_Run_Validation_Closeout_2026-04-25.md) |
| **DLP Batch 22 - Archive Transaction Preview Safety Layer** | **已收口 ✓（preview-only transaction safety layer; eligible-only preview items with precondition checks; no archive execution path）** | [OmniMemora_DLP_Batch22_Archive_Transaction_Preview_Safety_Layer_Closeout_2026-04-25.md](./OmniMemora_DLP_Batch22_Archive_Transaction_Preview_Safety_Layer_Closeout_2026-04-25.md) |
| **DLP Batch 23 - Archive Restore Readiness Contract** | **已收口 ✓（readiness-only restore/read-through contract; request-to-restore explainability mapping; no cold-read execution）** | [OmniMemora_DLP_Batch23_Archive_Restore_Readiness_Contract_Closeout_2026-04-25.md](./OmniMemora_DLP_Batch23_Archive_Restore_Readiness_Contract_Closeout_2026-04-25.md) |
| **DLP Batch 24 - Archive Safety API + Health Surface** | **已收口 ✓（preview/readiness rebuild + read endpoints and status projection; no execute/archive/delete/move/compress endpoint）** | [OmniMemora_DLP_Batch24_Archive_Safety_API_Health_Surface_Closeout_2026-04-25.md](./OmniMemora_DLP_Batch24_Archive_Safety_API_Health_Surface_Closeout_2026-04-25.md) |
| **DLP Batch 25 - Archive Safety Running Preview Validation** | **已收口 ✓（adapter+ui promoted; safety rebuild chain validated; preview/readiness schemas and status projections verified; raw evidence archive side effect absent）** | [OmniMemora_DLP_Batch25_Archive_Safety_Running_Preview_Validation_Closeout_2026-04-25.md](./OmniMemora_DLP_Batch25_Archive_Safety_Running_Preview_Validation_Closeout_2026-04-25.md) |
| **DLP Batch 26 - Archive Execution Gate Contract** | **已收口 ✓（gate-only decision artifact with blocking reasons, required approvals, artifact hashes and default allowed=false）** | [OmniMemora_DLP_Batch26_Archive_Execution_Gate_Contract_Closeout_2026-04-25.md](./OmniMemora_DLP_Batch26_Archive_Execution_Gate_Contract_Closeout_2026-04-25.md) |
| **DLP Batch 27 - Archive Operator Approval Contract** | **已收口 ✓（local-only operator approval artifact schema and hash-bound validity contract; upstream change invalidates approval）** | [OmniMemora_DLP_Batch27_Archive_Operator_Approval_Contract_Closeout_2026-04-25.md](./OmniMemora_DLP_Batch27_Archive_Operator_Approval_Contract_Closeout_2026-04-25.md) |
| **DLP Batch 28 - Archive Gate API + Health Surface** | **已收口 ✓（execution gate read/rebuild and approval read endpoints plus status gate summary; no execute endpoint）** | [OmniMemora_DLP_Batch28_Archive_Gate_API_Health_Surface_Closeout_2026-04-25.md](./OmniMemora_DLP_Batch28_Archive_Gate_API_Health_Surface_Closeout_2026-04-25.md) |
| **DLP Batch 29 - Archive Gate Running Validation** | **已收口 ✓（adapter+ui promoted; missing-approval blocked, matching-approval allowed, upstream-change invalidation confirmed; archive execution not started）** | [OmniMemora_DLP_Batch29_Archive_Gate_Running_Validation_Closeout_2026-04-25.md](./OmniMemora_DLP_Batch29_Archive_Gate_Running_Validation_Closeout_2026-04-25.md) |
| **DLP Batch 30 - Single-Artifact Pilot Executor** | **已收口 ✓（copy-only single-artifact pilot executor with deterministic selection and strict prechecks; no source delete/move/compress）** | [OmniMemora_DLP_Batch30_Single_Artifact_Pilot_Executor_Closeout_2026-04-25.md](./OmniMemora_DLP_Batch30_Single_Artifact_Pilot_Executor_Closeout_2026-04-25.md) |
| **DLP Batch 31 - Pilot API + Health Surface** | **已收口 ✓（pilot copy-one execute endpoint + latest read endpoint + status archive_pilot summary; no batch/delete/move/compress endpoint）** | [OmniMemora_DLP_Batch31_Pilot_API_Health_Surface_Closeout_2026-04-25.md](./OmniMemora_DLP_Batch31_Pilot_API_Health_Surface_Closeout_2026-04-25.md) |
| **DLP Batch 32 - Pilot Restore Verification** | **已收口 ✓（restore readiness adds pilot copy verification for checksum/restore-key/source-retained/read-path-unchanged）** | [OmniMemora_DLP_Batch32_Pilot_Restore_Verification_Closeout_2026-04-25.md](./OmniMemora_DLP_Batch32_Pilot_Restore_Verification_Closeout_2026-04-25.md) |
| **DLP Batch 33 - Running Pilot Validation** | **已收口 ✓（adapter+ui promoted; gate missing-approval blocked then matching-approval allowed; one copy-only pilot executed with checksum match and source retained）** | [OmniMemora_DLP_Batch33_Running_Pilot_Validation_Closeout_2026-04-25.md](./OmniMemora_DLP_Batch33_Running_Pilot_Validation_Closeout_2026-04-25.md) |
| **DLP Batch 34 - Archive Read-Through Resolver** | **已收口 ✓（shadow_validation_only read-through resolver with source/archive checksum diagnostics; no production read-path switch）** | [OmniMemora_DLP_Batch34_Archive_Readthrough_Resolver_Closeout_2026-04-25.md](./OmniMemora_DLP_Batch34_Archive_Readthrough_Resolver_Closeout_2026-04-25.md) |
| **DLP Batch 35 - Read-Through API + Health Surface** | **已收口 ✓（readthrough report read/rebuild endpoints + status archive_readthrough projection; no cleanup/switch endpoints）** | [OmniMemora_DLP_Batch35_Readthrough_API_Health_Surface_Closeout_2026-04-25.md](./OmniMemora_DLP_Batch35_Readthrough_API_Health_Surface_Closeout_2026-04-25.md) |
| **DLP Batch 36 - Request Evidence Shadow Cross-Check** | **已收口 ✓（read-through report binds restore-key mapping to request-evidence shadow contract with mapped/not_applicable states）** | [OmniMemora_DLP_Batch36_Request_Evidence_Shadow_Cross_Check_Closeout_2026-04-25.md](./OmniMemora_DLP_Batch36_Request_Evidence_Shadow_Cross_Check_Closeout_2026-04-25.md) |
| **DLP Batch 37 - Running Shadow Validation** | **已收口 ✓（adapter+ui promoted; readthrough report passed after upstream realignment; source retained and production read path unchanged）** | [OmniMemora_DLP_Batch37_Running_Shadow_Validation_Closeout_2026-04-25.md](./OmniMemora_DLP_Batch37_Running_Shadow_Validation_Closeout_2026-04-25.md) |
| **DLP Batch 38 - Archive Fallback Simulation Contract** | **已收口 ✓（diagnostic-only fallback simulation for source-missing resolution; production read path unchanged）** | [OmniMemora_DLP_Batch38_Archive_Fallback_Simulation_Contract_Closeout_2026-04-25.md](./OmniMemora_DLP_Batch38_Archive_Fallback_Simulation_Contract_Closeout_2026-04-25.md) |
| **DLP Batch 39 - Fallback Simulation Running Validation** | **已收口 ✓（adapter+ui promoted; fallback simulation passed; source retained and no archive fallback switch）** | [OmniMemora_DLP_Batch39_Fallback_Simulation_Running_Validation_Closeout_2026-04-25.md](./OmniMemora_DLP_Batch39_Fallback_Simulation_Running_Validation_Closeout_2026-04-25.md) |
| **DLP Batch 40 - Source Quarantine Readiness Plan** | **已收口 ✓（readiness_plan_only quarantine candidate + transaction preview + approval/gate requirements; no source move）** | [OmniMemora_DLP_Batch40_Source_Quarantine_Readiness_Plan_Closeout_2026-04-25.md](./OmniMemora_DLP_Batch40_Source_Quarantine_Readiness_Plan_Closeout_2026-04-25.md) |
| **DLP Batch 41 - Source Quarantine Readiness Running Validation** | **已收口 ✓（adapter+ui promoted; readiness plan ready_for_approval; planned target not created; source retained; stop before actual quarantine）** | [OmniMemora_DLP_Batch41_Source_Quarantine_Readiness_Running_Validation_Closeout_2026-04-25.md](./OmniMemora_DLP_Batch41_Source_Quarantine_Readiness_Running_Validation_Closeout_2026-04-25.md) |
| **DLP Batch 42 - Guarded Source Quarantine Executor** | **已收口 ✓（single_artifact_quarantine_only executor with active-source guard; blocked records do not move source）** | [OmniMemora_DLP_Batch42_Guarded_Source_Quarantine_Executor_Closeout_2026-04-25.md](./OmniMemora_DLP_Batch42_Guarded_Source_Quarantine_Executor_Closeout_2026-04-25.md) |
| **DLP Batch 43 - Quarantine + Conditional Restore API/Health Surface** | **已收口 ✓（quarantine move-one/latest and restore pilot run/latest endpoints; no delete/compress/batch/production overwrite endpoint）** | [OmniMemora_DLP_Batch43_Quarantine_Restore_API_Health_Surface_Closeout_2026-04-25.md](./OmniMemora_DLP_Batch43_Quarantine_Restore_API_Health_Surface_Closeout_2026-04-25.md) |
| **DLP Batch 44 - Running Source Quarantine Safe Block Validation** | **已收口 ✓（adapter+ui promoted; active compile_events candidate blocked; source retained; planned quarantine target absent）** | [OmniMemora_DLP_Batch44_Running_Source_Quarantine_Safe_Block_Validation_Closeout_2026-04-25.md](./OmniMemora_DLP_Batch44_Running_Source_Quarantine_Safe_Block_Validation_Closeout_2026-04-25.md) |
| **DLP Batch 45 - Conditional Restore Pilot Blocked** | **已收口 ✓（restore pilot blocked_no_successful_quarantine after safe block; staging-only contract preserved）** | [OmniMemora_DLP_Batch45_Conditional_Restore_Pilot_Blocked_Closeout_2026-04-25.md](./OmniMemora_DLP_Batch45_Conditional_Restore_Pilot_Blocked_Closeout_2026-04-25.md) |
| **DLP Batch 46 - Non-Active Candidate Selector** | **已收口 ✓（selector-only report separates archive-eligible from quarantine-safe non-active candidates）** | [OmniMemora_DLP_Batch46_Non_Active_Candidate_Selector_Closeout_2026-04-25.md](./OmniMemora_DLP_Batch46_Non_Active_Candidate_Selector_Closeout_2026-04-25.md) |
| **DLP Batch 47 - Non-Active Candidate API + Health Surface** | **已收口 ✓（18011 report read/rebuild + status summary; no execute/move/delete/compress endpoint）** | [OmniMemora_DLP_Batch47_Non_Active_Candidate_API_Health_Surface_Closeout_2026-04-25.md](./OmniMemora_DLP_Batch47_Non_Active_Candidate_API_Health_Surface_Closeout_2026-04-25.md) |
| **DLP Batch 48 - Non-Active Candidate Running Validation** | **已收口 ✓（adapter+ui promoted; 35 forbidden active/control candidates + 1 plausible archive_pilot_copy; no source mutation）** | [OmniMemora_DLP_Batch48_Non_Active_Candidate_Running_Validation_Closeout_2026-04-25.md](./OmniMemora_DLP_Batch48_Non_Active_Candidate_Running_Validation_Closeout_2026-04-25.md) |
| **DLP Batch 49 - Non-Active Quarantine Readiness Plan** | **已收口 ✓（selector-approved archive_pilot_copy produces readiness plan; no source/copy movement）** | [OmniMemora_DLP_Batch49_Non_Active_Quarantine_Readiness_Plan_Closeout_2026-04-25.md](./OmniMemora_DLP_Batch49_Non_Active_Quarantine_Readiness_Plan_Closeout_2026-04-25.md) |
| **DLP Batch 50 - Non-Active Quarantine API + Health Surface** | **已收口 ✓（18011 readiness read/rebuild + status summary; no execute/move/delete/compress endpoint）** | [OmniMemora_DLP_Batch50_Non_Active_Quarantine_API_Health_Surface_Closeout_2026-04-25.md](./OmniMemora_DLP_Batch50_Non_Active_Quarantine_API_Health_Surface_Closeout_2026-04-25.md) |
| **DLP Batch 51 - Non-Active Quarantine Readiness Running Validation** | **已收口 ✓（adapter+ui promoted; archive_pilot_copy readiness ready_for_operator_approval; planned target absent; no source mutation）** | [OmniMemora_DLP_Batch51_Non_Active_Quarantine_Readiness_Running_Validation_Closeout_2026-04-25.md](./OmniMemora_DLP_Batch51_Non_Active_Quarantine_Readiness_Running_Validation_Closeout_2026-04-25.md) |
| **DLP Batch 52 - Non-Active Copy Execution Gate** | **已收口 ✓（gate-only contract for selector-approved archive copy; no source move/delete/compress/read-path switch）** | [OmniMemora_DLP_Batch52_Non_Active_Copy_Execution_Gate_Closeout_2026-04-25.md](./OmniMemora_DLP_Batch52_Non_Active_Copy_Execution_Gate_Closeout_2026-04-25.md) |
| **DLP Batch 53 - Non-Active Copy Gate API + Health Surface** | **已收口 ✓（18011 gate read/rebuild + status summary; no execute/move endpoint）** | [OmniMemora_DLP_Batch53_Non_Active_Copy_Gate_API_Health_Surface_Closeout_2026-04-25.md](./OmniMemora_DLP_Batch53_Non_Active_Copy_Gate_API_Health_Surface_Closeout_2026-04-25.md) |
| **DLP Batch 54 - Non-Active Copy Gate Running Validation** | **已收口 ✓（adapter+ui promoted; stale approval hash blocks gate; quarantine movement not started）** | [OmniMemora_DLP_Batch54_Non_Active_Copy_Gate_Running_Validation_Closeout_2026-04-25.md](./OmniMemora_DLP_Batch54_Non_Active_Copy_Gate_Running_Validation_Closeout_2026-04-25.md) |
| **DLP Batch 55 - Non-Active Copy Quarantine Executor** | **已收口 ✓（single archive_pilot_copy quarantine executor; source evidence retained）** | [OmniMemora_DLP_Batch55_Non_Active_Copy_Quarantine_Executor_Closeout_2026-04-25.md](./OmniMemora_DLP_Batch55_Non_Active_Copy_Quarantine_Executor_Closeout_2026-04-25.md) |
| **DLP Batch 56 - Non-Active Copy Quarantine API + Health Surface** | **已收口 ✓（18011 non-active move-one/latest + health summary; no source/delete/compress/batch endpoint）** | [OmniMemora_DLP_Batch56_Non_Active_Copy_Quarantine_API_Health_Surface_Closeout_2026-04-25.md](./OmniMemora_DLP_Batch56_Non_Active_Copy_Quarantine_API_Health_Surface_Closeout_2026-04-25.md) |
| **DLP Batch 57 - Quarantined Copy Shadow Restore Diagnostics** | **已收口 ✓（shadow/readiness diagnostics resolve quarantined non-active copy by lineage checksum）** | [OmniMemora_DLP_Batch57_Quarantined_Copy_Shadow_Restore_Diagnostics_Closeout_2026-04-25.md](./OmniMemora_DLP_Batch57_Quarantined_Copy_Shadow_Restore_Diagnostics_Closeout_2026-04-25.md) |
| **DLP Batch 58 - Non-Active Copy Quarantine Running Validation** | **已收口 ✓（adapter+ui promoted; archive_pilot_copy moved to non-active quarantine; source retained; staging restore passed）** | [OmniMemora_DLP_Batch58_Non_Active_Copy_Quarantine_Running_Validation_Closeout_2026-04-25.md](./OmniMemora_DLP_Batch58_Non_Active_Copy_Quarantine_Running_Validation_Closeout_2026-04-25.md) |
| **DLP Batch 59 - Shadow Readthrough After Non-Active Quarantine** | **已收口 ✓（readthrough passed via non_active_quarantine lineage; production read path unchanged）** | [OmniMemora_DLP_Batch59_Shadow_Readthrough_After_Non_Active_Quarantine_Closeout_2026-04-25.md](./OmniMemora_DLP_Batch59_Shadow_Readthrough_After_Non_Active_Quarantine_Closeout_2026-04-25.md) |
| **DLP Batch 60 - Stage 0-19 Total Closeout** | **已收口 ✓（Stage 0–19 baseline frozen; single non-active copy quarantine validated; source evidence retained; destructive/archive-at-scale not started）** | [OmniMemora_DLP_Mainline_Stage0_19_Closeout_2026-04-25.md](./OmniMemora_DLP_Mainline_Stage0_19_Closeout_2026-04-25.md) |
| **DLP Batch 61 - Safety Invariants Repo-Test Hardening** | **已收口 ✓（23 safety invariant tests added; no product behaviour change; one minimal None-guard fix in archive_restore_pilot）** | [test_data_lifecycle_safety_invariants.py](../../../../5_connectors/adapter/tests/test_data_lifecycle_safety_invariants.py) |
| **DLP Batch 62 - Running Baseline Revalidation** | **已收口 ✓（18011 running diagnostics verified; source_move_executed=false; non_active_copy_move_executed=true; readthrough.status=passed; lineage_checksum_match=true）** | — |
| **DLP Batch 63 - Active Docs Sync and Next-Line Freeze** | **已收口 ✓（README updated; next-line placeholder: archive-at-scale readiness design only）** | — |
| **RES-001 Raw Evidence Segmentation Mainline** | **已收口 ✓（observe-only running validation passed; legacy source retained; archive-at-scale execution still not started）** | [OmniMemora_RES001_Batch4_5_Running_Validation_Closeout_2026-04-25.md](./OmniMemora_RES001_Batch4_5_Running_Validation_Closeout_2026-04-25.md) |
| **RES-002 Meter Storage Governance Mainline** | **已收口 ✓（meter storage v2 mirror introduced; legacy authoritative retained; running parity passed; read-path switch deferred）** | [OmniMemora_RES002_Batch7_8_Running_Validation_Closeout_2026-04-25.md](./OmniMemora_RES002_Batch7_8_Running_Validation_Closeout_2026-04-25.md) |
| **RES-003 Narrow Request Meter Read-Path Switch** | **已收口 ✓（request meter sqlite-first + legacy fallback passed; request_evidence/metrics remain legacy-authoritative）** | [OmniMemora_RES003_Batch4_Request_Meter_ReadPath_Running_Validation_Closeout_2026-04-25.md](./OmniMemora_RES003_Batch4_Request_Meter_ReadPath_Running_Validation_Closeout_2026-04-25.md) |
| **RES-004 Request Evidence Meter Read-Path Switch** | **已收口 ✓（request_evidence sqlite-first + legacy fallback passed; metrics/status read model remain legacy-authoritative）** | [OmniMemora_RES004_Request_Evidence_Meter_ReadPath_Running_Validation_Closeout_2026-04-25.md](./OmniMemora_RES004_Request_Evidence_Meter_ReadPath_Running_Validation_Closeout_2026-04-25.md) |
| **RES-005 Metrics Residual Meter Read-Path Switch** | **已收口 ✓（metrics residual sqlite-first + legacy fallback passed; status read model remains legacy-authoritative）** | [OmniMemora_RES005_Metrics_Residual_Meter_ReadPath_Running_Validation_Closeout_2026-04-25.md](./OmniMemora_RES005_Metrics_Residual_Meter_ReadPath_Running_Validation_Closeout_2026-04-25.md) |
| **RES-006 Status Read Model Meter Read-Path Switch** | **已收口 ✓（status read model sqlite-first + legacy fallback passed; /agents/control schema and truth semantics unchanged）** | [OmniMemora_RES006_Status_ReadModel_Meter_ReadPath_Running_Validation_Closeout_2026-04-25.md](./OmniMemora_RES006_Status_ReadModel_Meter_ReadPath_Running_Validation_Closeout_2026-04-25.md) |
| **RES-007 Meter Storage Migration Closeout and Legacy Cleanup Readiness Freeze** | **已收口 ✓（RES-001..RES-006 baseline closed; sqlite-first read paths passed; legacy cleanup not started）** | [OmniMemora_RES001_006_Storage_Governance_Baseline_Closeout_2026-04-25.md](./OmniMemora_RES001_006_Storage_Governance_Baseline_Closeout_2026-04-25.md) |
| **RES-008 Legacy Meter Cleanup Readiness Design** | **已收口 ✓（legacy meter cleanup readiness designed; cleanup execution not started）** | [OmniMemora_RES008_Legacy_Meter_Cleanup_Readiness_Report_Gate_Design_2026-04-25.md](./OmniMemora_RES008_Legacy_Meter_Cleanup_Readiness_Report_Gate_Design_2026-04-25.md) |
| **RES-009 Legacy Meter Cleanup Preview Only** | **已收口 ✓（legacy meter cleanup preview generated; cleanup execution not started）** | [OmniMemora_RES009_Legacy_Meter_Cleanup_Preview_Running_Validation_Closeout_2026-04-25.md](./OmniMemora_RES009_Legacy_Meter_Cleanup_Preview_Running_Validation_Closeout_2026-04-25.md) |
| **RES-010 Backup Export Preview/Readiness Only** | **已收口 ✓（legacy meter backup export readiness planned; backup export execution not started; cleanup execution not started）** | [OmniMemora_RES010_Legacy_Meter_Backup_Export_Readiness_Running_Validation_Closeout_2026-04-25.md](./OmniMemora_RES010_Legacy_Meter_Backup_Export_Readiness_Running_Validation_Closeout_2026-04-25.md) |
| **RES-011 Backup Export Execution Gate Design Only** | **已收口 ✓（backup export execution gate designed; backup export execution not started; cleanup execution not started）** | [OmniMemora_RES011_Backup_Export_Execution_Gate_Design_2026-04-25.md](./OmniMemora_RES011_Backup_Export_Execution_Gate_Design_2026-04-25.md) |
| **RES-012 Backup Export Dry-Run Preview / Non-Destructive Planning** | **已收口 ✓（legacy meter backup export dry-run preview generated; backup export execution not started; cleanup execution not started）** | [OmniMemora_RES012_Legacy_Meter_Backup_Export_Dry_Run_Preview_Running_Validation_Closeout_2026-04-25.md](./OmniMemora_RES012_Legacy_Meter_Backup_Export_Dry_Run_Preview_Running_Validation_Closeout_2026-04-25.md) |
| **RES-013 Backup Export Approval Template / Export Package Manifest Planning** | **已收口 ✓（backup export approval template and package manifest preview generated; backup export execution not started; cleanup execution not started）** | [OmniMemora_RES013_Backup_Export_Approval_Template_Package_Manifest_Running_Validation_Closeout_2026-04-25.md](./OmniMemora_RES013_Backup_Export_Approval_Template_Package_Manifest_Running_Validation_Closeout_2026-04-25.md) |
| **RES-014 Backup Export Execution Gate Implementation Candidate** | **已收口 ✓（backup export execution gate implemented; backup export execution not started; cleanup execution not started）** | [OmniMemora_RES014_Backup_Export_Execution_Gate_Running_Validation_Closeout_2026-04-25.md](./OmniMemora_RES014_Backup_Export_Execution_Gate_Running_Validation_Closeout_2026-04-25.md) |
| **RES-015 Backup Export Execution Proposal Only** | **已收口 ✓（backup export execution proposal generated; backup export execution not started; cleanup execution not started）** | [OmniMemora_RES015_Backup_Export_Execution_Proposal_Running_Validation_Closeout_2026-04-25.md](./OmniMemora_RES015_Backup_Export_Execution_Proposal_Running_Validation_Closeout_2026-04-25.md) |
| **RES-016 Backup Export Execution Decision Checkpoint** | **已收口 ✓（backup export execution decision checkpoint recorded; backup export execution not started; cleanup execution not started）** | [OmniMemora_RES016_Backup_Export_Execution_Decision_Checkpoint_2026-04-26.md](./OmniMemora_RES016_Backup_Export_Execution_Decision_Checkpoint_2026-04-26.md) |
| **RES-016A Running Alignment + Parity Repair Preflight** | **已收口 ✓（running alignment and parity preflight completed; backup export execution not started; cleanup execution not started; critical_mismatch_count=0）** | [OmniMemora_RES016A_Running_Alignment_Parity_Preflight_2026-04-26.md](./OmniMemora_RES016A_Running_Alignment_Parity_Preflight_2026-04-26.md) |
| **RES-017 Single Backup Export Copy Pilot** | **已收口 ✓（single backup export copy pilot completed; source retained; cleanup execution not started）** | [OmniMemora_RES017_Single_Backup_Export_Copy_Pilot_Running_Validation_Closeout_2026-04-26.md](./OmniMemora_RES017_Single_Backup_Export_Copy_Pilot_Running_Validation_Closeout_2026-04-26.md) |
| **RES-018 Backup Export Restore/Readback Validation** | **已收口 ✓（backup export restore/readback validation passed; source retained; cleanup execution not started; validation-only; no production restore/read-path switch/delete/move/compress/truncate）** | [OmniMemora_RES018_Backup_Export_Restore_Readback_Validation_Closeout_2026-04-26.md](./OmniMemora_RES018_Backup_Export_Restore_Readback_Validation_Closeout_2026-04-26.md) |
| **RES-018A Restore/Readback Hash Contract Hardening** | **已收口 ✓（restore/readback hash contract hardened; backup export restore/readback validation still passed; cleanup execution not started）** | [OmniMemora_RES018A_Restore_Readback_Hash_Contract_Hardening_2026-04-26.md](./OmniMemora_RES018A_Restore_Readback_Hash_Contract_Hardening_2026-04-26.md) |
| **RES-019 Legacy Meter Cleanup Decision Checkpoint** | **已收口 ✓（legacy meter cleanup decision checkpoint recorded; cleanup execution not started; delete/move/compress/truncate execution not started）** | [OmniMemora_RES019_Legacy_Meter_Cleanup_Decision_Checkpoint_2026-04-26.md](./OmniMemora_RES019_Legacy_Meter_Cleanup_Decision_Checkpoint_2026-04-26.md) |
| **RES-020 Cleanup Execution Gate Contract** | **已收口 ✓（cleanup execution gate introduced; default blocked with cleanup_allowed=false and rollback_required=true; no cleanup execute/delete/move/compress/truncate endpoint; running alignment repaired/revalidated against committed HEAD）** | [OmniMemora_RES020_021_022_Cleanup_Gate_Transaction_Rollback_Closeout_2026-04-26.md](./OmniMemora_RES020_021_022_Cleanup_Gate_Transaction_Rollback_Closeout_2026-04-26.md) |
| **RES-021 Cleanup Transaction Preview** | **已收口 ✓（transaction preview introduced with retain/eligible_for_future_cleanup/blocked semantics; execution_allowed=false and preview-only contract preserved; running alignment repaired/revalidated against committed HEAD）** | [OmniMemora_RES020_021_022_Cleanup_Gate_Transaction_Rollback_Closeout_2026-04-26.md](./OmniMemora_RES020_021_022_Cleanup_Gate_Transaction_Rollback_Closeout_2026-04-26.md) |
| **RES-022 Rollback/Readback Drill** | **已收口 ✓（rollback/readback drill introduced; staging-only restore validates readability/checksum while source retained and production path unchanged; running alignment repaired/revalidated against committed HEAD）** | [OmniMemora_RES020_021_022_Cleanup_Gate_Transaction_Rollback_Closeout_2026-04-26.md](./OmniMemora_RES020_021_022_Cleanup_Gate_Transaction_Rollback_Closeout_2026-04-26.md) |
| **RES-023 Single Legacy Meter Cleanup Pilot** | **已收口 ✓（single-file reversible quarantine pilot executed; source moved to quarantine; delete/compress/truncate/batch cleanup not started）** | [OmniMemora_RES023_Single_Legacy_Meter_Cleanup_Pilot_Running_Validation_Closeout_2026-04-26.md](./OmniMemora_RES023_Single_Legacy_Meter_Cleanup_Pilot_Running_Validation_Closeout_2026-04-26.md) |
| **RES-024 Post-Pilot Stability Window** | **已收口 ✓（single-file cleanup pilot stability window passed; cleanup scope expansion not started）** | [OmniMemora_RES024_Post_Pilot_Stability_Window_Closeout_2026-04-26.md](./OmniMemora_RES024_Post_Pilot_Stability_Window_Closeout_2026-04-26.md) |
| **RES-025 Cleanup Scale-Up Readiness Design** | **已收口 ✓（cleanup scale-up readiness designed; cleanup scope expansion not started）** | [OmniMemora_RES025_Cleanup_Scaleup_Readiness_Closeout_2026-04-26.md](./OmniMemora_RES025_Cleanup_Scaleup_Readiness_Closeout_2026-04-26.md) |
| **RES-026 Cleanup Operator Decision Checkpoint** | **已收口 ✓（cleanup operator decision checkpoint recorded; cleanup scope expansion not started）** | [OmniMemora_RES026_Cleanup_Operator_Decision_Checkpoint_2026-04-26.md](./OmniMemora_RES026_Cleanup_Operator_Decision_Checkpoint_2026-04-26.md) |
| **RES-027 Repeatable Cleanup Pilot Protocol** | **已收口 ✓（repeatable cleanup pilot protocol designed; second-file pilot execution not started; cleanup scope expansion not started）** | [OmniMemora_RES027_Second_File_Pilot_Proposal_Freeze_2026-04-26.md](./OmniMemora_RES027_Second_File_Pilot_Proposal_Freeze_2026-04-26.md) |
| **RES-027 Repeatable Cleanup Pilot Protocol SPEC** | **已收口 ✓（proposal-only contract fixed; second-file pilot requires explicit approval）** | [OmniMemora_RES027_Repeatable_Cleanup_Pilot_Protocol_SPEC_2026-04-26.md](./OmniMemora_RES027_Repeatable_Cleanup_Pilot_Protocol_SPEC_2026-04-26.md) |
| **RES-027A Repeatable Cleanup Pilot Protocol Running Validation** | **已收口 ✓（repeatable cleanup pilot protocol running-validated; second-file pilot execution not started; cleanup scope expansion not started）** | [OmniMemora_RES027A_Repeatable_Cleanup_Pilot_Protocol_Running_Validation_2026-04-26.md](./OmniMemora_RES027A_Repeatable_Cleanup_Pilot_Protocol_Running_Validation_2026-04-26.md) |
| **RES-027B Meter Parity Degraded Root-Cause Diagnosis** | **已收口 ✓（meter parity degraded root cause diagnosed; second-file pilot execution not started; cleanup scope expansion not started; RES-028 blocked）** | [OmniMemora_RES027B_Meter_Parity_Degraded_Root_Cause_Diagnosis_2026-04-27.md](./OmniMemora_RES027B_Meter_Parity_Degraded_Root_Cause_Diagnosis_2026-04-27.md) |
| **RES-027C Meter Parity Contract Repair** | **已收口 ✓（meter parity contract separates semantic provenance drift from critical business drift; cleanup scope expansion not started）** | [OmniMemora_RES027C_Meter_Parity_Contract_Repair_Closeout_2026-04-27.md](./OmniMemora_RES027C_Meter_Parity_Contract_Repair_Closeout_2026-04-27.md) |
| **RES-027C.1 Running Validation and Worktree Hygiene** | **已记录（running validation attempted; parity remains degraded; RES-028 remains blocked; cleanup scope expansion not started）** | [OmniMemora_RES027C1_Running_Validation_Worktree_Hygiene_2026-04-27.md](./OmniMemora_RES027C1_Running_Validation_Worktree_Hygiene_2026-04-27.md) |
| **RES-027D Meter Parity Timestamp Semantics Repair** | **已收口 ✓（meter parity timestamp semantics repaired; RES-028 remains blocked until running parity is clean; cleanup scope expansion not started）** | [OmniMemora_RES027D_Meter_Parity_Timestamp_Semantics_Repair_Closeout_2026-04-27.md](./OmniMemora_RES027D_Meter_Parity_Timestamp_Semantics_Repair_Closeout_2026-04-27.md) |
| **RES-027D.1 Running Stability Re-Sampling** | **已收口 ✓（running stability re-sampling passed; RES-028 remains unopened）** | [OmniMemora_RES027D1_Running_Stability_Resampling_2026-04-27.md](./OmniMemora_RES027D1_Running_Stability_Resampling_2026-04-27.md) |
| **RES-027E Running Latency Diagnosis** | **已收口 ✓（running latency source diagnosed; RES-028 remains unopened; cleanup scope expansion not started）** | [OmniMemora_RES027E_Running_Latency_Diagnosis_2026-04-27.md](./OmniMemora_RES027E_Running_Latency_Diagnosis_2026-04-27.md) |
| **RES-027F Parity Read Optimization** | **已收口 ✓（meter parity read path optimized; RES-028 remains unopened; cleanup scope expansion not started）** | [OmniMemora_RES027F_Parity_Read_Optimization_Closeout_2026-04-27.md](./OmniMemora_RES027F_Parity_Read_Optimization_Closeout_2026-04-27.md) |
| **RES-028 Second-File Pilot Approval Readiness** | **已收口 ✓（second-file pilot approval readiness prepared; second-file pilot execution not started; cleanup scope expansion not started）** | [OmniMemora_RES028_Second_File_Pilot_Approval_Readiness_Closeout_2026-04-27.md](./OmniMemora_RES028_Second_File_Pilot_Approval_Readiness_Closeout_2026-04-27.md) |
| **RES-029 Data Maintenance Simplification Freeze** | **已收口 ✓（automatic cleanup expansion paused; manual maintenance surface preferred）** | [OmniMemora_RES029_Data_Maintenance_Simplification_Freeze_2026-04-27.md](./OmniMemora_RES029_Data_Maintenance_Simplification_Freeze_2026-04-27.md) |
| **UXV-001 Personal Value Loop Repair** | **已收口 ✓（dashboard value loop explains current usefulness; RES cleanup expansion paused）** | [OmniMemora_UXV001_Personal_Value_Loop_Repair_Closeout_2026-04-27.md](./OmniMemora_UXV001_Personal_Value_Loop_Repair_Closeout_2026-04-27.md) |
| **Cloud-Local Sync Check (2026-04-30)** | **已记录（local healthy; cloud verification blocked by DNS/timeouts; no phase closeout claim）** | [OmniMemora_Cloud_Local_Sync_Check_2026-04-30.md](./OmniMemora_Cloud_Local_Sync_Check_2026-04-30.md) |
| **Cloudflare Clean Install Closeout** | **已收口 ✓（openviking-site deleted; control-entry reinstalled; candidate pointer reserved）** | [OmniMemora_Cloudflare_Clean_Install_Closeout_2026-04-30.md](./OmniMemora_Cloudflare_Clean_Install_Closeout_2026-04-30.md) |
| **Cloud Platform Stewardship Rule** | **已固定（Codex cloud authority + project isolation + replace-old-iteration rule）** | [OmniMemora_Cloud_Platform_Stewardship_Rule_2026-04-30.md](./OmniMemora_Cloud_Platform_Stewardship_Rule_2026-04-30.md) |
| **Desktop GUI + Codex Managed Attach Sync (2026-05-10)** | **已收口 ✓（Desktop app is current control surface; 5173 retired from service controls; Codex attach uses managed profile/launcher）** | [OmniMemora_Desktop_GUI_Codex_Attach_Sync_Closeout_2026-05-10.md](./OmniMemora_Desktop_GUI_Codex_Attach_Sync_Closeout_2026-05-10.md) |
| Controlled Beta Next Step Engineering Plan | **进行中（historical controlled-beta execution line preserved; active architecture mainline has moved to Data Lifecycle Plane）** | [OmniMemora_Controlled_Beta_Next_Step_Engineering_Plan_2026-04-23.md](./OmniMemora_Controlled_Beta_Next_Step_Engineering_Plan_2026-04-23.md) |

> Cloud Reset `Batch 6.1` is classified as **optional cleanup only** (legacy project physical retire), not a mainline closeout prerequisite.

> 2026-05-10 supersession note: current user control/display is the packaged OmniMemora Desktop app. Historical `5173` records below remain preserved as historical evidence, but `5173` must not be treated as the current desktop GUI dependency or service-control target.

---

## Promotion Evidence Routing

**狀態：** 已收口
**收口日期：** 2026-04-20

### 目標

把「已經成立的 adoption 結果」接進 phase docs、驗證記錄、running reality 宣告規則，形成正式 evidence routing。

### 核心變更

1. **三層落點固定**
   - Layer 1：`tools/verification/logs/promotion_*.log`（原始日誌）
   - Layer 2：`OmniMemora_Adoption_Verification_Records_*.md`（執行記錄）
   - Layer 3：phase6 README / 主計劃（只有正式宣告條件滿足時才寫入）

2. **結果路由矩陣固定**
   - `running_reality_promoted` → 寫 Layer 1 + Layer 2，若 full stack 成功可提升到 Layer 3
   - `running_reality_partial` → 寫 Layer 1 + Layer 2，不得寫 Layer 3
   - `promotion_failed` → 寫 Layer 1 + Layer 2，若觸及主線目標需形成 finding
   - `prerequisite_failed` → 寫 Layer 1 + Layer 2，不自動歸類為產品失敗

3. **正式宣告條件固定**
   - 必須是 `runtime+adapter+ui`
   - `8765/health = 200`, `18011/health = 200`, `5173` 可訪問
   - UI 與 adapter 基本對位成立
   - primary breakpoint = `none`
   - 所有 warning 都是契約化非阻塞

4. **Warning 升級規則固定**
   - 契約化非阻塞 warning：僅有 `adapter plist reality`（API/process 正常時）
   - 未契約化 warning → 自動升級為 finding（至少 P2）

### Evidence Routing 文檔

| 文檔 | 說明 |
|------|------|
| [OmniMemora_Promotion_Evidence_Routing.md](./OmniMemora_Promotion_Evidence_Routing.md) | 完整路由規則、快速參考卡、驗證樣例 |

### 路由驗證樣例

| 場景 | Layer 1 | Layer 2 | Layer 3 |
|------|---------|---------|---------|
| runtime 單組件成功 | ✓ 寫 | ✓ 寫 | ✗ 不寫 |
| adapter 單組件成功（帶 plist warning） | ✓ 寫 | ✓ 寫 | ✗ 不寫 |
| runtime+adapter+ui 全鏈路成功 | ✓ 寫 | ✓ 寫 | ✓ 寫（正式宣告） |

### 後續執行者無需判斷

- promotion 成功後寫哪份記錄 ✓
- 哪些 warning 可以忽略 ✓
- 什麼條件下能在 phase6 中正式宣告成功 ✓

---

## Promotion Workflow Adoption

**狀態：** 已收口
**收口日期：** 2026-04-20

### Adoption 文檔四件套

| 文檔 | 說明 |
|------|------|
| [OmniMemora_Adoption_Contract.md](./OmniMemora_Adoption_Contract.md) | 誰可以用、哪些場景必須用、不該用的場景 |
| [OmniMemora_Promotion_Success_Definition.md](./OmniMemora_Promotion_Success_Definition.md) | runtime/adapter/ui 成功標準、組合標準、失敗定義 |
| [OmniMemora_Adoption_Runbook.md](./OmniMemora_Adoption_Runbook.md) | 入口命令、推薦順序、驗證命令、記錄模板 |
| [OmniMemora_Adoption_Verification_Records_2026-04-20.md](./OmniMemora_Adoption_Verification_Records_2026-04-20.md) | 三批六組驗證記錄 |

### 執行入口

```bash
cd /Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora
./tools/promotion/promotion.sh <target>
```

### 驗證矩陣

| Target | Result |
|--------|--------|
| `runtime` | `running_reality_promoted` |
| `adapter` | `running_reality_promoted` |
| `ui` | `running_reality_promoted` |
| `runtime+adapter` | `running_reality_promoted` |
| `adapter+ui` | `running_reality_promoted` |
| `runtime+adapter+ui` | `running_reality_promoted` |

### 已知非阻塞 Warning

| 組件 | Warning |
|------|---------|
| Adapter | `plist reality` 未通過 launchctl 檢查（launchd 重啟覆蓋可見性，API/process 正常） |

---

## Promotion Workflow Usage Governance

**狀態：** 已收口
**收口日期：** 2026-04-20
**文檔位置：** `docs/phase6/PROMOTION_USAGE_GOVERNANCE.md`

### 核心變更

1. **使用邊界三元組**
   - 必須走 promotion：runtime/adapter/UI 變更影響在線行為
   - 禁止繞過：手工複製、繞過 launchd、不經記錄回填
   - 不需要走：純文檔、未準備提升到 running reality

2. **執行前後檢查項固化**
   - 執行前：15 項強制確認
   - 執行後：結構化日誌 + 三層驗證 + 記錄回填

3. **失敗即停住規則**
   - 單組件失敗 = 停止，不繼續組合驗證
   - 組合失敗 = 停止，不並行修多個面
   - warning 未契約化 = 先升級 finding，再繼續

4. **宣告職責規則**
   - 運行成功 ≠ 階段完成
   - 三層宣告（Layer 1/2/3）職責分離

### Governance Validation Record

| 驗證日期 | 場景 | 結果 |
|----------|------|------|
| 2026-04-20 | adapter-only 真實場景 | PASS |

Validation Record：`docs/phase6/adoption_verification/20260420_adapter_only_validation.md`

---

## Promotion Outcome Reporting

**狀態：** 已收口
**收口日期：** 2026-04-20
**文檔位置：** `OmniMemora_Promotion_Outcome_Reporting_Contract.md`

### 目標

定義 promotion 結果的讀者面向報告格式，規範：
- 何時只寫 record（Layer 2）
- 何時允許提升為 phase 結論（Layer 3）
- 何時允許提升到根 README

### 核心約定

1. **Canonical Outcome Vocabulary**：四個固定值，`running_reality_promoted` / `running_reality_partial` / `promotion_failed` / `prerequisite_failed`
2. **Layer 2 標準欄位**：`target` / `datetime` / `repo_revision` / `result` / `primary_breakpoint` / `warning_status` / `declaration_status`
3. **Declaration Status 判定**：執行 §5 決策樹，產出 `record only` / `phase_conclusion_allowed` / `readme_surface_allowed`
4. **Layer 3 觸發條件**：只有 `readme_surface_allowed` 時才能寫 phase plan/README
5. **Root README 觸發條件**：`readme_surface_allowed` + 里程碑判定

### 驗證結果

| # | 日誌 | result | declaration_status | 結論 |
|---|------|--------|-------------------|------|
| R-1 | `promotion_20260420_000136.log` (runtime only) | `running_reality_promoted` | `record only` | ✓ PASS |
| R-2 | `promotion_20260420_000143.log` (adapter only, plist warning) | `running_reality_promoted` | `record only` | ✓ PASS |
| R-3 | `promotion_20260420_000151.log` (runtime+adapter+ui full stack) | `running_reality_promoted` | `readme_surface_allowed` | ✓ PASS |
| R-4 | `promotion_20260420_004133.log` (adapter+ui) | `running_reality_promoted` | `phase_conclusion_allowed` | ✓ PASS |
| R-5 | `promotion_20260420_000203.log` (adapter only, plist warning) | `running_reality_promoted` | `record only` | ✓ PASS |

### 後續執行者無需判斷

- 某個 result 該寫哪個 Layer？✓ 明確
- declaration_status 怎麼判定？✓ 決策樹已給出
- 什麼時候寫 root README？✓ 只有里程碑 + readme_surface_allowed
