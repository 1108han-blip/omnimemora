param(
    [int]$Cycles = 10
)

$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$logDir = Join-Path $projectRoot "tools/verification/logs"
New-Item -ItemType Directory -Path $logDir -Force | Out-Null

$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$runtimeOut = Join-Path $logDir "runtime_${stamp}.out.log"
$runtimeErr = Join-Path $logDir "runtime_${stamp}.err.log"
$adapterOut = Join-Path $logDir "adapter_${stamp}.out.log"
$adapterErr = Join-Path $logDir "adapter_${stamp}.err.log"
$reportPath = Join-Path $logDir "phase1_step1_restart_validation_${stamp}.md"

$runtimeExe = Join-Path $projectRoot "tools/omnimemora-runtime"
if (-not (Test-Path $runtimeExe)) {
    $runtimeExe = Join-Path $projectRoot "tools/omnimemora.exe"
}
$adapterScript = Join-Path $projectRoot "tools/_run_adapter.py"
$currentProcessId = $PID
$parentProcessId = (Get-CimInstance Win32_Process -Filter "ProcessId=$PID" -ErrorAction SilentlyContinue).ParentProcessId

function Get-PortProcessId {
    param([int]$Port)
    $conn = Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue | Where-Object { $_.LocalPort -eq $Port } | Select-Object -First 1
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
    param([string]$Url, [int]$MaxAttempts = 20, [int]$DelayMs = 500)
    for ($i = 1; $i -le $MaxAttempts; $i++) {
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

    Start-Process -FilePath $runtimeExe -ArgumentList "serve" -WorkingDirectory $projectRoot -RedirectStandardOutput $runtimeOut -RedirectStandardError $runtimeErr -WindowStyle Hidden | Out-Null
    Start-Sleep -Milliseconds 700
    Start-Process -FilePath "python" -ArgumentList $adapterScript -WorkingDirectory $projectRoot -RedirectStandardOutput $adapterOut -RedirectStandardError $adapterErr -WindowStyle Hidden | Out-Null

    $runtimeOk = Wait-Health -Url "http://127.0.0.1:8765/health"
    $adapterOk = Wait-Health -Url "http://127.0.0.1:18011/health"
    return ($runtimeOk -and $adapterOk)
}

$results = @()

for ($i = 1; $i -le $Cycles; $i++) {
    $token = "phase1cycle${i}" + [guid]::NewGuid().ToString("N").Substring(0, 8)
    $cycleOk = $true
    $notes = @()

    if (-not (Start-Services)) {
        $cycleOk = $false
        $notes += "start_services_failed"
    }

    if ($cycleOk) {
        $headers = @{
            "Content-Type" = "application/json"
            "X-OmniMemora-Agent" = "phase1-agent"
            "X-OmniMemora-User" = "phase1-user"
            "X-OmniMemora-Workspace" = "phase1-ws"
            "X-OmniMemora-Scope" = "workspace"
        }

        $writeBody = @{ content = "phase1 restart consistency $token" } | ConvertTo-Json
        try {
            $writeResp = Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8765/memory/write" -Headers $headers -Body $writeBody -TimeoutSec 5
        } catch {
            $cycleOk = $false
            $notes += ("write_failed: " + $_.Exception.Message)
        }

        $queryBody = @{ query = $token; limit = 10 } | ConvertTo-Json
        if ($cycleOk) {
            try {
                $queryRespBefore = Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8765/memory/query" -Headers $headers -Body $queryBody -TimeoutSec 5
                if ([int]$queryRespBefore.total -lt 1) {
                    $cycleOk = $false
                    $notes += "query_before_restart_empty"
                }
            } catch {
                $cycleOk = $false
                $notes += ("query_before_restart_failed: " + $_.Exception.Message)
            }
        }

        if ($cycleOk) {
            if (-not (Start-Services)) {
                $cycleOk = $false
                $notes += "restart_services_failed"
            } else {
                try {
                    $queryRespAfter = Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8765/memory/query" -Headers $headers -Body $queryBody -TimeoutSec 5
                    if ([int]$queryRespAfter.total -lt 1) {
                        $cycleOk = $false
                        $notes += "query_after_restart_empty"
                    }
                } catch {
                    $cycleOk = $false
                    $notes += ("query_after_restart_failed: " + $_.Exception.Message)
                }
            }
        }

        if ($cycleOk) {
            $adapterPayload = @{
                tenant = "phase1-tenant"
                user = "phase1-user"
                agent = "codex"
                agent_id = "codex"
                workspace_id = "phase1-ws"
                scope = "workspace"
                query = "phase1 adapter check $token"
                options = @{ max_local_cards = 4 }
            } | ConvertTo-Json -Depth 8
            try {
                $adapterResp = Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:18011/memory/query" -ContentType "application/json" -Body $adapterPayload -TimeoutSec 8
                if (-not $adapterResp.request_id) {
                    $cycleOk = $false
                    $notes += "adapter_missing_request_id"
                }
            } catch {
                $cycleOk = $false
                $notes += ("adapter_query_failed: " + $_.Exception.Message)
            }
        }
    }

    $results += [PSCustomObject]@{
        cycle = $i
        ok = $cycleOk
        token = $token
        notes = ($notes -join "; ")
        ts_utc = [DateTime]::UtcNow.ToString("o")
    }
}

$usage = $null
try {
    $usage = Invoke-RestMethod -Method Get -Uri "http://127.0.0.1:18011/usage/token-savings?tenant=phase1-tenant&agent=codex" -TimeoutSec 5
} catch {}

$passCount = ($results | Where-Object { $_.ok }).Count
$failCount = $Cycles - $passCount

$lines = @()
$lines += "# Phase 1 Step 1 Restart Validation"
$lines += ""
$lines += "- Timestamp (UTC): $([DateTime]::UtcNow.ToString("yyyy-MM-dd HH:mm:ss"))"
$lines += "- Cycles: $Cycles"
$lines += "- Passed: $passCount"
$lines += "- Failed: $failCount"
$lines += "- Runtime log: $runtimeOut"
$lines += "- Adapter log: $adapterOut"
$lines += ""
$lines += "## Cycle Results"
$lines += ""
$lines += "| Cycle | Result | Notes | UTC |"
$lines += "|---|---|---|---|"
foreach ($r in $results) {
    $state = if ($r.ok) { "PASS" } else { "FAIL" }
    $noteText = if ($r.notes) { $r.notes } else { "-" }
    $lines += "| $($r.cycle) | $state | $noteText | $($r.ts_utc) |"
}
$lines += ""
$lines += "## Adapter Usage Snapshot"
$lines += ""
if ($null -ne $usage) {
    $lines += "- tenant: $($usage.tenant)"
    $lines += "- request_count: $($usage.request_count)"
    $lines += "- saved_tokens_total: $($usage.saved_tokens_total)"
    $lines += "- average_savings_ratio: $($usage.average_savings_ratio)"
} else {
    $lines += "- usage endpoint: unavailable"
}

Set-Content -Path $reportPath -Value $lines -Encoding UTF8
Write-Output $reportPath
