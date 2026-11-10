@echo off
rem WKT 一鍵安裝（第一次安裝只需要雙擊這個檔案；之後的操作都用 wkt 指令）。
rem 可加參數：-CheckOnly（只檢查）、-Yes（不詢問）、-NoPath、-NoMenu
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\install.ps1" %*
set "WKT_EXIT_CODE=%errorlevel%"
echo.
pause
exit /b %WKT_EXIT_CODE%
