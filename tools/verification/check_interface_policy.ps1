# check_interface_policy.ps1
# OmniMemora Interface Policy Acceptance Check
# Validates that the product entry path is unified at 18011 and no stale 8765 references exist.
#
# FAIL conditions:
#   1. Codex config contains legacy [omnimemora] block or "8765" endpoint
#   2. Codex config does NOT contain [mcp_servers.omnimemora]
#   3. Adapter /health does not return interface_policy field
#   4. Adapter /mcp does not return ok
#   5. OpenClaw config contains "8765" endpoint (not 18011)
#   6. Claude/Cursor config contains "8765" endpoint (not 18011)
#
# Usage:
#   powershell -File tools/verification/check_interface_policy.ps1

$ErrorActionPreference = "Continue"
$FAIL = $false

function Get-CodexConfigPath {
    $userHome = $env:USERPROFILE
    Join-Path $userHome ".codex\config.toml"
}

function Get-OpenClawConfigPath {
    $userHome = $env:USERPROFILE
    Join-Path $userHome ".openclaw\openclaw.json"
}

function Get-ClaudeConfigPath {
    $userHome = $env:USERPROFILE
    $settings = Join-Path $userHome ".claude\settings.json"
    if (Test-Path $settings) { return $settings }
    return Join-Path $userHome ".claude.json"
}

function Get-CursorConfigPath {
    if ($env:APPDATA) {
        $settings = Join-Path $env:APPDATA "Cursor\config\settings.json"
        if (Test-Path $settings) { return $settings }
    }
    $userHome = $env:USERPROFILE
    return Join-Path $userHome ".cursor\config\settings.json"
}

function Test-TOMLContains {
    param($path, $pattern)
    if (-not (Test-Path $path)) { return $false }
    $content = Get-Content $path -Raw -ErrorAction SilentlyContinue
    if (-not $content) { return $false }
    return $content -match $pattern
}

function Test-JSONContains {
    param($path, $pattern)
    if (-not (Test-Path $path)) { return $false }
    $content = Get-Content $path -Raw -ErrorAction SilentlyContinue
    if (-not $content) { return $false }
    # Check for 8765 in URL strings
    if ($pattern -eq "8765") {
        return $content -match '":\s*"[^"]*8765' -or $content -match "8765"
    }
    return $content -match $pattern
}

function Test-JSONNotContains {
    param($path, $pattern)
    return -not (Test-JSONContains -path $path -pattern $pattern)
}

function Invoke-AdapterCheck {
    param($path, $description)
    Write-Host "  CHECK: $description" -ForegroundColor Cyan

    try {
        $r = Invoke-RestMethod -Uri $path -TimeoutSec 5 -ErrorAction Stop
        return $r
    } catch {
        Write-Host "    WARN: could not reach $path — $_" -ForegroundColor Yellow
        return $null
    }
}

Write-Host ""
Write-Host "===============================================" -ForegroundColor Gray
Write-Host " OmniMemora Interface Policy Acceptance Check" -ForegroundColor White
Write-Host "===============================================" -ForegroundColor Gray
Write-Host ""

# ---------------------------------------------------------------------------
# 1. Adapter /mcp health probe
# ---------------------------------------------------------------------------
Write-Host "[1/6] Adapter MCP endpoint" -ForegroundColor Yellow
$mcp = Invoke-AdapterCheck -path "http://127.0.0.1:18011/mcp" -description "GET /mcp returns ok"
if ($mcp) {
    if ($mcp.status -eq "ok") {
        Write-Host "    PASS: /mcp status=ok" -ForegroundColor Green
    } else {
        Write-Host "    FAIL: /mcp status=$($mcp.status)" -ForegroundColor Red
        $FAIL = $true
    }
} else {
    Write-Host "    FAIL: /mcp unreachable" -ForegroundColor Red
    $FAIL = $true
}

# ---------------------------------------------------------------------------
# 2. Adapter /health interface_policy field
# ---------------------------------------------------------------------------
Write-Host ""
Write-Host "[2/6] Adapter /health interface_policy field" -ForegroundColor Yellow
$health = Invoke-AdapterCheck -path "http://127.0.0.1:18011/health?mode=local" -description "GET /health?mode=local has interface_policy"
if ($health) {
    if ($health.interface_policy) {
        $policy = $health.interface_policy
        Write-Host "    PASS: interface_policy present" -ForegroundColor Green
        Write-Host "    product_entry_port=$($policy.product_entry_port)" -ForegroundColor Gray
        Write-Host "    mcp_endpoint=$($policy.mcp_endpoint)" -ForegroundColor Gray
        Write-Host "    internal_backend_port=$($policy.internal_backend_port)" -ForegroundColor Gray
        if ($policy.product_entry_port -ne 18011) {
            Write-Host "    FAIL: product_entry_port should be 18011, got $($policy.product_entry_port)" -ForegroundColor Red
            $FAIL = $true
        }
        if ($policy.internal_backend_port -ne 8765) {
            Write-Host "    FAIL: internal_backend_port should be 8765, got $($policy.internal_backend_port)" -ForegroundColor Red
            $FAIL = $true
        }
    } else {
        Write-Host "    FAIL: interface_policy field missing from /health" -ForegroundColor Red
        $FAIL = $true
    }
} else {
    Write-Host "    FAIL: /health unreachable" -ForegroundColor Red
    $FAIL = $true
}

# ---------------------------------------------------------------------------
# 3. Codex config: no legacy [omnimemora] block
# ---------------------------------------------------------------------------
Write-Host ""
Write-Host "[3/6] Codex config — legacy [omnimemora] block check" -ForegroundColor Yellow
$codexPath = Get-CodexConfigPath
Write-Host "    Config: $codexPath" -ForegroundColor Gray

if (Test-Path $codexPath) {
    $content = Get-Content $codexPath -Raw -ErrorAction SilentlyContinue

    # Check for legacy [omnimemora] TOML block (wrong format)
    if ($content -match '\[omnimemora\]') {
        Write-Host "    FAIL: legacy [omnimemora] block found — should use [mcp_servers.omnimemora]" -ForegroundColor Red
        $FAIL = $true
    } else {
        Write-Host "    PASS: no legacy [omnimemora] block" -ForegroundColor Green
    }

    # Check for direct 8765 endpoint reference
    if ($content -match '8765') {
        Write-Host "    FAIL: 8765 endpoint found in Codex config — must use adapter at 18011" -ForegroundColor Red
        $FAIL = $true
    } else {
        Write-Host "    PASS: no 8765 reference" -ForegroundColor Green
    }

    # Check that MCP server block exists
    if ($content -match '\[mcp_servers\.omnimemora\]') {
        Write-Host "    PASS: [mcp_servers.omnimemora] block present" -ForegroundColor Green
    } else {
        Write-Host "    FAIL: [mcp_servers.omnimemora] block missing — Codex MCP shim not configured" -ForegroundColor Red
        $FAIL = $true
    }
} else {
    Write-Host "    INFO: Codex config not found (skipping)" -ForegroundColor DarkGray
}

# ---------------------------------------------------------------------------
# 4. OpenClaw config: 8765 check
# ---------------------------------------------------------------------------
Write-Host ""
Write-Host "[4/6] OpenClaw config — endpoint port check" -ForegroundColor Yellow
$openclawPath = Get-OpenClawConfigPath
Write-Host "    Config: $openclawPath" -ForegroundColor Gray

if (Test-Path $openclawPath) {
    $content = Get-Content $openclawPath -Raw -ErrorAction SilentlyContinue
    if ($content -match '":\s*"[^"]*8765') {
        Write-Host "    FAIL: 8765 endpoint found in OpenClaw config — must use 18011" -ForegroundColor Red
        $FAIL = $true
    } else {
        Write-Host "    PASS: no 8765 reference" -ForegroundColor Green
    }
} else {
    Write-Host "    INFO: OpenClaw config not found (skipping)" -ForegroundColor DarkGray
}

# ---------------------------------------------------------------------------
# 5. Claude config: 8765 check
# ---------------------------------------------------------------------------
Write-Host ""
Write-Host "[5/6] Claude config — endpoint port check" -ForegroundColor Yellow
$claudePath = Get-ClaudeConfigPath
Write-Host "    Config: $claudePath" -ForegroundColor Gray

if (Test-Path $claudePath) {
    $content = Get-Content $claudePath -Raw -ErrorAction SilentlyContinue
    if ($content -match '":\s*"[^"]*8765') {
        Write-Host "    FAIL: 8765 endpoint found in Claude config — must use 18011" -ForegroundColor Red
        $FAIL = $true
    } else {
        Write-Host "    PASS: no 8765 reference" -ForegroundColor Green
    }
} else {
    Write-Host "    INFO: Claude config not found (skipping)" -ForegroundColor DarkGray
}

# ---------------------------------------------------------------------------
# 6. Cursor config: 8765 check
# ---------------------------------------------------------------------------
Write-Host ""
Write-Host "[6/6] Cursor config — endpoint port check" -ForegroundColor Yellow
$cursorPath = Get-CursorConfigPath
Write-Host "    Config: $cursorPath" -ForegroundColor Gray

if (Test-Path $cursorPath) {
    $content = Get-Content $cursorPath -Raw -ErrorAction SilentlyContinue
    if ($content -match '":\s*"[^"]*8765') {
        Write-Host "    FAIL: 8765 endpoint found in Cursor config — must use 18011" -ForegroundColor Red
        $FAIL = $true
    } else {
        Write-Host "    PASS: no 8765 reference" -ForegroundColor Green
    }
} else {
    Write-Host "    INFO: Cursor config not found (skipping)" -ForegroundColor DarkGray
}

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
Write-Host ""
Write-Host "===============================================" -ForegroundColor Gray
if ($FAIL) {
    Write-Host "RESULT: FAIL — interface policy violations detected" -ForegroundColor Red
    exit 1
} else {
    Write-Host "RESULT: PASS — all interface policy checks passed" -ForegroundColor Green
    exit 0
}
