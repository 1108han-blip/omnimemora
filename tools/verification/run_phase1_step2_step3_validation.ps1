param()

$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$logDir = Join-Path $projectRoot "tools/verification/logs"
New-Item -ItemType Directory -Path $logDir -Force | Out-Null

$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$reportPath = Join-Path $logDir "phase1_step2_step3_validation_${stamp}.md"
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
        $runtimeBin = Join-Path $projectRoot "tools/omnimemora-runtime"
        if (-not (Test-Path $runtimeBin)) {
            $runtimeBin = Join-Path $projectRoot "tools/omnimemora.exe"
        }
        Start-Process -FilePath $runtimeBin -ArgumentList "serve" -WorkingDirectory $projectRoot -WindowStyle Hidden | Out-Null
        $runtimeUp = Wait-Health -Url "http://127.0.0.1:8765/health"
    }
    if (-not $adapterUp) {
        Start-Process -FilePath "python" -ArgumentList (Join-Path $projectRoot "tools/_run_adapter.py") -WorkingDirectory $projectRoot -WindowStyle Hidden | Out-Null
        $adapterUp = Wait-Health -Url "http://127.0.0.1:18011/health"
    }
    return ($runtimeUp -and $adapterUp)
}

function Test-Result {
    param([string]$Name, [bool]$Ok, [string]$Evidence)
    return [PSCustomObject]@{
        name = $Name
        ok = $Ok
        evidence = $Evidence
    }
}

$results = @()
$evidence = @{}

if (-not (Ensure-ServicesUp)) {
    throw "Services are not healthy; cannot run Step 2/3 validation."
}

# -------- Step 2: Scope isolation --------
$scopeToken = "scopecheck" + [guid]::NewGuid().ToString("N").Substring(0, 8)

$hAgentA = @{
    "Content-Type" = "application/json"
    "X-OmniMemora-Tenant" = "phase1-step2"
    "X-OmniMemora-User" = "user-a"
    "X-OmniMemora-Workspace" = "ws-a"
    "X-OmniMemora-Agent" = "agent-a"
    "X-OmniMemora-Scope" = "agent"
}
$hAgentB = @{
    "Content-Type" = "application/json"
    "X-OmniMemora-Tenant" = "phase1-step2"
    "X-OmniMemora-User" = "user-a"
    "X-OmniMemora-Workspace" = "ws-a"
    "X-OmniMemora-Agent" = "agent-b"
    "X-OmniMemora-Scope" = "agent"
}
$hWorkspaceA = @{
    "Content-Type" = "application/json"
    "X-OmniMemora-Tenant" = "phase1-step2"
    "X-OmniMemora-User" = "user-a"
    "X-OmniMemora-Workspace" = "ws-shared"
    "X-OmniMemora-Agent" = "agent-a"
    "X-OmniMemora-Scope" = "workspace"
}
$hWorkspaceB = @{
    "Content-Type" = "application/json"
    "X-OmniMemora-Tenant" = "phase1-step2"
    "X-OmniMemora-User" = "user-a"
    "X-OmniMemora-Workspace" = "ws-shared"
    "X-OmniMemora-Agent" = "agent-b"
    "X-OmniMemora-Scope" = "workspace"
}
$hUser1 = @{
    "Content-Type" = "application/json"
    "X-OmniMemora-Tenant" = "phase1-step2"
    "X-OmniMemora-User" = "user-1"
    "X-OmniMemora-Workspace" = "ws-user"
    "X-OmniMemora-Agent" = "agent-u"
    "X-OmniMemora-Scope" = "user"
}
$hUser2 = @{
    "Content-Type" = "application/json"
    "X-OmniMemora-Tenant" = "phase1-step2"
    "X-OmniMemora-User" = "user-2"
    "X-OmniMemora-Workspace" = "ws-user"
    "X-OmniMemora-Agent" = "agent-u"
    "X-OmniMemora-Scope" = "user"
}

Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8765/memory/write" -Headers $hAgentA -Body (@{ content = "agent isolated $scopeToken" } | ConvertTo-Json) -TimeoutSec 5 | Out-Null
$agentBQuery = Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8765/memory/query" -Headers $hAgentB -Body (@{ query = $scopeToken; limit = 10 } | ConvertTo-Json) -TimeoutSec 5
$agentIsolationOk = ([int]$agentBQuery.total -eq 0)
$results += Test-Result -Name "Scope: agent isolation" -Ok $agentIsolationOk -Evidence ("agent-b total=" + $agentBQuery.total)

Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8765/memory/write" -Headers $hWorkspaceA -Body (@{ content = "workspace shared $scopeToken" } | ConvertTo-Json) -TimeoutSec 5 | Out-Null
$workspaceBQuery = Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8765/memory/query" -Headers $hWorkspaceB -Body (@{ query = $scopeToken; limit = 10 } | ConvertTo-Json) -TimeoutSec 5
$workspaceSharedOk = ([int]$workspaceBQuery.total -ge 1)
$results += Test-Result -Name "Scope: workspace sharing" -Ok $workspaceSharedOk -Evidence ("agent-b workspace total=" + $workspaceBQuery.total)

Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8765/memory/write" -Headers $hUser1 -Body (@{ content = "user isolated $scopeToken" } | ConvertTo-Json) -TimeoutSec 5 | Out-Null
$user2Query = Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8765/memory/query" -Headers $hUser2 -Body (@{ query = $scopeToken; limit = 10 } | ConvertTo-Json) -TimeoutSec 5
$userIsolationOk = ([int]$user2Query.total -eq 0)
$results += Test-Result -Name "Scope: user isolation" -Ok $userIsolationOk -Evidence ("user-2 total=" + $user2Query.total)

# -------- Step 2: Abnormal scenarios --------
$emptyHeaders = @{
    "Content-Type" = "application/json"
    "X-OmniMemora-Tenant" = "phase1-empty"
    "X-OmniMemora-User" = "empty-user"
    "X-OmniMemora-Workspace" = "empty-ws"
    "X-OmniMemora-Agent" = "empty-agent"
    "X-OmniMemora-Scope" = "agent"
}
$emptyQuery = Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8765/memory/query" -Headers $emptyHeaders -Body (@{ query = "nohit" + [guid]::NewGuid().ToString("N"); limit = 10 } | ConvertTo-Json) -TimeoutSec 5
$emptyOk = ([int]$emptyQuery.total -eq 0)
$results += Test-Result -Name "Abnormal: empty memory returns normal empty result" -Ok $emptyOk -Evidence ("total=" + $emptyQuery.total)

$invalidScopeOk = $false
$invalidScopeDetail = ""
try {
    Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8765/memory/write" -Headers @{
        "Content-Type" = "application/json"
        "X-OmniMemora-Agent" = "bad-scope"
        "X-OmniMemora-Scope" = "custom"
    } -Body (@{ content = "invalid scope test" } | ConvertTo-Json) -TimeoutSec 5 | Out-Null
    $invalidScopeDetail = "unexpected success"
} catch {
    $resp = $_.Exception.Response
    if ($resp -and [int]$resp.StatusCode -eq 501) {
        $invalidScopeOk = $true
        $invalidScopeDetail = "status=501"
    } else {
        $invalidScopeDetail = $_.Exception.Message
    }
}
$results += Test-Result -Name "Abnormal: invalid scope returns 501" -Ok $invalidScopeOk -Evidence $invalidScopeDetail

# runtime down scenario (adapter should fail, then recover)
$runtimeDownOk = $false
$runtimeRecoverOk = $false
$runtimeDownDetail = ""
Stop-PortProcess -Port 8765
Start-Sleep -Milliseconds 800
try {
    Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:18011/memory/query" -ContentType "application/json" -Body (@{
        tenant = "phase1-step2"
        user = "runtime-down"
        agent = "codex"
        query = "runtime down check"
    } | ConvertTo-Json) -TimeoutSec 6 | Out-Null
    $runtimeDownDetail = "unexpected success"
} catch {
    $runtimeDownOk = $true
    $runtimeDownDetail = $_.Exception.Message
}
$runtimeBin = Join-Path $projectRoot "tools/omnimemora-runtime"
if (-not (Test-Path $runtimeBin)) {
    $runtimeBin = Join-Path $projectRoot "tools/omnimemora.exe"
}
Start-Process -FilePath $runtimeBin -ArgumentList "serve" -WorkingDirectory $projectRoot -WindowStyle Hidden | Out-Null
$runtimeRecovered = Wait-Health -Url "http://127.0.0.1:8765/health"
if ($runtimeRecovered) {
    try {
        $postRecover = Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:18011/memory/query" -ContentType "application/json" -Body (@{
            tenant = "phase1-step2"
            user = "runtime-down"
            agent = "codex"
            query = "runtime recovered check"
        } | ConvertTo-Json) -TimeoutSec 8
        $runtimeRecoverOk = [bool]$postRecover.request_id
    } catch {}
}
$results += Test-Result -Name "Abnormal: runtime down surfaces error" -Ok $runtimeDownOk -Evidence $runtimeDownDetail
$results += Test-Result -Name "Abnormal: runtime recovers and query resumes" -Ok $runtimeRecoverOk -Evidence ("runtime_health=" + $runtimeRecovered)

# connector down scenario
$connectorDownOk = $false
$connectorRecoverOk = $false
$connectorDetail = ""
Stop-PortProcess -Port 18011
Start-Sleep -Milliseconds 800
try {
    Invoke-RestMethod -Method Get -Uri "http://127.0.0.1:18011/health" -TimeoutSec 3 | Out-Null
    $connectorDetail = "unexpected health success"
} catch {
    $connectorDownOk = $true
    $connectorDetail = $_.Exception.Message
}
Start-Process -FilePath "python" -ArgumentList (Join-Path $projectRoot "tools/_run_adapter.py") -WorkingDirectory $projectRoot -WindowStyle Hidden | Out-Null
$adapterRecovered = Wait-Health -Url "http://127.0.0.1:18011/health"
if ($adapterRecovered) {
    $connectorRecoverOk = $true
}
$results += Test-Result -Name "Abnormal: connector down detectable" -Ok $connectorDownOk -Evidence $connectorDetail
$results += Test-Result -Name "Abnormal: connector recovers" -Ok $connectorRecoverOk -Evidence ("adapter_health=" + $adapterRecovered)

# -------- Step 3: Token savings explainability --------
$explainTenant = "phase1-step3"
$decisionResp = Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:18011/memory/query" -ContentType "application/json" -Body (@{
    tenant = $explainTenant
    user = "explain-user"
    agent = "codex"
    agent_id = "codex"
    workspace_id = "ws-explain"
    scope = "workspace"
    query = "which approach should we choose for migration decision"
    options = @{ max_local_cards = 4 }
} | ConvertTo-Json -Depth 8) -TimeoutSec 10

$decisionMeter = Invoke-RestMethod -Method Get -Uri ("http://127.0.0.1:18011/requests/{0}/meter" -f $decisionResp.request_id) -TimeoutSec 6
$decisionMathOk = ([int]$decisionMeter.saved_tokens_estimate -eq ([int]$decisionMeter.baseline_tokens_estimate - [int]$decisionMeter.actual_tokens_estimate))
$decisionExplainOk = (([double]$decisionMeter.savings_ratio -ge 0) -and ([double]$decisionMeter.savings_ratio -le 1))
$results += Test-Result -Name "Token explainability: decision query savings math" -Ok $decisionMathOk -Evidence ("baseline=" + $decisionMeter.baseline_tokens_estimate + ", actual=" + $decisionMeter.actual_tokens_estimate + ", saved=" + $decisionMeter.saved_tokens_estimate)
$results += Test-Result -Name "Token explainability: decision savings ratio in [0,1]" -Ok $decisionExplainOk -Evidence ("ratio=" + $decisionMeter.savings_ratio)

$implResp = Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:18011/memory/query" -ContentType "application/json" -Body (@{
    tenant = $explainTenant
    user = "explain-user"
    agent = "codex"
    agent_id = "codex"
    workspace_id = "ws-explain"
    scope = "workspace"
    query = "write code to implement login flow"
} | ConvertTo-Json -Depth 8) -TimeoutSec 10
$bypassOk = ([bool]$implResp.context_bypass -eq $true -and [int]$implResp.memory_tokens_injected -eq 0)
$results += Test-Result -Name "Token explainability: implementation bypass rationale visible" -Ok $bypassOk -Evidence ("context_bypass=" + $implResp.context_bypass + ", memory_tokens_injected=" + $implResp.memory_tokens_injected + ", task_type=" + $implResp.task_type)

$usage = Invoke-RestMethod -Method Get -Uri ("http://127.0.0.1:18011/usage/token-savings?tenant={0}&agent=codex" -f $explainTenant) -TimeoutSec 6
$usageOk = ([int]$usage.request_count -ge 2 -and [int]$usage.saved_tokens_total -ge 0)
$results += Test-Result -Name "Token explainability: usage aggregation present" -Ok $usageOk -Evidence ("request_count=" + $usage.request_count + ", saved_tokens_total=" + $usage.saved_tokens_total)

$passCount = ($results | Where-Object { $_.ok }).Count
$failCount = $results.Count - $passCount

$lines = @()
$lines += "# Phase 1 Step 2 + Step 3 Validation"
$lines += ""
$lines += "- Timestamp (UTC): $([DateTime]::UtcNow.ToString("yyyy-MM-dd HH:mm:ss"))"
$lines += "- Total checks: $($results.Count)"
$lines += "- Passed: $passCount"
$lines += "- Failed: $failCount"
$lines += ""
$lines += "## Results"
$lines += ""
$lines += "| Check | Result | Evidence |"
$lines += "|---|---|---|"
foreach ($r in $results) {
    $state = if ($r.ok) { "PASS" } else { "FAIL" }
    $ev = ($r.evidence -replace "\|", "/")
    $lines += "| $($r.name) | $state | $ev |"
}
$lines += ""
$lines += "## Token Explainability Snapshot"
$lines += ""
$lines += "- decision_request_id: $($decisionResp.request_id)"
$lines += "- implementation_request_id: $($implResp.request_id)"
$lines += "- decision_meter: baseline=$($decisionMeter.baseline_tokens_estimate), actual=$($decisionMeter.actual_tokens_estimate), saved=$($decisionMeter.saved_tokens_estimate), ratio=$($decisionMeter.savings_ratio)"
$lines += "- implementation_flags: task_type=$($implResp.task_type), context_bypass=$($implResp.context_bypass), memory_tokens_injected=$($implResp.memory_tokens_injected)"
$lines += "- usage_summary: request_count=$($usage.request_count), saved_tokens_total=$($usage.saved_tokens_total)"

Set-Content -Path $reportPath -Value $lines -Encoding UTF8
Write-Output $reportPath
