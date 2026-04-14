@echo off
REM ============================================================================
REM OmniMemora Quick Recovery Test
REM 执行三实例恢复测试的快速检查脚本
REM ============================================================================
echo.
echo === OmniMemora Recovery Test ===
echo.

echo [T1] Checking Go Runtime on 8765...
curl -s --max-time 3 http://127.0.0.1:8765/health >nul 2>&1
if %errorlevel%==0 (
    echo  [PASS] Go Runtime is UP
) else (
    echo  [FAIL] Go Runtime is DOWN - run tools\start_omnimemora.bat
)
echo.

echo [T2] Checking Python Adapter on 18011...
curl -s --max-time 3 "http://127.0.0.1:18011/health?mode=local" >nul 2>&1
if %errorlevel%==0 (
    echo  [PASS] Adapter is UP
) else (
    echo  [FAIL] Adapter is DOWN - run: python tools\_run_adapter.py
)
echo.

echo [T3] Testing Query Path (18011 query)...
curl -s -X POST http://127.0.0.1:18011/memory/query -H "Content-Type: application/json" -d "{\"tenant\":\"test-tenant\",\"user\":\"test-user\",\"agent\":\"openclaw\",\"query\":\"test query\",\"options\":{\"max_local_cards\":4}}" >nul 2>&1
if %errorlevel%==0 (
    echo  [PASS] Query path OK
) else (
    echo  [FAIL] Query path FAILED
)
echo.

echo [T8] Testing Implementation Bypass...
curl -s -X POST http://127.0.0.1:18011/memory/query -H "Content-Type: application/json" -d "{\"tenant\":\"test-tenant\",\"user\":\"test-user\",\"agent\":\"openclaw\",\"query\":\"write code for login\"}" | findstr /C:"implementation" >nul 2>&1
if %errorlevel%==0 (
    echo  [PASS] Implementation bypass OK
) else (
    echo  [FAIL] Implementation bypass FAILED
)
echo.

echo [T9] Testing Decision Non-Bypass...
curl -s -X POST http://127.0.0.1:18011/memory/query -H "Content-Type: application/json" -d "{\"tenant\":\"test-tenant\",\"user\":\"test-user\",\"agent\":\"openclaw\",\"query\":\"which database should i choose\"}" | findstr /C:"decision" >nul 2>&1
if %errorlevel%==0 (
    echo  [PASS] Decision path OK
) else (
    echo  [FAIL] Decision path FAILED
)
echo.
echo === Quick Test Complete ===
echo.
pause
