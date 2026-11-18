@echo off
setlocal
set "PYTHONPATH=%~dp0;%PYTHONPATH%"
rem 安裝方式記錄在 .wkt-env（由 install.cmd／wkt install 寫入）：venv 用專案的 .venv，其餘用全域 Python
findstr /x /i /c:"venv" "%~dp0.wkt-env" >nul 2>&1 || goto global
if not exist "%~dp0.venv\Scripts\python.exe" goto global
"%~dp0.venv\Scripts\python.exe" -m wkt %*
exit /b %errorlevel%
:global
py -3 -m wkt %*
exit /b %errorlevel%
