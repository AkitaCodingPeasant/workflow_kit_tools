@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0.."

py -3 -m unittest discover -s tests
if errorlevel 1 (
    echo 測試未通過，已中止更新。
    exit /b 1
)

py -3 -X utf8 scripts\build_portable.py
if errorlevel 1 (
    echo 可攜式安裝包建立失敗。
    exit /b 1
)

echo 已更新 dist\WKT-portable.zip，接著重新註冊這台電腦的右鍵選單。
call "%~dp0..\wkt.cmd" menu register
exit /b %errorlevel%
