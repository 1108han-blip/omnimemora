param(
    [string]$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..\..")).Path,
    [string]$ArchiveDir = ""
)

$ErrorActionPreference = "Stop"

function Get-Sha256 {
    param([string]$Path)
    return (Get-FileHash -Algorithm SHA256 -Path $Path).Hash.ToLowerInvariant()
}

if (-not $ArchiveDir) {
    $archivesRoot = Join-Path $ProjectRoot "tools\verification\data_governance\archives"
    if (-not (Test-Path $archivesRoot)) { throw "Archives root not found: $archivesRoot" }
    $latest = Get-ChildItem -Path $archivesRoot -Directory | Sort-Object LastWriteTimeUtc -Descending | Select-Object -First 1
    if (-not $latest) { throw "No archives found in $archivesRoot" }
    $ArchiveDir = $latest.FullName
}

$manifestPath = Join-Path $ArchiveDir "manifest.sha256.json"
if (-not (Test-Path $manifestPath)) { throw "Manifest missing: $manifestPath" }

$manifest = Get-Content -Path $manifestPath -Raw | ConvertFrom-Json
$failures = @()

foreach ($entry in $manifest) {
    $filePath = Join-Path (Join-Path $ArchiveDir "data") $entry.file
    if (-not (Test-Path $filePath)) {
        $failures += "MISSING: $($entry.file)"
        continue
    }
    $actual = Get-Sha256 -Path $filePath
    if ($actual -ne $entry.sha256) {
        $failures += "MISMATCH: $($entry.file) expected=$($entry.sha256) actual=$actual"
    }
}

if ($failures.Count -gt 0) {
    Write-Output ("VERIFY_ARCHIVE=FAILED")
    $failures | ForEach-Object { Write-Output $_ }
    exit 2
}

Write-Output ("VERIFY_ARCHIVE=PASS")
Write-Output ("ARCHIVE_DIR=" + $ArchiveDir)
Write-Output ("FILES=" + $manifest.Count)

