param()

$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$logDir = Join-Path $projectRoot "tools/verification/logs"
New-Item -ItemType Directory -Path $logDir -Force | Out-Null

$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$reportPath = Join-Path $logDir "phase2_stepc_migration_rehearsal_${stamp}.md"
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

function Start-Services {
    Stop-PortProcess -Port 8765
    Stop-PortProcess -Port 18011

    $runtimeBin = Join-Path $projectRoot "tools/omnimemora-runtime"
    if (-not (Test-Path $runtimeBin)) {
        $runtimeBin = Join-Path $projectRoot "tools/omnimemora.exe"
    }
    Start-Process -FilePath $runtimeBin -ArgumentList "serve" -WorkingDirectory $projectRoot -WindowStyle Hidden | Out-Null
    Start-Process -FilePath "python" -ArgumentList (Join-Path $projectRoot "tools/_run_adapter.py") -WorkingDirectory $projectRoot -WindowStyle Hidden | Out-Null

    $runtimeOk = Wait-Health -Url "http://127.0.0.1:8765/health"
    $adapterOk = Wait-Health -Url "http://127.0.0.1:18011/health"
    return ($runtimeOk -and $adapterOk)
}

function Add-Result {
    param([string]$Name, [bool]$Ok, [string]$Evidence)
    [PSCustomObject]@{
        name = $Name
        ok = $Ok
        evidence = $Evidence
    }
}

$results = @()

if (-not (Start-Services)) {
    throw "Runtime/Adapter failed to start for migration rehearsal."
}

# Health checks
$runtimeHealthOk = $false
$adapterHealthOk = $false
try {
    Invoke-RestMethod -Method Get -Uri "http://127.0.0.1:8765/health" -TimeoutSec 5 | Out-Null
    $runtimeHealthOk = $true
} catch {}
try {
    Invoke-RestMethod -Method Get -Uri "http://127.0.0.1:18011/health" -TimeoutSec 5 | Out-Null
    $adapterHealthOk = $true
} catch {}
$results += Add-Result -Name "Health: runtime /health" -Ok $runtimeHealthOk -Evidence "port=8765"
$results += Add-Result -Name "Health: adapter /health" -Ok $adapterHealthOk -Evidence "port=18011"

# Runtime write/query loop
$token = "migrationsop" + [guid]::NewGuid().ToString("N").Substring(0, 8)
$hRuntime = @{
    "Content-Type" = "application/json"
    "X-OmniMemora-Tenant" = "migration-check-tenant"
    "X-OmniMemora-User" = "migration-check-user"
    "X-OmniMemora-Workspace" = "migration-check-workspace"
    "X-OmniMemora-Agent" = "migration-check"
    "X-OmniMemora-Scope" = "agent"
}

$writeOk = $false
$queryOk = $false
$queryTotal = 0
try {
    $writeResp = Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8765/memory/write" -Headers $hRuntime -Body (@{
        content = "migration sop verification $token"
    } | ConvertTo-Json) -TimeoutSec 8
    $writeOk = [bool]$writeResp.memory_id
} catch {}

try {
    Start-Sleep -Milliseconds 300
    $queryResp = Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8765/memory/query" -Headers $hRuntime -Body (@{
        query = $token
        limit = 10
    } | ConvertTo-Json) -TimeoutSec 8
    $queryTotal = [int]$queryResp.total
    $queryOk = ($queryTotal -ge 1)
} catch {}

$results += Add-Result -Name "Runtime: write success" -Ok $writeOk -Evidence ("memory_id_present=" + $writeOk)
$results += Add-Result -Name "Runtime: query recalls written content" -Ok $queryOk -Evidence ("total=" + $queryTotal)

# Adapter request_count growth + token savings presence
$tenant = "migration-tenant"
$agent = "codex"

$before = Invoke-RestMethod -Method Get -Uri ("http://127.0.0.1:18011/usage/token-savings?tenant={0}&agent={1}" -f $tenant, $agent) -TimeoutSec 8
$beforeCount = [int]$before.request_count

$adapterQueryOk = $false
try {
    $aq = Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:18011/memory/query" -ContentType "application/json" -Body (@{
        tenant = $tenant
        user = "migration-user"
        agent = $agent
        query = "which migration path should we choose"
    } | ConvertTo-Json -Depth 6) -TimeoutSec 10
    $adapterQueryOk = [bool]$aq.request_id
} catch {}

$after = Invoke-RestMethod -Method Get -Uri ("http://127.0.0.1:18011/usage/token-savings?tenant={0}&agent={1}" -f $tenant, $agent) -TimeoutSec 8
$afterCount = [int]$after.request_count
$countGrowthOk = ($afterCount -gt $beforeCount)
$savingsPresentOk = ([int]$after.saved_tokens_total -ge 0)

$results += Add-Result -Name "Adapter: query success" -Ok $adapterQueryOk -Evidence ("request_id_present=" + $adapterQueryOk)
$results += Add-Result -Name "Adapter: request_count grows" -Ok $countGrowthOk -Evidence ("before=" + $beforeCount + ", after=" + $afterCount)
$results += Add-Result -Name "Adapter: token savings endpoint available" -Ok $savingsPresentOk -Evidence ("saved_tokens_total=" + $after.saved_tokens_total)

$passCount = ($results | Where-Object { $_.ok }).Count
$failCount = $results.Count - $passCount

$lines = @()
$lines += "# Phase 2 Step C Migration Rehearsal"
$lines += ""
$lines += "- Timestamp: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss zzz')"
$lines += "- Runtime URL: http://127.0.0.1:8765"
$lines += "- Adapter URL: http://127.0.0.1:18011"
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
$lines += "## Acceptance"
$lines += ""
$lines += "- Runtime + Adapter health: $($runtimeHealthOk -and $adapterHealthOk)"
$lines += "- Write/query closed-loop: $($writeOk -and $queryOk)"
$lines += "- request_count growth observed: $countGrowthOk"
$lines += "- token savings endpoint available: $savingsPresentOk"
$lines += ""
$lines += "## Note"
$lines += ""
$lines += "- Services are kept running after this script for continued Phase 2/3 work."

Set-Content -Path $reportPath -Value $lines -Encoding UTF8
Write-Output $reportPath
