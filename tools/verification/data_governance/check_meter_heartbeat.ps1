param(
    [string]$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..\..")).Path,
    [string]$MeterDataDir = "",
    [int]$StaleAfterMinutes = 15
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

$meterDir = Resolve-MeterDataDir -ProjectRoot $ProjectRoot -MeterDataDirInput $MeterDataDir
$targetFiles = Get-ChildItem -Path $meterDir -File | Where-Object { $_.Name -eq "meters_index.json" -or $_.Name -like "meters_*.json" }
if (-not $targetFiles) { throw "No meter files found in $meterDir" }

$latest = $targetFiles | Sort-Object LastWriteTimeUtc -Descending | Select-Object -First 1
$nowUtc = [DateTime]::UtcNow
$ageMinutes = [math]::Round((New-TimeSpan -Start $latest.LastWriteTimeUtc -End $nowUtc).TotalMinutes, 2)
$healthy = $ageMinutes -le $StaleAfterMinutes

$result = [PSCustomObject]@{
    status = if ($healthy) { "healthy" } else { "stale" }
    stale_after_minutes = $StaleAfterMinutes
    latest_file = $latest.FullName
    latest_write_utc = $latest.LastWriteTimeUtc.ToString("o")
    now_utc = $nowUtc.ToString("o")
    age_minutes = $ageMinutes
    meter_data_dir = $meterDir
}

$result | ConvertTo-Json -Depth 6

if (-not $healthy) {
    exit 2
}

