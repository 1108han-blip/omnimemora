# Phase 2 Hardcoding Scan

- Timestamp (UTC): 2026-04-12 19:38:33
- Scope: 4_core, 5_connectors, tools, root startup/config files
- Findings: 85

## Findings

| File | Line | Pattern | Snippet |
|---|---:|---|---|
| .env.example | 9 | 127\.0\.0\.1:8765 | MEMORY_BACKEND_URL=http://127.0.0.1:8765 |
| 4_core\adapter-raw\docker-compose.yml | 44 | localhost | "import sys, urllib.request; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/health', timeout=5).getcode() == 200 else 1)", |
| 4_core\local-runtime\.gitignore | 3 | omnimemora\.exe | omnimemora.exe |
| 4_core\local-runtime\internal\cli\commands.go | 530 | localhost | req, _ := http.NewRequest("POST", fmt.Sprintf("http://localhost:%d/shutdown", port), nil) |
| 4_core\local-runtime\internal\demo\seed.go | 138 | localhost | return fmt.Sprintf("http://localhost:%d", port) |
| 4_core\local-runtime\README.txt | 12 | omnimemora\.exe | 2. Double-click `omnimemora.exe` or run: `omnimemora start` |
| 4_core\local-runtime\README.txt | 73 | 127\.0\.0\.1:8765 | Access at: http://127.0.0.1:8765/dashboard |
| 4_core\local-runtime\runtime.err.log | 1 | 127\.0\.0\.1:8765 | 2026/04/10 01:49:10 Server listening on 127.0.0.1:8765 |
| 4_core\local-runtime\scripts\release\README.txt | 12 | omnimemora\.exe | 2. Run: `./omnimemora start` (or `omnimemora.exe start` on Windows) |
| 5_connectors\adapter\backends\factory.py | 36 | 127\.0\.0\.1:8765 | base_url: str = "http://127.0.0.1:8765", |
| 5_connectors\adapter\backends\factory.py | 89 | 127\.0\.0\.1:8765 | default_omnimemora_url = 'http://127.0.0.1:8765' |
| 5_connectors\adapter\backends\omnimemora_runtime_backend.py | 31 | 127\.0\.0\.1:8765 | base_url: str = "http://127.0.0.1:8765", |
| 5_connectors\adapter\config.py | 12 | 127\.0\.0\.1:8765 | base_url: str = os.getenv("MEMORY_BACKEND_URL", "http://127.0.0.1:8765") |
| 5_connectors\omni-omnimemora-plugin\README.md | 82 | localhost | curl http://localhost:8000/health |
| 5_connectors\omni-omnimemora-plugin\README.md | 106 | localhost | 3. `curl http://localhost:8000/health` - 测试健康端点 |
| Makefile | 13 | 127\.0\.0\.1:8765 | curl -fsS http://127.0.0.1:8765/health |
| Makefile | 14 | 127\.0\.0\.1:18011 | curl -fsS http://127.0.0.1:18011/health |
| start.sh | 10 | omnimemora\.exe | RUNTIME_EXE_LEGACY="$ROOT_DIR/tools/omnimemora.exe" |
| tools\dashboard.py | 40 | 127\.0\.0\.1:18011 | ADAPTER_URL = os.getenv("OMNIMEMORA_ADAPTER_URL", "http://127.0.0.1:18011") |
| tools\memrun.py | 32 | 127\.0\.0\.1:18011 | ADAPTER_URL = os.getenv("OMNIMEMORA_ADAPTER_URL", "http://127.0.0.1:18011") |
| tools\memrun.py | 54 | 127\.0\.0\.1:18011 | Stage 2: Fall back to TCP port probe on 127.0.0.1:18011. |
| tools\memrun.py | 85 | 127\.0\.0\.1:18011 | 2. TCP probe   → connect 127.0.0.1:18011 (fallback if /health absent) |
| tools\quick_recovery_test.bat | 11 | 127\.0\.0\.1:8765 | curl -s --max-time 3 http://127.0.0.1:8765/health >nul 2>&1 |
| tools\quick_recovery_test.bat | 20 | 127\.0\.0\.1:18011 | curl -s --max-time 3 "http://127.0.0.1:18011/health?mode=local" >nul 2>&1 |
| tools\quick_recovery_test.bat | 29 | 127\.0\.0\.1:18011 | curl -s -X POST http://127.0.0.1:18011/memory/query -H "Content-Type: application/json" -d "{\"tenant\":\"test-tenant\",\"user\":\"test-user\",\"agent\":\"openclaw\",\"query\":\"test query\",\"options\":{\"max_local_cards\":4}}" >nul 2>&1 |
| tools\quick_recovery_test.bat | 38 | 127\.0\.0\.1:18011 | curl -s -X POST http://127.0.0.1:18011/memory/query -H "Content-Type: application/json" -d "{\"tenant\":\"test-tenant\",\"user\":\"test-user\",\"agent\":\"openclaw\",\"query\":\"write code for login\"}" / findstr /C:"implementation" >nul 2>&1 |
| tools\quick_recovery_test.bat | 47 | 127\.0\.0\.1:18011 | curl -s -X POST http://127.0.0.1:18011/memory/query -H "Content-Type: application/json" -d "{\"tenant\":\"test-tenant\",\"user\":\"test-user\",\"agent\":\"openclaw\",\"query\":\"which database should i choose\"}" / findstr /C:"decision" >nul 2>&1 |
| tools\README.md | 23 | omnimemora\.exe | ├── omnimemora.exe          # Go Runtime 二进制（今日编译版，:8765） |
| tools\README.md | 55 | 127\.0\.0\.1:8765 | curl http://127.0.0.1:8765/health |
| tools\README.md | 59 | 127\.0\.0\.1:18011 | curl http://127.0.0.1:18011/health?mode=local |
| tools\README.md | 163 | 127\.0\.0\.1:18011 | / `OMNIMEMORA_ADAPTER_URL` / `http://127.0.0.1:18011` / adapter 服务地址 / |
| tools\README.md | 195 | 127\.0\.0\.1:18011 | - 新 OmniMemora：`127.0.0.1:18011`（Windows Python 进程） |
| tools\start_omnimemora.bat | 8 | 127\.0\.0\.1:8765 | REM      - Dashboard: http://127.0.0.1:8765/dashboard |
| tools\start_omnimemora.bat | 13 | omnimemora\.exe | REM 关闭：关闭两个黑窗口，或任务管理器结束 python.exe / omnimemora.exe |
| tools\start_omnimemora.bat | 17 | omnimemora\.exe | REM ---- 找 omnimemora.exe ---- |
| tools\start_omnimemora.bat | 20 | omnimemora\.exe | if exist "%~dp0omnimemora.exe" ( |
| tools\start_omnimemora.bat | 21 | omnimemora\.exe | set "OMNI_EXE=%~dp0omnimemora.exe" |
| tools\start_omnimemora.bat | 23 | omnimemora\.exe | for %%e in (omnimemora.exe) do ( |
| tools\start_omnimemora.bat | 30 | omnimemora\.exe | echo [ERROR] omnimemora.exe not found. Build it with: |
| tools\start_omnimemora.bat | 31 | omnimemora\.exe | echo   cd 4_core\local-runtime ^&^& go build -o tools\omnimemora.exe .\cmd\omnimemora |
| tools\start_omnimemora.bat | 36 | 127\.0\.0\.1:8765 | echo [1/2] Starting OmniMemora Go Runtime (MCP) on http://127.0.0.1:8765 ... |
| tools\start_omnimemora.bat | 42 | 127\.0\.0\.1:8765 | curl -s --max-time 2 http://127.0.0.1:8765/health >nul 2>&1 |
| tools\start_omnimemora.bat | 50 | 127\.0\.0\.1:8765 | echo [OK] Go Runtime is up at http://127.0.0.1:8765 |
| tools\start_omnimemora.bat | 54 | 127\.0\.0\.1:18011 | echo [2/2] Starting OmniMemora Python Adapter on http://127.0.0.1:18011 ... |
| tools\start_omnimemora.bat | 60 | 127\.0\.0\.1:18011 | curl -s --max-time 2 http://127.0.0.1:18011/health?mode=local >nul 2>&1 |
| tools\start_omnimemora.bat | 68 | 127\.0\.0\.1:18011 | echo [OK] Python Adapter is up at http://127.0.0.1:18011 |
| tools\start_omnimemora.bat | 73 | 127\.0\.0\.1:8765 | echo   Go Runtime  - http://127.0.0.1:8765  ^(OpenClaw MCP^) |
| tools\start_omnimemora.bat | 74 | 127\.0\.0\.1:18011 | echo   Adapter     - http://127.0.0.1:18011  ^(REST API for wrappers^) |
| tools\verification\run_phase1_step1_restart_validation.ps1 | 20 | omnimemora\.exe | $runtimeExe = Join-Path $projectRoot "tools/omnimemora.exe" |
| tools\verification\run_phase1_step1_restart_validation.ps1 | 61 | 127\.0\.0\.1:8765 | $runtimeOk = Wait-Health -Url "http://127.0.0.1:8765/health" |
| tools\verification\run_phase1_step1_restart_validation.ps1 | 62 | 127\.0\.0\.1:18011 | $adapterOk = Wait-Health -Url "http://127.0.0.1:18011/health" |
| tools\verification\run_phase1_step1_restart_validation.ps1 | 89 | 127\.0\.0\.1:8765 | $writeResp = Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8765/memory/write" -Headers $headers -Body $writeBody -TimeoutSec 5 |
| tools\verification\run_phase1_step1_restart_validation.ps1 | 98 | 127\.0\.0\.1:8765 | $queryRespBefore = Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8765/memory/query" -Headers $headers -Body $queryBody -TimeoutSec 5 |
| tools\verification\run_phase1_step1_restart_validation.ps1 | 115 | 127\.0\.0\.1:8765 | $queryRespAfter = Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8765/memory/query" -Headers $headers -Body $queryBody -TimeoutSec 5 |
| tools\verification\run_phase1_step1_restart_validation.ps1 | 139 | 127\.0\.0\.1:18011 | $adapterResp = Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:18011/memory/query" -ContentType "application/json" -Body $adapterPayload -TimeoutSec 8 |
| tools\verification\run_phase1_step1_restart_validation.ps1 | 162 | 127\.0\.0\.1:18011 | $usage = Invoke-RestMethod -Method Get -Uri "http://127.0.0.1:18011/usage/token-savings?tenant=phase1-tenant&agent=codex" -TimeoutSec 5 |
| tools\verification\run_phase1_step2_step3_validation.ps1 | 47 | 127\.0\.0\.1:8765 | Invoke-RestMethod -Method Get -Uri "http://127.0.0.1:8765/health" -TimeoutSec 3 / Out-Null |
| tools\verification\run_phase1_step2_step3_validation.ps1 | 51 | 127\.0\.0\.1:18011 | Invoke-RestMethod -Method Get -Uri "http://127.0.0.1:18011/health" -TimeoutSec 3 / Out-Null |
| tools\verification\run_phase1_step2_step3_validation.ps1 | 58 | omnimemora\.exe | $runtimeBin = Join-Path $projectRoot "tools/omnimemora.exe" |
| tools\verification\run_phase1_step2_step3_validation.ps1 | 61 | 127\.0\.0\.1:8765 | $runtimeUp = Wait-Health -Url "http://127.0.0.1:8765/health" |
| tools\verification\run_phase1_step2_step3_validation.ps1 | 65 | 127\.0\.0\.1:18011 | $adapterUp = Wait-Health -Url "http://127.0.0.1:18011/health" |
| tools\verification\run_phase1_step2_step3_validation.ps1 | 138 | 127\.0\.0\.1:8765 | Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8765/memory/write" -Headers $hAgentA -Body (@{ content = "agent isolated $scopeToken" } / ConvertTo-Json) -TimeoutSec 5 / Out-Null |
| tools\verification\run_phase1_step2_step3_validation.ps1 | 139 | 127\.0\.0\.1:8765 | $agentBQuery = Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8765/memory/query" -Headers $hAgentB -Body (@{ query = $scopeToken; limit = 10 } / ConvertTo-Json) -TimeoutSec 5 |
| tools\verification\run_phase1_step2_step3_validation.ps1 | 143 | 127\.0\.0\.1:8765 | Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8765/memory/write" -Headers $hWorkspaceA -Body (@{ content = "workspace shared $scopeToken" } / ConvertTo-Json) -TimeoutSec 5 / Out-Null |
| tools\verification\run_phase1_step2_step3_validation.ps1 | 144 | 127\.0\.0\.1:8765 | $workspaceBQuery = Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8765/memory/query" -Headers $hWorkspaceB -Body (@{ query = $scopeToken; limit = 10 } / ConvertTo-Json) -TimeoutSec 5 |
| tools\verification\run_phase1_step2_step3_validation.ps1 | 148 | 127\.0\.0\.1:8765 | Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8765/memory/write" -Headers $hUser1 -Body (@{ content = "user isolated $scopeToken" } / ConvertTo-Json) -TimeoutSec 5 / Out-Null |
| tools\verification\run_phase1_step2_step3_validation.ps1 | 149 | 127\.0\.0\.1:8765 | $user2Query = Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8765/memory/query" -Headers $hUser2 -Body (@{ query = $scopeToken; limit = 10 } / ConvertTo-Json) -TimeoutSec 5 |
| tools\verification\run_phase1_step2_step3_validation.ps1 | 162 | 127\.0\.0\.1:8765 | $emptyQuery = Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8765/memory/query" -Headers $emptyHeaders -Body (@{ query = "nohit" + [guid]::NewGuid().ToString("N"); limit = 10 } / ConvertTo-Json) -TimeoutSec 5 |
| tools\verification\run_phase1_step2_step3_validation.ps1 | 169 | 127\.0\.0\.1:8765 | Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8765/memory/write" -Headers @{ |
| tools\verification\run_phase1_step2_step3_validation.ps1 | 193 | 127\.0\.0\.1:18011 | Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:18011/memory/query" -ContentType "application/json" -Body (@{ |
| tools\verification\run_phase1_step2_step3_validation.ps1 | 206 | omnimemora\.exe | $runtimeBin = Join-Path $projectRoot "tools/omnimemora.exe" |
| tools\verification\run_phase1_step2_step3_validation.ps1 | 209 | 127\.0\.0\.1:8765 | $runtimeRecovered = Wait-Health -Url "http://127.0.0.1:8765/health" |
| tools\verification\run_phase1_step2_step3_validation.ps1 | 212 | 127\.0\.0\.1:18011 | $postRecover = Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:18011/memory/query" -ContentType "application/json" -Body (@{ |
| tools\verification\run_phase1_step2_step3_validation.ps1 | 231 | 127\.0\.0\.1:18011 | Invoke-RestMethod -Method Get -Uri "http://127.0.0.1:18011/health" -TimeoutSec 3 / Out-Null |
| tools\verification\run_phase1_step2_step3_validation.ps1 | 238 | 127\.0\.0\.1:18011 | $adapterRecovered = Wait-Health -Url "http://127.0.0.1:18011/health" |
| tools\verification\run_phase1_step2_step3_validation.ps1 | 247 | 127\.0\.0\.1:18011 | $decisionResp = Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:18011/memory/query" -ContentType "application/json" -Body (@{ |
| tools\verification\run_phase1_step2_step3_validation.ps1 | 258 | 127\.0\.0\.1:18011 | $decisionMeter = Invoke-RestMethod -Method Get -Uri ("http://127.0.0.1:18011/requests/{0}/meter" -f $decisionResp.request_id) -TimeoutSec 6 |
| tools\verification\run_phase1_step2_step3_validation.ps1 | 264 | 127\.0\.0\.1:18011 | $implResp = Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:18011/memory/query" -ContentType "application/json" -Body (@{ |
| tools\verification\run_phase1_step2_step3_validation.ps1 | 276 | 127\.0\.0\.1:18011 | $usage = Invoke-RestMethod -Method Get -Uri ("http://127.0.0.1:18011/usage/token-savings?tenant={0}&agent=codex" -f $explainTenant) -TimeoutSec 6 |
| tools\verification\run_stability_probe.ps1 | 34 | 127\.0\.0\.1:18011 | return Invoke-RestMethod -Method Get -Uri "http://127.0.0.1:18011/usage/token-savings?tenant=$TenantName&agent=$AgentName" -TimeoutSec 5 |
| tools\verification\run_stability_probe.ps1 | 56 | 127\.0\.0\.1:8765 | $runtimeOk = Get-Health -Url "http://127.0.0.1:8765/health" |
| tools\verification\run_stability_probe.ps1 | 57 | 127\.0\.0\.1:18011 | $adapterOk = Get-Health -Url "http://127.0.0.1:18011/health" |
| tools\verification\run_stability_probe.ps1 | 81 | 127\.0\.0\.1:18011 | $resp = Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:18011/memory/query" -ContentType "application/json" -Body $payload -TimeoutSec 10 |
| tools\verification\scan_phase2_hardcoding.ps1 | 22 | C:\\\\ | "C:\\\\", |
| tools\verification\scan_phase2_hardcoding.ps1 | 23 | localhost | "localhost", |
