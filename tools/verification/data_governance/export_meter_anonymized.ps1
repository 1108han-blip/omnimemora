param(
    [string]$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..\..")).Path,
    [string]$MeterDataDir = "",
    [string]$OutputDir = "",
    [string]$Salt = "omnimemora-default-salt",
    [string]$Tenant = "all"
)

$ErrorActionPreference = "Stop"

function Resolve-MeterDataDir {
    param([string]$ProjectRoot, [string]$MeterDataDirInput)
    if ($MeterDataDirInput -and (Test-Path $MeterDataDirInput)) {
        return (Resolve-Path $MeterDataDirInput).Path
    }
    if ($env:OMNIMEMORA_METER_DATA_DIR -and (Test-Path $env:OMNIMEMORA_METER_DATA_DIR)) {
        return (Resolve-Path $env:OMNIMEMORA_METER_DATA_DIR).Path
    }
    $candidates = @(
        (Join-Path $ProjectRoot "5_connectors\data"),
        (Join-Path $ProjectRoot "5_connectors\adapter\data")
    )
    foreach ($c in $candidates) {
        if (Test-Path $c) { return (Resolve-Path $c).Path }
    }
    throw "Meter data directory not found."
}

function Hash-Value {
    param([string]$InputText, [string]$Salt)
    $bytes = [System.Text.Encoding]::UTF8.GetBytes("$Salt|$InputText")
    $sha = [System.Security.Cryptography.SHA256]::Create()
    try {
        $hashBytes = $sha.ComputeHash($bytes)
        return ($hashBytes | ForEach-Object { $_.ToString("x2") }) -join ""
    }
    finally {
        $sha.Dispose()
    }
}

$meterDir = Resolve-MeterDataDir -ProjectRoot $ProjectRoot -MeterDataDirInput $MeterDataDir
$indexPath = Join-Path $meterDir "meters_index.json"
if (-not (Test-Path $indexPath)) { throw "meters_index.json not found in $meterDir" }

if (-not $OutputDir) {
    $OutputDir = Join-Path $ProjectRoot "tools\verification\data_governance\exports"
}
New-Item -ItemType Directory -Path $OutputDir -Force | Out-Null

$stamp = [DateTime]::UtcNow.ToString("yyyyMMdd_HHmmss")
$jsonOut = Join-Path $OutputDir "meter_anonymized_${Tenant}_${stamp}.json"
$csvOut = Join-Path $OutputDir "meter_anonymized_${Tenant}_${stamp}.csv"

$raw = Get-Content -Path $indexPath -Raw | ConvertFrom-Json
$records = @()
foreach ($p in $raw.PSObject.Properties) {
    $records += $p.Value
}

if ($Tenant -ne "all") {
    $records = $records | Where-Object { $_.tenant -eq $Tenant }
}

$rows = foreach ($r in $records) {
    [PSCustomObject]@{
        timestamp = $r.timestamp
        tenant = $r.tenant
        user_hash = Hash-Value -InputText ([string]$r.user) -Salt $Salt
        agent = $r.agent
        request_id_hash = Hash-Value -InputText ([string]$r.request_id) -Salt $Salt
        query_hash = Hash-Value -InputText ([string]$r.query) -Salt $Salt
        task_type = $r.task_type
        context_bypass = $r.context_bypass
        baseline_tokens = [int]$r.baseline_tokens_estimate
        actual_tokens = [int]$r.actual_tokens_estimate
        saved_tokens = [int]$r.saved_tokens_estimate
        savings_ratio = [double]$r.savings_ratio
        packed_memory_count = [int]$r.packed_memory_count
        local_cards_used = [int]$r.local_cards_used
        remote_candidates_considered = [int]$r.remote_candidates_considered
        remote_candidates_skipped = [int]$r.remote_candidates_skipped
    }
}

$rows | ConvertTo-Json -Depth 6 | Set-Content -Path $jsonOut -Encoding UTF8
$rows | Export-Csv -Path $csvOut -NoTypeInformation -Encoding UTF8

Write-Output ("EXPORT_JSON=" + $jsonOut)
Write-Output ("EXPORT_CSV=" + $csvOut)
Write-Output ("ROWS=" + $rows.Count)

