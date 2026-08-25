@echo off
chcp 65001 >nul
title FB Auto Poster - Cai dat

echo.
echo ============================================
echo   FB Auto Poster - Cai dat lan dau
echo ============================================
echo.

set "PYEXE=%~dp0python\python.exe"
set "LIB=%~dp0lib"
set "BROWSERS=%~dp0browsers"
set "PLAYWRIGHT_BROWSERS_PATH=%BROWSERS%"

:: Kiem tra Python noi bo
if not exist "%PYEXE%" (
    echo [LOI] Khong tim thay python\python.exe
    echo Hay dam bao thu muc python\ da giai nen dung cho.
    pause
    exit /b 1
)

:: Tao thu muc lib neu chua co
if not exist "%LIB%" mkdir "%LIB%"

:: --- Buoc 1: Cai pip vao lib\ ---
echo [1/4] Cai pip...
"%PYEXE%" -c "import urllib.request; urllib.request.urlretrieve('https://bootstrap.pypa.io/get-pip.py', r'%TEMP%\get-pip.py')"
if errorlevel 1 (
    echo [LOI] Khong tai duoc get-pip.py. Kiem tra ket noi mang.
    pause
    exit /b 1
)
:: Cai pip vao lib\ (pip se duoc tim thay nho ../lib trong _pth)
"%PYEXE%" "%TEMP%\get-pip.py" --target "%LIB%" --no-warn-script-location -q
if errorlevel 1 (
    echo [LOI] Cai pip that bai!
    pause
    exit /b 1
)

:: --- Buoc 2: Cai thu vien (dung pip truc tiep tu lib\) ---
echo [2/4] Cai thu vien Python vao lib\...
"%PYEXE%" "%LIB%\pip\__main__.py" install -r "%~dp0requirements.txt" --target "%LIB%" --no-warn-script-location -q
if errorlevel 1 (
    echo [LOI] Cai thu vien that bai!
    pause
    exit /b 1
)

:: --- Buoc 3: Cai Chromium ---
echo [3/4] Tai trinh duyet Chromium vao browsers\...
echo       (Lan dau co the mat 5-10 phut tuy mang)
"%PYEXE%" "%LIB%\pip\__main__.py" install playwright --target "%LIB%" --no-warn-script-location -q
"%PYEXE%" -m playwright install chromium
if errorlevel 1 (
    echo [LOI] Cai Playwright / Chromium that bai!
    pause
    exit /b 1
)

:: --- Buoc 4: Tao thu muc du lieu ---
echo [4/4] Tao thu muc du lieu...
if not exist "%~dp0data"           mkdir "%~dp0data"
if not exist "%~dp0chrome_profile" mkdir "%~dp0chrome_profile"

echo.
echo ============================================
echo   Cai dat hoan tat!
echo   Bam dup start.bat de su dung.
echo ============================================
echo.
pause
