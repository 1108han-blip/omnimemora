param()

$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$logDir = Join-Path $projectRoot "tools/verification/logs"
New-Item -ItemType Directory -Path $logDir -Force | Out-Null

$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$reportPath = Join-Path $logDir "phase2_hardcoding_scan_${stamp}.md"

$targets = @(
    (Join-Path $projectRoot "4_core"),
    (Join-Path $projectRoot "5_connectors"),
    (Join-Path $projectRoot "tools"),
    (Join-Path $projectRoot "start.sh"),
    (Join-Path $projectRoot "Makefile"),
    (Join-Path $projectRoot ".env.example")
)

$patterns = @(
    "C:\\\\",
    "localhost",
    "127\.0\.0\.1:8765",
    "127\.0\.0\.1:18011",
    "omnimemora\.exe"
)

$allFiles = @()
foreach ($t in $targets) {
    if (Test-Path $t -PathType Container) {
        $allFiles += Get-ChildItem -Path $t -Recurse -File -ErrorAction SilentlyContinue
    } elseif (Test-Path $t -PathType Leaf) {
        $allFiles += Get-Item -Path $t -ErrorAction SilentlyContinue
    }
}

$allFiles = $allFiles |
    Where-Object {
        $_.FullName -notmatch "\\__pycache__\\" -and
        $_.FullName -notmatch "\\tools\\verification\\logs\\" -and
        $_.Name -ne "nul" -and
        $_.Extension -notin @(".exe", ".dll", ".png", ".jpg", ".jpeg", ".gif", ".zip", ".db", ".sqlite", ".woff", ".woff2", ".pyc")
    }

$hits = @()
foreach ($f in $allFiles) {
    foreach ($p in $patterns) {
        try {
            $m = Select-String -Path $f.FullName -Pattern $p -SimpleMatch:$false -ErrorAction SilentlyContinue
        } catch {
            $m = $null
        }
        if ($m) {
            foreach ($x in $m) {
                $hits += [PSCustomObject]@{
                    path = $x.Path
                    line = $x.LineNumber
                    pattern = $p
                    text = ($x.Line.Trim() -replace "\|", "/")
                }
            }
        }
    }
}

$lines = @()
$lines += "# Phase 2 Hardcoding Scan"
$lines += ""
$lines += "- Timestamp (UTC): $([DateTime]::UtcNow.ToString("yyyy-MM-dd HH:mm:ss"))"
$lines += "- Scope: 4_core, 5_connectors, tools, root startup/config files"
$lines += "- Findings: $($hits.Count)"
$lines += ""
$lines += "## Findings"
$lines += ""
$lines += "| File | Line | Pattern | Snippet |"
$lines += "|---|---:|---|---|"

foreach ($h in $hits | Sort-Object path, line) {
    $rel = $h.path.Replace($projectRoot + "\", "")
    $lines += "| $rel | $($h.line) | $($h.pattern) | $($h.text) |"
}

Set-Content -Path $reportPath -Value $lines -Encoding UTF8
Write-Output $reportPath
