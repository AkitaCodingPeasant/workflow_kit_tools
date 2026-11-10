@echo off
call "%~dp0..\wkt.cmd" menu register
set "WKT_EXIT_CODE=%errorlevel%"
echo.
pause
exit /b %WKT_EXIT_CODE%
