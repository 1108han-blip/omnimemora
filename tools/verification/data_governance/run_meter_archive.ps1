param(
    [string]$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..\..")).Path,
    [string]$MeterDataDir = "",
    [string]$ArchiveRoot = "",
    [string]$RunLabel = "manual",
    [switch]$IncludeRawLogs
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

function Get-Sha256 {
    param([string]$Path)
    return (Get-FileHash -Algorithm SHA256 -Path $Path).Hash.ToLowerInvariant()
}

$meterDir = Resolve-MeterDataDir -ProjectRoot $ProjectRoot -MeterDataDirInput $MeterDataDir
if (-not $ArchiveRoot) {
    $ArchiveRoot = Join-Path $ProjectRoot "tools\verification\data_governance\archives"
}

$utcNow = [DateTime]::UtcNow
$stamp = $utcNow.ToString("yyyyMMdd_HHmmss")
$archiveDirName = "archive_${stamp}_$RunLabel"
$archiveDir = Join-Path $ArchiveRoot $archiveDirName
$dataOut = Join-Path $archiveDir "data"

New-Item -ItemType Directory -Path $dataOut -Force | Out-Null

$meterFiles = Get-ChildItem -Path $meterDir -File | Where-Object { $_.Name -eq "meters_index.json" -or $_.Name -like "meters_*.json" }
if (-not $meterFiles) {
    throw "No meter files found in $meterDir"
}

foreach ($f in $meterFiles) {
    Copy-Item -LiteralPath $f.FullName -Destination (Join-Path $dataOut $f.Name) -Force
}

if ($IncludeRawLogs) {
    $rawLogDir = Join-Path $ProjectRoot "tools\verification\logs"
    if (Test-Path $rawLogDir) {
        $logsOut = Join-Path $archiveDir "logs"
        New-Item -ItemType Directory -Path $logsOut -Force | Out-Null
        Get-ChildItem -Path $rawLogDir -File | Copy-Item -Destination $logsOut -Force
    }
}

$manifest = @()
foreach ($f in (Get-ChildItem -Path $dataOut -File | Sort-Object Name)) {
    $manifest += [PSCustomObject]@{
        file = $f.Name
        bytes = $f.Length
        sha256 = Get-Sha256 -Path $f.FullName
        last_write_utc = $f.LastWriteTimeUtc.ToString("o")
    }
}

$metadata = [PSCustomObject]@{
    archive_id = $archiveDirName
    created_at_utc = $utcNow.ToString("o")
    created_at_local = (Get-Date).ToString("o")
    timezone = (Get-TimeZone).Id
    run_label = $RunLabel
    project_root = $ProjectRoot
    meter_data_source = $meterDir
    meter_files_count = $manifest.Count
    include_raw_logs = [bool]$IncludeRawLogs
    note = "Immutable archive for experiment evidence."
}

$metadata | ConvertTo-Json -Depth 6 | Set-Content -Path (Join-Path $archiveDir "metadata.json") -Encoding UTF8
$manifest | ConvertTo-Json -Depth 6 | Set-Content -Path (Join-Path $archiveDir "manifest.sha256.json") -Encoding UTF8

Write-Output ("ARCHIVE_DIR=" + $archiveDir)
Write-Output ("METER_SOURCE=" + $meterDir)
Write-Output ("FILES=" + $manifest.Count)

