# EXPERIMENT_DATA_GOVERNANCE_SOP

## Goal

Maintain OmniMemora token-savings data in a paper-grade, auditable, reproducible workflow.

## Scope

- Raw meter persistence:
  - `meters_index.json`
  - `meters_<tenant>.json`
- Archive evidence
- Integrity verification
- Freshness heartbeat
- Anonymized export for analysis

## Operating Rules

1. Raw data is append-only evidence.
2. Raw data is never manually edited.
3. Every analysis run starts from a checksum-verified archive.
4. Paper analysis uses anonymized export, not raw PII-like fields.

## Standard Runbook

### Fast Path (recommended)

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\verification\data_governance\run_all.ps1 -RunLabel "phase3" -Tenant all -Salt "<paper-secret-salt>"
```

This runs archive, integrity verify, heartbeat, and anonymized export in one command.

### Step 1: Create immutable archive

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\verification\data_governance\run_meter_archive.ps1 -RunLabel "phase3"
```

Outputs:

- `tools/verification/data_governance/archives/archive_<timestamp>_<label>/metadata.json`
- `.../manifest.sha256.json`
- `.../data/*.json`

### Step 2: Verify integrity

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\verification\data_governance\verify_meter_archive.ps1
```

Expected: `VERIFY_ARCHIVE=PASS`

### Step 3: Heartbeat freshness check

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\verification\data_governance\check_meter_heartbeat.ps1 -StaleAfterMinutes 15
```

Expected JSON: `"status": "healthy"`

### Step 4: Anonymized export for paper

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\verification\data_governance\export_meter_anonymized.ps1 -Tenant all -Salt "<paper-secret-salt>"
```

Outputs:

- `tools/verification/data_governance/exports/meter_anonymized_all_<timestamp>.json`
- `tools/verification/data_governance/exports/meter_anonymized_all_<timestamp>.csv`

## Retention Policy

- Raw evidence archives: keep 180+ days minimum.
- Anonymized paper exports: keep with experiment artifacts indefinitely.
- Keep one salt per study and store it in secure secret manager.

## Quality Gates

- Archive integrity must pass before any summary/report publication.
- Heartbeat must be healthy during active experiments.
- Any mismatch/stale state blocks final acceptance summary.
