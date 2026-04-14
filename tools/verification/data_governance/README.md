# Experiment Data Governance Toolkit

This toolkit manages OmniMemora token-savings experiment data with production-grade controls.

## Included Scripts

- `run_all.ps1`
  - One-command workflow: archive -> verify -> heartbeat -> anonymized export.
- `run_meter_archive.ps1`
  - Creates immutable snapshot archives from meter data files.
  - Writes metadata and SHA256 manifest.
- `verify_meter_archive.ps1`
  - Verifies archive file integrity against manifest checksums.
- `check_meter_heartbeat.ps1`
  - Checks meter write freshness using latest file write time.
  - Supports CI/cron alert style exit codes.
- `export_meter_anonymized.ps1`
  - Exports anonymized analysis-ready CSV/JSON from meter index.
  - Hashes request/query fields with a salt.

## Default Paths

- Source meter data directory auto-resolution order:
  1. `OMNIMEMORA_METER_DATA_DIR`
  2. `<repo>\5_connectors\data`
  3. `<repo>\5_connectors\adapter\data`
- Archive root:
  - `<repo>\tools\verification\data_governance\archives`
- Export root:
  - `<repo>\tools\verification\data_governance\exports`

## Typical Usage

```powershell
# 0) One-command full workflow (recommended)
powershell -ExecutionPolicy Bypass -File .\tools\verification\data_governance\run_all.ps1 -RunLabel "daily" -Tenant all -Salt "replace-me"

# 1) Snapshot archive (immutable evidence)
powershell -ExecutionPolicy Bypass -File .\tools\verification\data_governance\run_meter_archive.ps1

# 2) Verify checksum integrity
powershell -ExecutionPolicy Bypass -File .\tools\verification\data_governance\verify_meter_archive.ps1

# 3) Heartbeat freshness check (15 min threshold)
powershell -ExecutionPolicy Bypass -File .\tools\verification\data_governance\check_meter_heartbeat.ps1 -StaleAfterMinutes 15

# 4) Anonymized export for paper analysis
powershell -ExecutionPolicy Bypass -File .\tools\verification\data_governance\export_meter_anonymized.ps1 -Salt "replace-me"
```
