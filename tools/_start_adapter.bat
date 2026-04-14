@echo off
REM _start_adapter.bat - 内部用：启动 OmniMemora Adapter
setlocal
set PORT=%1
cd /d "%~dp0.."
python -c "import sys,os,importlib,uvicorn;sys.path.insert(0,'.');mod=importlib.import_module('5_connectors.adapter.main');uvicorn.run(mod.app,host='127.0.0.1',port=%PORT%,log_level='info')"
