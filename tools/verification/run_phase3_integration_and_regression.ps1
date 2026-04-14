param()

$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$logDir = Join-Path $projectRoot "tools/verification/logs"
New-Item -ItemType Directory -Path $logDir -Force | Out-Null

$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$reportPath = Join-Path $logDir "phase3_integration_regression_${stamp}.md"
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
    param([string]$Url, [int]$MaxAttempts = 30, [int]$DelayMs = 500)
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

function Ensure-ServicesUp {
    $runtimeUp = $false
    $adapterUp = $false
    try {
        Invoke-RestMethod -Method Get -Uri "http://127.0.0.1:8765/health" -TimeoutSec 3 | Out-Null
        $runtimeUp = $true
    } catch {}
    try {
        Invoke-RestMethod -Method Get -Uri "http://127.0.0.1:18011/health" -TimeoutSec 3 | Out-Null
        $adapterUp = $true
    } catch {}

    if (-not $runtimeUp) {
        $runtimeBin = Join-Path $projectRoot "tools/omnimemora.exe"
        Start-Process -FilePath $runtimeBin -ArgumentList "serve" -WorkingDirectory $projectRoot -WindowStyle Hidden | Out-Null
        $runtimeUp = Wait-Health -Url "http://127.0.0.1:8765/health"
    }
    if (-not $adapterUp) {
        Start-Process -FilePath "python" -ArgumentList (Join-Path $projectRoot "tools/_run_adapter.py") -WorkingDirectory $projectRoot -WindowStyle Hidden | Out-Null
        $adapterUp = Wait-Health -Url "http://127.0.0.1:18011/health"
    }
    return ($runtimeUp -and $adapterUp)
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

if (-not (Ensure-ServicesUp)) {
    throw "Services are not healthy; cannot run integration+regression suite."
}

# ---- Integration validation: Codex attach chain ----
$preRuntimeHealth = Wait-Health -Url "http://127.0.0.1:8765/health" -MaxAttempts 3 -DelayMs 300
$preAdapterHealth = Wait-Health -Url "http://127.0.0.1:18011/health" -MaxAttempts 3 -DelayMs 300

$attachOutput = (& (Join-Path $projectRoot "tools/omnimemora.exe") attach codex 2>&1 | Out-String).Trim()
$attachListOutput = (& (Join-Path $projectRoot "tools/omnimemora.exe") attach 2>&1 | Out-String)
$attachOk = ($attachOutput -match "configured|already configured") -and ($attachListOutput -match "Codex")
Add-Check -Name "Integration: Codex attach command succeeds" -Ok $attachOk -Evidence $attachOutput

$integrationResp = $null
$integrationOk = $false
try {
    $integrationResp = Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:18011/memory/query" -ContentType "application/json" -Body (@{
        tenant = "phase3-integration"
        user = "integration-user"
        agent = "codex"
        query = "integration validation query"
    } | ConvertTo-Json -Depth 6) -TimeoutSec 10
    $integrationOk = [bool]$integrationResp.request_id
} catch {}
Add-Check -Name "Integration: memory call works after Codex attach" -Ok $integrationOk -Evidence ("request_id=" + $integrationResp.request_id)

$postRuntimeHealth = Wait-Health -Url "http://127.0.0.1:8765/health" -MaxAttempts 3 -DelayMs 300
$postAdapterHealth = Wait-Health -Url "http://127.0.0.1:18011/health" -MaxAttempts 3 -DelayMs 300
$mainFlowOk = $preRuntimeHealth -and $preAdapterHealth -and $postRuntimeHealth -and $postAdapterHealth
Add-Check -Name "Integration: main flow unaffected" -Ok $mainFlowOk -Evidence ("runtime=" + $postRuntimeHealth + ", adapter=" + $postAdapterHealth)

# ---- Regression: write -> query -> delete -> query ----
$token = "reg" + [guid]::NewGuid().ToString("N").Substring(0, 8)
$h = @{
    "Content-Type" = "application/json"
    "X-OmniMemora-Tenant" = "phase3-reg"
    "X-OmniMemora-User" = "reg-user"
    "X-OmniMemora-Workspace" = "reg-ws"
    "X-OmniMemora-Agent" = "reg-agent"
    "X-OmniMemora-Scope" = "agent"
}

$w = Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8765/memory/write" -Headers $h -Body (@{ content = "phase3 lifecycle $token" } | ConvertTo-Json) -TimeoutSec 8
$q1 = Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8765/memory/query" -Headers $h -Body (@{ query = $token; limit = 10 } | ConvertTo-Json) -TimeoutSec 8
$d = Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8765/memory/delete" -Headers $h -Body (@{ memory_id = $w.memory_id } | ConvertTo-Json) -TimeoutSec 8
$q2 = Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8765/memory/query" -Headers $h -Body (@{ query = $token; limit = 10 } | ConvertTo-Json) -TimeoutSec 8
$lifeCycleOk = ([int]$q1.total -ge 1) -and ($d.status -eq "deleted") -and ([int]$q2.total -eq 0)
Add-Check -Name "Regression: write->query->delete->query" -Ok $lifeCycleOk -Evidence ("before=" + $q1.total + ", after=" + $q2.total)

# ---- Regression: scope isolation ----
$scopeToken = "scope" + [guid]::NewGuid().ToString("N").Substring(0, 8)
$hA = @{
    "Content-Type" = "application/json"
    "X-OmniMemora-Tenant" = "phase3-scope"
    "X-OmniMemora-User" = "u1"
    "X-OmniMemora-Workspace" = "ws1"
    "X-OmniMemora-Agent" = "agent-a"
    "X-OmniMemora-Scope" = "agent"
}
$hB = @{
    "Content-Type" = "application/json"
    "X-OmniMemora-Tenant" = "phase3-scope"
    "X-OmniMemora-User" = "u1"
    "X-OmniMemora-Workspace" = "ws1"
    "X-OmniMemora-Agent" = "agent-b"
    "X-OmniMemora-Scope" = "agent"
}
Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8765/memory/write" -Headers $hA -Body (@{ content = "phase3 scope $scopeToken" } | ConvertTo-Json) -TimeoutSec 8 | Out-Null
$qB = Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8765/memory/query" -Headers $hB -Body (@{ query = $scopeToken; limit = 10 } | ConvertTo-Json) -TimeoutSec 8
$scopeOk = ([int]$qB.total -eq 0)
Add-Check -Name "Regression: agent scope isolation" -Ok $scopeOk -Evidence ("agent-b total=" + $qB.total)

# ---- Regression: token savings growth ----
$tenant = "phase3-regression"
$agent = "codex"
$u0 = Invoke-RestMethod -Method Get -Uri ("http://127.0.0.1:18011/usage/token-savings?tenant={0}&agent={1}" -f $tenant, $agent) -TimeoutSec 8
$c0 = [int]$u0.request_count
Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:18011/memory/query" -ContentType "application/json" -Body (@{
    tenant = $tenant
    user = "regression-user"
    agent = $agent
    query = "regression token savings check"
} | ConvertTo-Json -Depth 6) -TimeoutSec 10 | Out-Null
$u1 = Invoke-RestMethod -Method Get -Uri ("http://127.0.0.1:18011/usage/token-savings?tenant={0}&agent={1}" -f $tenant, $agent) -TimeoutSec 8
$c1 = [int]$u1.request_count
$tokenOk = ($c1 -gt $c0) -and ([int]$u1.saved_tokens_total -ge 0)
Add-Check -Name "Regression: token savings usage increments" -Ok $tokenOk -Evidence ("before=" + $c0 + ", after=" + $c1 + ", saved=" + $u1.saved_tokens_total)

# ---- Regression: abnormal paths ----
$invalidScopeOk = $false
$invalidScopeEvidence = ""
try {
    Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8765/memory/write" -Headers @{
        "Content-Type" = "application/json"
        "X-OmniMemora-Agent" = "bad-scope"
        "X-OmniMemora-Scope" = "custom"
    } -Body (@{ content = "phase3 invalid scope" } | ConvertTo-Json) -TimeoutSec 8 | Out-Null
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
Add-Check -Name "Regression: invalid scope returns 501" -Ok $invalidScopeOk -Evidence $invalidScopeEvidence

$emptyQuery = Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8765/memory/query" -Headers @{
    "Content-Type" = "application/json"
    "X-OmniMemora-Tenant" = "phase3-empty"
    "X-OmniMemora-User" = "empty-user"
    "X-OmniMemora-Workspace" = "empty-ws"
    "X-OmniMemora-Agent" = "empty-agent"
    "X-OmniMemora-Scope" = "agent"
} -Body (@{ query = "nohit" + [guid]::NewGuid().ToString("N"); limit = 5 } | ConvertTo-Json) -TimeoutSec 8
$emptyOk = ([int]$emptyQuery.total -eq 0)
Add-Check -Name "Regression: empty result path is normal" -Ok $emptyOk -Evidence ("total=" + $emptyQuery.total)

$passCount = ($checks | Where-Object { $_.ok }).Count
$failCount = $checks.Count - $passCount

$lines = @()
$lines += "# Phase 3 Integration + Regression"
$lines += ""
$lines += "- Timestamp: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss zzz')"
$lines += "- Total checks: $($checks.Count)"
$lines += "- Passed: $passCount"
$lines += "- Failed: $failCount"
$lines += ""
$lines += "## Results"
$lines += ""
$lines += "| Check | Result | Evidence |"
$lines += "|---|---|---|"
foreach ($c in $checks) {
    $state = if ($c.ok) { "PASS" } else { "FAIL" }
    $ev = ($c.evidence -replace "\|", "/")
    $lines += "| $($c.name) | $state | $ev |"
}

Set-Content -Path $reportPath -Value $lines -Encoding UTF8
Write-Output $reportPath
