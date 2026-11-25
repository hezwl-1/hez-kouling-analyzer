@echo off
chcp 65001 >nul
title 网易云口令解析器

echo.
echo   网易云口令解析器
echo   ─────────────────────────────────────
echo.

cd /d "%~dp0"

where node >nul 2>nul
if errorlevel 1 (
    echo   [错误] 没找到 Node.js
    echo   请先安装：https://nodejs.org/
    echo.
    pause
    exit /b 1
)

echo   正在启动本地服务...
echo   浏览器将自动打开 http://127.0.0.1:8899
echo.
echo   关闭此窗口即可停止服务
echo.

start "" http://127.0.0.1:8899
node server.js

pause