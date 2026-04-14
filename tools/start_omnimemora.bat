@echo off
REM ============================================================================
REM start_omnimemora.bat  -  一键启动 OmniMemora 双服务
REM
REM 启动内容：
REM   1. OmniMemora Go Runtime (MCP SSE，:8765)
REM      - Internal MCP server for Adapter ↔ Runtime communication
REM      - Dashboard: http://127.0.0.1:8765/dashboard
REM   2. OmniMemora Python Adapter (REST，:18011)
REM      - Wrapper / CLI 调用入口
REM      - Dashboard: http://127.0.0.1:8501
REM
REM 关闭：关闭两个黑窗口，或任务管理器结束 python.exe / omnimemora.exe
REM ============================================================================
setlocal

REM ---- 找 omnimemora.exe ----
REM 优先用 tools/ 下的（本次编译版本），其次 PATH
set "OMNI_EXE="
if exist "%~dp0omnimemora.exe" (
    set "OMNI_EXE=%~dp0omnimemora.exe"
) else (
    for %%e in (omnimemora.exe) do (
        set "OMNI_EXE=%%~$PATH:e"
    )
)

REM ---- 1. 启动 Go Runtime (MCP，8765) ----
if not defined OMNI_EXE (
    echo [ERROR] omnimemora.exe not found. Build it with:
    echo   cd 4_core\local-runtime ^&^& go build -o tools\omnimemora.exe .\cmd\omnimemora
    pause
    exit /b 1
)

echo [1/2] Starting OmniMemora Go Runtime (MCP) on http://127.0.0.1:8765 ...
start "OmniMemora Runtime (8765)" cmd /k "%OMNI_EXE%" serve

REM ---- 等 Go Runtime 就绪 ----
echo Waiting for Go Runtime ...
for /L %%n in (1,1,10) do (
    curl -s --max-time 2 http://127.0.0.1:8765/health >nul 2>&1
    if not errorlevel 1 goto :runtime_ready
    timeout /t 2 /nobreak >nul
)
echo [WARNING] Go Runtime may not have started. Check its window.
goto :start_python

:runtime_ready
echo [OK] Go Runtime is up at http://127.0.0.1:8765

:start_python
REM ---- 2. 启动 Python REST Adapter (18011) ----
echo [2/2] Starting OmniMemora Python Adapter on http://127.0.0.1:18011 ...
start "OmniMemora Adapter (18011)" cmd /k python -c "import sys,os,importlib,uvicorn;sys.path.insert(0,'.');mod=importlib.import_module('5_connectors.adapter.main');uvicorn.run(mod.app,host='127.0.0.1',port=18011,log_level='info')"

REM ---- 等 Python Adapter 就绪 ----
echo Waiting for Python Adapter ...
for /L %%n in (1,1,10) do (
    curl -s --max-time 2 http://127.0.0.1:18011/health?mode=local >nul 2>&1
    if not errorlevel 1 goto :adapter_ready
    timeout /t 2 /nobreak >nul
)
echo [WARNING] Python Adapter may not have started. Check its window.
goto :done

:adapter_ready
echo [OK] Python Adapter is up at http://127.0.0.1:18011

:done
echo.
echo All services started:
echo   Go Runtime  - http://127.0.0.1:8765  ^(MCP SSE for Adapter^)
echo   Adapter     - http://127.0.0.1:18011  ^(REST API for wrappers^)
echo.
echo Press any key to close this launcher ...
pause >nul
