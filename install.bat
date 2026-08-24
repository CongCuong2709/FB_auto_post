@echo off
chcp 65001 >nul
title FB Auto Poster — Cài đặt
echo.
echo  ╔══════════════════════════════════════╗
echo  ║   FB Auto Poster — Cài đặt lần đầu  ║
echo  ╚══════════════════════════════════════╝
echo.

:: Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo  [LỖI] Chưa cài Python! Tải tại: https://python.org/downloads
    echo  Nhớ tick "Add Python to PATH" khi cài!
    pause
    exit /b 1
)

echo  [1/3] Cài thư viện Python...
python -m pip install --upgrade pip -q
python -m pip install -r requirements.txt -q
if errorlevel 1 (
    echo  [LỖI] Cài thư viện thất bại!
    pause
    exit /b 1
)

echo  [2/3] Cài trình duyệt Chromium cho Playwright...
python -m playwright install chromium
if errorlevel 1 (
    echo  [LỖI] Cài Playwright thất bại!
    pause
    exit /b 1
)

echo  [3/3] Tạo thư mục dữ liệu...
if not exist "data" mkdir data
if not exist "chrome_profile" mkdir chrome_profile

echo.
echo  ╔══════════════════════════════════════╗
echo  ║   ✅  Cài đặt hoàn tất!             ║
echo  ║   Chạy start.bat để sử dụng         ║
echo  ╚══════════════════════════════════════╝
echo.
pause
