param(
    [string]$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..\..")).Path,
    [string]$RunLabel = "daily",
    [int]$StaleAfterMinutes = 15,
    [string]$Tenant = "all",
    [string]$Salt = "omnimemora-default-salt"
)

$ErrorActionPreference = "Stop"

function Run-Step {
    param(
        [string]$Name,
        [scriptblock]$Action
    )
    Write-Output ("[START] " + $Name)
    & $Action
    Write-Output ("[PASS] " + $Name)
}

$scriptRoot = $PSScriptRoot
$archiveScript = Join-Path $scriptRoot "run_meter_archive.ps1"
$verifyScript = Join-Path $scriptRoot "verify_meter_archive.ps1"
$heartbeatScript = Join-Path $scriptRoot "check_meter_heartbeat.ps1"
$exportScript = Join-Path $scriptRoot "export_meter_anonymized.ps1"

Run-Step -Name "Archive Meter Data" -Action {
    powershell -ExecutionPolicy Bypass -File $archiveScript -ProjectRoot $ProjectRoot -RunLabel $RunLabel
}

Run-Step -Name "Verify Archive Integrity" -Action {
    powershell -ExecutionPolicy Bypass -File $verifyScript -ProjectRoot $ProjectRoot
}

Run-Step -Name "Check Meter Heartbeat" -Action {
    powershell -ExecutionPolicy Bypass -File $heartbeatScript -ProjectRoot $ProjectRoot -StaleAfterMinutes $StaleAfterMinutes
}

Run-Step -Name "Export Anonymized Dataset" -Action {
    powershell -ExecutionPolicy Bypass -File $exportScript -ProjectRoot $ProjectRoot -Tenant $Tenant -Salt $Salt
}

Write-Output ("[DONE] Data governance workflow completed.")

