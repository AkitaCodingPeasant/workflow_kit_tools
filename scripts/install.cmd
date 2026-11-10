@echo off
rem WKT 一鍵安裝。可加參數：-CheckOnly（只檢查）、-Yes（不詢問）、-NoPath、-NoMenu
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1" %*
set "WKT_EXIT_CODE=%errorlevel%"
echo.
pause
exit /b %WKT_EXIT_CODE%
