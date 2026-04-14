param(
    [double]$DurationHours = 2,
    [int]$IntervalSeconds = 30,
    [string]$Tenant = "stability-tenant",
    [string]$User = "stability-user",
    [string]$Agent = "codex",
    [string]$AgentId = "codex",
    [string]$WorkspaceId = "ws-stability"
)

$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$logDir = Join-Path $projectRoot "tools/verification/logs"
New-Item -ItemType Directory -Path $logDir -Force | Out-Null

$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$jsonlPath = Join-Path $logDir "stability_probe_${stamp}.jsonl"
$summaryPath = Join-Path $logDir "stability_probe_${stamp}_summary.json"

function Get-Health {
    param([string]$Url)
    try {
        Invoke-RestMethod -Method Get -Uri $Url -TimeoutSec 3 | Out-Null
        return $true
    } catch {
        return $false
    }
}

function Get-Usage {
    param([string]$TenantName, [string]$AgentName)
    try {
        return Invoke-RestMethod -Method Get -Uri "http://127.0.0.1:18011/usage/token-savings?tenant=$TenantName&agent=$AgentName" -TimeoutSec 5
    } catch {
        return $null
    }
}

$start = [DateTime]::UtcNow
$end = $start.AddHours($DurationHours)
$iterations = 0
$runtimeFailures = 0
$adapterFailures = 0
$queryFailures = 0
$lastError = $null

$baseline = Get-Usage -TenantName $Tenant -AgentName $Agent
$baselineCount = if ($null -ne $baseline) { [int]$baseline.request_count } else { 0 }
$baselineSaved = if ($null -ne $baseline) { [int]$baseline.saved_tokens_total } else { 0 }

while ([DateTime]::UtcNow -lt $end) {
    $iterations++
    $utcNow = [DateTime]::UtcNow.ToString("o")

    $runtimeOk = Get-Health -Url "http://127.0.0.1:8765/health"
    $adapterOk = Get-Health -Url "http://127.0.0.1:18011/health"

    if (-not $runtimeOk) { $runtimeFailures++ }
    if (-not $adapterOk) { $adapterFailures++ }

    $requestId = ""
    $saved = 0
    $ratio = 0.0
    $taskType = ""
    $contextBypass = $false
    $queryOk = $false

    try {
        $payload = @{
            tenant = $Tenant
            user = $User
            agent = $Agent
            agent_id = $AgentId
            workspace_id = $WorkspaceId
            scope = "workspace"
            query = "stability heartbeat iteration $iterations"
            options = @{ max_local_cards = 4 }
        } | ConvertTo-Json -Depth 8

        $resp = Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:18011/memory/query" -ContentType "application/json" -Body $payload -TimeoutSec 10
        $requestId = [string]$resp.request_id
        $saved = [int]$resp.tokens_saved_estimate
        $ratio = [double]$resp.savings_ratio
        $taskType = [string]$resp.task_type
        $contextBypass = [bool]$resp.context_bypass
        $queryOk = $true
    } catch {
        $queryFailures++
        $lastError = $_.Exception.Message
    }

    $usage = Get-Usage -TenantName $Tenant -AgentName $Agent
    $usageCount = if ($null -ne $usage) { [int]$usage.request_count } else { -1 }
    $usageSaved = if ($null -ne $usage) { [int]$usage.saved_tokens_total } else { -1 }

    $line = @{
        ts_utc = $utcNow
        iteration = $iterations
        runtime_ok = $runtimeOk
        adapter_ok = $adapterOk
        query_ok = $queryOk
        request_id = $requestId
        saved_tokens_estimate = $saved
        savings_ratio = $ratio
        task_type = $taskType
        context_bypass = $contextBypass
        usage_request_count = $usageCount
        usage_saved_tokens_total = $usageSaved
        last_error = $lastError
    } | ConvertTo-Json -Compress

    Add-Content -Path $jsonlPath -Value $line

    Start-Sleep -Seconds $IntervalSeconds
}

$final = Get-Usage -TenantName $Tenant -AgentName $Agent
$finalCount = if ($null -ne $final) { [int]$final.request_count } else { -1 }
$finalSaved = if ($null -ne $final) { [int]$final.saved_tokens_total } else { -1 }

$summary = @{
    started_at_utc = $start.ToString("o")
    ended_at_utc = [DateTime]::UtcNow.ToString("o")
    duration_hours_target = $DurationHours
    interval_seconds = $IntervalSeconds
    tenant = $Tenant
    agent = $Agent
    iterations = $iterations
    runtime_failures = $runtimeFailures
    adapter_failures = $adapterFailures
    query_failures = $queryFailures
    baseline_request_count = $baselineCount
    final_request_count = $finalCount
    request_count_growth = ($finalCount - $baselineCount)
    baseline_saved_tokens_total = $baselineSaved
    final_saved_tokens_total = $finalSaved
    saved_tokens_growth = ($finalSaved - $baselineSaved)
    jsonl = $jsonlPath
    last_error = $lastError
} | ConvertTo-Json -Depth 8

Set-Content -Path $summaryPath -Value $summary -Encoding UTF8
Write-Output $summaryPath
