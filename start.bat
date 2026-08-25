@echo off
chcp 65001 >nul
title FB Auto Poster

set "PYEXE=%~dp0python\python.exe"
set "PYTHONPATH=%~dp0lib"
set "PLAYWRIGHT_BROWSERS_PATH=%~dp0browsers"

:: Kiem tra da cai chua
if not exist "%~dp0lib\flask" (
    echo.
    echo [!] Chua cai dat! Hay chay install.bat truoc.
    echo.
    pause
    exit /b 1
)

echo.
echo Dang kiem tra cap nhat...
"%PYEXE%" "%~dp0updater.py"
