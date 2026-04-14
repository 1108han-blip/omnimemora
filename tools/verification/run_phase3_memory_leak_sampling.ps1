param(
    [int]$DurationSeconds = 600,
    [int]$RequestIntervalSeconds = 2,
    [int]$SampleIntervalSeconds = 30
)

$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$logDir = Join-Path $projectRoot "tools/verification/logs"
New-Item -ItemType Directory -Path $logDir -Force | Out-Null

$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$reportPath = Join-Path $logDir "phase3_memory_leak_sampling_${stamp}.md"

function Get-PortProcessId {
    param([int]$Port)
    $conn = Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue |
        Where-Object { $_.LocalPort -eq $Port } |
        Select-Object -First 1
    if ($null -eq $conn) { return $null }
    return $conn.OwningProcess
}

function Wait-Health {
    param([string]$Url, [int]$MaxAttempts = 20, [int]$DelayMs = 500)
    for ($i = 0; $i -lt $MaxAttempts; $i++) {
        try {
            Invoke-RestMethod -Method Get -Uri $Url -TimeoutSec 2 | Out-Null
            return $true
        } catch {
            Start-Sleep -Milliseconds $DelayMs
        }
    }
    return $false
}

if (-not (Wait-Health -Url "http://127.0.0.1:8765/health")) {
    throw "Runtime is not healthy on 8765."
}
if (-not (Wait-Health -Url "http://127.0.0.1:18011/health")) {
    throw "Adapter is not healthy on 18011."
}

$runtimePid = Get-PortProcessId -Port 8765
$adapterPid = Get-PortProcessId -Port 18011
if (-not $runtimePid -or -not $adapterPid) {
    throw "Failed to resolve runtime/adapter PID from listening ports."
}

$tenant = "phase3-memleak"
$agent = "codex"
$start = Get-Date
$end = $start.AddSeconds($DurationSeconds)
$nextSampleAt = $start

$requestSuccess = 0
$requestFail = 0
$samples = New-Object System.Collections.Generic.List[Object]

while ((Get-Date) -lt $end) {
    try {
        Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:18011/memory/query" -ContentType "application/json" -Body (@{
            tenant = $tenant
            user = "memleak-user"
            agent = $agent
            query = ("memory leak sampling " + [guid]::NewGuid().ToString("N").Substring(0, 8))
        } | ConvertTo-Json -Depth 6) -TimeoutSec 10 | Out-Null
        $requestSuccess++
    } catch {
        $requestFail++
    }

    $now = Get-Date
    if ($now -ge $nextSampleAt) {
        $r = Get-Process -Id $runtimePid -ErrorAction SilentlyContinue
        $a = Get-Process -Id $adapterPid -ErrorAction SilentlyContinue
        if ($null -ne $r -and $null -ne $a) {
            $samples.Add([PSCustomObject]@{
                t = $now.ToString("HH:mm:ss")
                runtime_ws_mb = [math]::Round($r.WorkingSet64 / 1MB, 2)
                runtime_pm_mb = [math]::Round($r.PrivateMemorySize64 / 1MB, 2)
                adapter_ws_mb = [math]::Round($a.WorkingSet64 / 1MB, 2)
                adapter_pm_mb = [math]::Round($a.PrivateMemorySize64 / 1MB, 2)
            })
        }
        $nextSampleAt = $nextSampleAt.AddSeconds($SampleIntervalSeconds)
    }

    Start-Sleep -Seconds $RequestIntervalSeconds
}

$runtimeAfter = Wait-Health -Url "http://127.0.0.1:8765/health" -MaxAttempts 3 -DelayMs 300
$adapterAfter = Wait-Health -Url "http://127.0.0.1:18011/health" -MaxAttempts 3 -DelayMs 300

$first = $samples[0]
$last = $samples[$samples.Count - 1]
$runtimeDeltaPm = [math]::Round(($last.runtime_pm_mb - $first.runtime_pm_mb), 2)
$adapterDeltaPm = [math]::Round(($last.adapter_pm_mb - $first.adapter_pm_mb), 2)

$totalReq = $requestSuccess + $requestFail
$failRate = if ($totalReq -gt 0) { [math]::Round(($requestFail * 100.0 / $totalReq), 2) } else { 0 }

# Heuristic "no obvious leak" gate for local verification.
$noObviousLeak = ($runtimeDeltaPm -lt 120) -and ($adapterDeltaPm -lt 120) -and $runtimeAfter -and $adapterAfter -and ($failRate -lt 5)

$lines = @()
$lines += "# Phase 3 Memory Leak Sampling"
$lines += ""
$lines += "- Timestamp: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss zzz')"
$lines += "- DurationSeconds: $DurationSeconds"
$lines += "- RequestIntervalSeconds: $RequestIntervalSeconds"
$lines += "- SampleIntervalSeconds: $SampleIntervalSeconds"
$lines += "- Runtime PID: $runtimePid"
$lines += "- Adapter PID: $adapterPid"
$lines += ""
$lines += "## Request Summary"
$lines += ""
$lines += "- request_success: $requestSuccess"
$lines += "- request_fail: $requestFail"
$lines += "- fail_rate_percent: $failRate"
$lines += ""
$lines += "## Memory Delta (Private MB)"
$lines += ""
$lines += "- runtime_private_mb_start: $($first.runtime_pm_mb)"
$lines += "- runtime_private_mb_end: $($last.runtime_pm_mb)"
$lines += "- runtime_private_mb_delta: $runtimeDeltaPm"
$lines += "- adapter_private_mb_start: $($first.adapter_pm_mb)"
$lines += "- adapter_private_mb_end: $($last.adapter_pm_mb)"
$lines += "- adapter_private_mb_delta: $adapterDeltaPm"
$lines += ""
$lines += "## Health After Run"
$lines += ""
$lines += "- runtime_health: $runtimeAfter"
$lines += "- adapter_health: $adapterAfter"
$lines += ""
$lines += "## Verdict"
$lines += ""
$lines += "- no_obvious_memory_leak: $noObviousLeak"
$lines += ""
$lines += "## Samples"
$lines += ""
$lines += "| t | runtime_ws_mb | runtime_pm_mb | adapter_ws_mb | adapter_pm_mb |"
$lines += "|---|---:|---:|---:|---:|"
foreach ($s in $samples) {
    $lines += "| $($s.t) | $($s.runtime_ws_mb) | $($s.runtime_pm_mb) | $($s.adapter_ws_mb) | $($s.adapter_pm_mb) |"
}

Set-Content -Path $reportPath -Value $lines -Encoding UTF8
Write-Output $reportPath
