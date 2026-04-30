@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo ========================================
echo  ContentUploader - Build Script
echo ========================================
echo.

echo [1/5] Checking Python...
where python >nul 2>nul
if errorlevel 1 (
    echo ERROR: Python is not on PATH. Install Python 3.12+ from python.org and re-run.
    pause
    exit /b 1
)

echo [2/5] Creating venv if missing...
if not exist .venv\Scripts\python.exe (
    python -m venv .venv
    if errorlevel 1 (
        echo ERROR: Failed to create venv.
        pause
        exit /b 1
    )
)
call .venv\Scripts\activate.bat

echo [3/5] Installing Python dependencies...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
if errorlevel 1 (
    echo ERROR: Failed to install requirements.
    pause
    exit /b 1
)

echo [4/5] Installing Playwright Chromium browser...
python -m playwright install chromium
if errorlevel 1 (
    echo WARNING: Failed to install Playwright browser. The app will try to install it on first run.
)

echo [5/5] Building exe with PyInstaller...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist ContentUploader.spec del /q ContentUploader.spec

set ICON_FLAG=
if exist assets\icon.ico set ICON_FLAG=--icon=assets\icon.ico

python -m PyInstaller --noconfirm --onefile --windowed ^
    --name "ContentUploader" ^
    %ICON_FLAG% ^
    --collect-all PySide6 ^
    --collect-all playwright ^
    --collect-all keyring ^
    --hidden-import apscheduler ^
    --hidden-import filetype ^
    main.py
if errorlevel 1 (
    echo ERROR: PyInstaller build failed.
    pause
    exit /b 1
)

echo.
echo ========================================
echo  Build successful.
echo  Output: dist\ContentUploader.exe
echo ========================================
echo.
pause
endlocal
