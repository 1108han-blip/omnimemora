@echo off
setlocal enabledelayedexpansion

set "SCRIPT_DIR=%~dp0"
set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"

echo ============================================
echo OmniMemora Launcher
echo ============================================
echo.

:: Check if Python is available
python --version >/dev/null 2>&1
if errorlevel 1 (
    echo ERROR: Python not found. Please install Python 3.8+ first.
    echo Download: https://www.python.org/downloads/
    pause
    exit /b 1
)

:: Kill any existing instances on our ports
echo Cleaning up existing processes...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8765 ^| findstr LISTENING') do (
    echo Stopping Runtime on 8765 (PID: %%a)
    taskkill /F /PID %%a >/dev/null 2>&1
)
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :18011 ^| findstr LISTENING') do (
    echo Stopping Adapter on 18011 (PID: %%a)
    taskkill /F /PID %%a >/dev/null 2>&1
)

echo.
echo Starting OmniMemora Runtime (8765)...
start "OmniMemora Runtime" cmd /k "cd /d \"%SCRIPT_DIR%\4_core\local-runtime\" && omnimemora.exe"

timeout /t 2 /nobreak >/dev/null

echo Starting OmniMemora Adapter (18011)...
start "OmniMemora Adapter" cmd /k "cd /d \"%SCRIPT_DIR%\5_connectors\adapter\" && set PORT=18011 && set PYTHONPATH=\"%SCRIPT_DIR%\" && python -m uvicorn main:app --host 127.0.0.1 --port 18011"

echo.
echo Waiting for services to start...
timeout /t 5 /nobreak >/dev/null

echo.
echo ============================================
echo OmniMemora Services
echo ============================================
netstat -ano ^| findstr :8765 ^| findstr LISTENING && echo Runtime: RUNNING on 8765 || echo Runtime: NOT RUNNING
netstat -ano ^| findstr :18011 ^| findstr LISTENING && echo Adapter: RUNNING on 18011 || echo Adapter: NOT RUNNING
echo ============================================
echo.
echo Quick Test:
echo   curl http://127.0.0.1:8765/health
echo   curl http://127.0.0.1:18011/health
echo.
echo NOTE: Close this window to exit. Services keep running in background.
echo To stop: taskkill /F /FI "WINDOWTITLE eq OmniMemora*"
echo.
pause
