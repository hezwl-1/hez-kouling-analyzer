@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
title hez-kouling-analyzer - Install

echo.
echo  ============================================
echo    hez-kouling-analyzer  -  Install
echo  ============================================
echo.

set "SKILL_NAME=hez口令解析分析"
set "SRC=%~dp0"
set "TARGET=%USERPROFILE%\.workbuddy-ai\skills"

REM --- sanity check: are we inside the repo? ---
if not exist "%SRC%SKILL.md" (
    echo  [ERROR] SKILL.md not found next to this script.
    echo          Run install.cmd from inside the cloned repository.
    echo.
    pause
    exit /b 1
)

echo  Source : %SRC%
echo  Target : %TARGET%\%SKILL_NAME%
echo.

if not exist "%TARGET%" mkdir "%TARGET%"

REM --- back up an existing install instead of clobbering it ---
if exist "%TARGET%\%SKILL_NAME%" (
    echo  [!] An existing install was found.
    set /p CONFIRM="      Back it up and replace? (Y/N) "
    if /i not "!CONFIRM!"=="Y" (
        echo  Cancelled.
        pause
        exit /b 0
    )
    for /f "tokens=2-4 delims=/ " %%a in ("%DATE%") do set "D=%%c%%a%%b"
    for /f "tokens=1-3 delims=:." %%a in ("%TIME: =0%") do set "T=%%a%%b%%c"
    set "BAK=%TARGET%\%SKILL_NAME%.bak-!D!-!T!"
    move "%TARGET%\%SKILL_NAME%" "!BAK!" >nul
    echo  Backed up to: !BAK!
)

echo  Copying...
xcopy "%SRC%SKILL.md"   "%TARGET%\%SKILL_NAME%\" /Q /Y >nul
xcopy "%SRC%scripts"    "%TARGET%\%SKILL_NAME%\scripts\"    /E /I /Q /Y >nul
xcopy "%SRC%references" "%TARGET%\%SKILL_NAME%\references\" /E /I /Q /Y >nul

echo.
if exist "%TARGET%\%SKILL_NAME%\SKILL.md" (
    echo  [OK] Installed.
    echo       %TARGET%\%SKILL_NAME%
    echo.
    echo  Next:
    echo    1. Restart WorkBuddy so the skill list refreshes
    echo    2. Say: 用 hez口令解析分析 帮我看看这个包的口令接口
    echo.
    echo  Verify the parser:
    python "%TARGET%\%SKILL_NAME%\scripts\dex_tool.py"
) else (
    echo  [FAIL] Copy failed. Check permissions on %TARGET%
)
echo.
pause