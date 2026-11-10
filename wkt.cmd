@echo off
setlocal
set "PYTHONPATH=%~dp0;%PYTHONPATH%"
py -3 -m wkt %*
exit /b %errorlevel%
