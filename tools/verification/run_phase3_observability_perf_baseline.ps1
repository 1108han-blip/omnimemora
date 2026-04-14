param()

$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$runtimeRoot = Join-Path $projectRoot "4_core/local-runtime"
$logDir = Join-Path $projectRoot "tools/verification/logs"
New-Item -ItemType Directory -Path $logDir -Force | Out-Null

$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$reportPath = Join-Path $logDir "phase3_observability_perf_baseline_${stamp}.md"
$currentProcessId = $PID
$parentProcessId = (Get-CimInstance Win32_Process -Filter "ProcessId=$PID" -ErrorAction SilentlyContinue).ParentProcessId

function Get-PortProcessId {
    param([int]$Port)
    $conn = Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue |
        Where-Object { $_.LocalPort -eq $Port } |
        Select-Object -First 1
    if ($null -eq $conn) { return $null }
    return $conn.OwningProcess
}

function Stop-PortProcess {
    param([int]$Port)
    $procId = Get-PortProcessId -Port $Port
    if ($null -ne $procId) {
        if ($procId -eq $currentProcessId -or $procId -eq $parentProcessId) {
            Write-Warning "Skip stopping protected process on port $Port (pid=$procId)."
            return
        }
        Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
        Start-Sleep -Milliseconds 800
    }
}

function Wait-Health {
    param([string]$Url, [int]$MaxAttempts = 40, [int]$DelayMs = 500)
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

function Percentile {
    param([double[]]$Data, [double]$P)
    if ($Data.Count -eq 0) { return 0.0 }
    $sorted = $Data | Sort-Object
    $idx = [Math]::Ceiling($P * $sorted.Count) - 1
    if ($idx -lt 0) { $idx = 0 }
    if ($idx -ge $sorted.Count) { $idx = $sorted.Count - 1 }
    return [double]$sorted[$idx]
}

# Build updated runtime binary
Push-Location $runtimeRoot
& go build -o (Join-Path $projectRoot "tools/omnimemora.exe") ./cmd/omnimemora
if ($LASTEXITCODE -ne 0) {
    Pop-Location
    throw "go build failed for runtime"
}
Pop-Location

# Restart services (only target ports)
Stop-PortProcess -Port 8765
Stop-PortProcess -Port 18011

Start-Process -FilePath (Join-Path $projectRoot "tools/omnimemora.exe") -ArgumentList "serve" -WorkingDirectory $projectRoot -WindowStyle Hidden | Out-Null
Start-Process -FilePath "python" -ArgumentList (Join-Path $projectRoot "tools/_run_adapter.py") -WorkingDirectory $projectRoot -WindowStyle Hidden | Out-Null

$runtimeUp = Wait-Health -Url "http://127.0.0.1:8765/health"
$adapterUp = Wait-Health -Url "http://127.0.0.1:18011/health"
if (-not ($runtimeUp -and $adapterUp)) {
    throw "Services failed to become healthy after restart."
}

$checks = @()
function Add-Check {
    param([string]$Name, [bool]$Ok, [string]$Evidence)
    $script:checks += [PSCustomObject]@{
        name = $Name
        ok = $Ok
        evidence = $Evidence
    }
}

# ---- Observability checks ----
$obsHeaders = @{
    "Content-Type" = "application/json"
    "X-OmniMemora-Tenant" = "phase3-obs"
    "X-OmniMemora-User" = "obs-user"
    "X-OmniMemora-Workspace" = "obs-ws"
    "X-OmniMemora-Agent" = "obs-agent"
    "X-OmniMemora-Scope" = "agent"
}

$token = "obs" + [guid]::NewGuid().ToString("N").Substring(0, 8)
$wr = Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8765/memory/write" -Headers $obsHeaders -Body (@{ content = "phase3 observability $token" } | ConvertTo-Json) -TimeoutSec 8

$tmpHeader = Join-Path $env:TEMP ("omnimemora_q_header_" + [guid]::NewGuid().ToString("N") + ".txt")
$queryJson = (@{ query = $token; limit = 5 } | ConvertTo-Json -Compress)
& curl.exe -sS -D $tmpHeader -o NUL -X POST "http://127.0.0.1:8765/memory/query" `
    -H "Content-Type: application/json" `
    -H "X-OmniMemora-Tenant: phase3-obs" `
    -H "X-OmniMemora-User: obs-user" `
    -H "X-OmniMemora-Workspace: obs-ws" `
    -H "X-OmniMemora-Agent: obs-agent" `
    -H "X-OmniMemora-Scope: agent" `
    --data $queryJson | Out-Null
$headerLines = Get-Content $tmpHeader -ErrorAction SilentlyContinue
$respHeaderReqId = ""
foreach ($h in $headerLines) {
    if ($h -match "^(?i)x-omnimemora-request-id:\s*(.+)$") {
        $respHeaderReqId = $matches[1].Trim()
        break
    }
}
Remove-Item -Force -ErrorAction SilentlyContinue $tmpHeader
$respHeaderReqIdOk = -not [string]::IsNullOrWhiteSpace($respHeaderReqId)
Add-Check -Name "Observability: response header includes request_id" -Ok $respHeaderReqIdOk -Evidence ("header=" + $respHeaderReqId)

$qBody2 = Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8765/memory/query" -Headers $obsHeaders -Body (@{ query = $token; limit = 5 } | ConvertTo-Json) -TimeoutSec 8
$bodyReqId = ""
if ($null -ne $qBody2) {
    $p = $qBody2.PSObject.Properties["request_id"]
    if ($null -ne $p) {
        $bodyReqId = [string]$p.Value
    }
}
$bodyReqIdOk = -not [string]::IsNullOrWhiteSpace($bodyReqId)
Add-Check -Name "Observability: response body includes request_id" -Ok $bodyReqIdOk -Evidence ("body=" + $bodyReqId)

$scopeMetricOk = $false
$scopeMetricEvidence = ""
try {
    $metrics = Invoke-RestMethod -Method Get -Uri "http://127.0.0.1:8765/metrics" -TimeoutSec 8
    $scopeMetricOk = ($null -ne $metrics.by_scope) -and ($null -ne $metrics.token_savings)
    $scopeMetricEvidence = "by_scope=" + ($null -ne $metrics.by_scope) + ", token_savings=" + ($null -ne $metrics.token_savings)
} catch {
    $scopeMetricEvidence = $_.Exception.Message
}
Add-Check -Name "Observability: /metrics contains by_scope + token_savings" -Ok $scopeMetricOk -Evidence $scopeMetricEvidence

$invalidScopeOk = $false
$invalidScopeEvidence = ""
try {
    Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8765/memory/write" -Headers @{
        "Content-Type" = "application/json"
        "X-OmniMemora-Agent" = "obs-agent"
        "X-OmniMemora-Scope" = "custom"
    } -Body (@{ content = "invalid scope phase3" } | ConvertTo-Json) -TimeoutSec 8 | Out-Null
    $invalidScopeEvidence = "unexpected success"
} catch {
    $resp = $_.Exception.Response
    if ($resp -and [int]$resp.StatusCode -eq 501) {
        $invalidScopeOk = $true
        $invalidScopeEvidence = "status=501"
    } else {
        $invalidScopeEvidence = $_.Exception.Message
    }
}
Add-Check -Name "Observability: error path returns explicit 501" -Ok $invalidScopeOk -Evidence $invalidScopeEvidence

# ---- 100 request performance baseline on adapter ----
$tenant = "phase3-perf"
$agent = "codex"
$beforeUsage = Invoke-RestMethod -Method Get -Uri ("http://127.0.0.1:18011/usage/token-savings?tenant={0}&agent={1}" -f $tenant, $agent) -TimeoutSec 8
$beforeCount = [int]$beforeUsage.request_count

$latencies = New-Object System.Collections.Generic.List[Double]
$success = 0
$failed = 0
$firstErr = ""

for ($i = 1; $i -le 100; $i++) {
    $sw = [System.Diagnostics.Stopwatch]::StartNew()
    try {
        $resp = Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:18011/memory/query" -ContentType "application/json" -Body (@{
            tenant = $tenant
            user = "perf-user"
            agent = $agent
            query = ("phase3 performance baseline request " + $i)
        } | ConvertTo-Json -Depth 6) -TimeoutSec 10
        $sw.Stop()
        $latencies.Add([double]$sw.ElapsedMilliseconds)
        if ($resp.request_id) {
            $success++
        } else {
            $failed++
            if ($firstErr -eq "") { $firstErr = "missing request_id at #" + $i }
        }
    } catch {
        $sw.Stop()
        $failed++
        if ($firstErr -eq "") { $firstErr = $_.Exception.Message }
    }
}

$afterUsage = Invoke-RestMethod -Method Get -Uri ("http://127.0.0.1:18011/usage/token-savings?tenant={0}&agent={1}" -f $tenant, $agent) -TimeoutSec 8
$afterCount = [int]$afterUsage.request_count
$growth = $afterCount - $beforeCount
$growthOk = $growth -ge 95
Add-Check -Name "Performance: request_count growth after 100 requests" -Ok $growthOk -Evidence ("before=" + $beforeCount + ", after=" + $afterCount + ", growth=" + $growth)

$runtimeAfter = Wait-Health -Url "http://127.0.0.1:8765/health" -MaxAttempts 3 -DelayMs 300
$adapterAfter = Wait-Health -Url "http://127.0.0.1:18011/health" -MaxAttempts 3 -DelayMs 300
$stabilityOk = $runtimeAfter -and $adapterAfter -and ($failed -eq 0)
Add-Check -Name "Performance: no crash during 100 requests" -Ok $stabilityOk -Evidence ("failed=" + $failed + ", runtime_health=" + $runtimeAfter + ", adapter_health=" + $adapterAfter)

$avg = if ($latencies.Count -gt 0) { [Math]::Round((($latencies | Measure-Object -Average).Average), 2) } else { 0 }
$p50 = [Math]::Round((Percentile -Data $latencies.ToArray() -P 0.50), 2)
$p95 = [Math]::Round((Percentile -Data $latencies.ToArray() -P 0.95), 2)
$min = if ($latencies.Count -gt 0) { [Math]::Round((($latencies | Measure-Object -Minimum).Minimum), 2) } else { 0 }
$max = if ($latencies.Count -gt 0) { [Math]::Round((($latencies | Measure-Object -Maximum).Maximum), 2) } else { 0 }

$passCount = ($checks | Where-Object { $_.ok }).Count
$failCount = $checks.Count - $passCount

$lines = @()
$lines += "# Phase 3 Observability + Performance Baseline"
$lines += ""
$lines += "- Timestamp: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss zzz')"
$lines += "- Total checks: $($checks.Count)"
$lines += "- Passed: $passCount"
$lines += "- Failed: $failCount"
$lines += ""
$lines += "## Checks"
$lines += ""
$lines += "| Check | Result | Evidence |"
$lines += "|---|---|---|"
foreach ($c in $checks) {
    $state = if ($c.ok) { "PASS" } else { "FAIL" }
    $ev = ($c.evidence -replace "\|", "/")
    $lines += "| $($c.name) | $state | $ev |"
}
$lines += ""
$lines += "## 100 Request Latency (ms)"
$lines += ""
$lines += "- success: $success"
$lines += "- failed: $failed"
$lines += "- min: $min"
$lines += "- p50: $p50"
$lines += "- p95: $p95"
$lines += "- max: $max"
$lines += "- avg: $avg"
if ($firstErr -ne "") {
    $lines += "- first_error: $firstErr"
}
$lines += ""
$lines += "## Conclusion"
$lines += ""
$lines += "- runtime_health_after: $runtimeAfter"
$lines += "- adapter_health_after: $adapterAfter"
$lines += "- request_count_growth: $growth"
$lines += "- saved_tokens_total: $($afterUsage.saved_tokens_total)"

Set-Content -Path $reportPath -Value $lines -Encoding UTF8
Write-Output $reportPath
