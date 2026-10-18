@echo off
cd /d "%~dp0"
title BreakTimer Ultra Launcher

echo ==================================================
echo   BreakTimer Ultra - Fullscreen Protected Timer
echo ==================================================
echo 起動中... (Starting BreakTimer Ultra...)

:: Try pythonw first for clean background execution, or python if pythonw is not found
where pythonw >nul 2>nul
if %ERRORLEVEL% equ 0 (
    start "" pythonw main.py
) else (
    start "" python main.py
)

exit
