@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo ========================================
echo  ContentUploader - Build Script
echo ========================================
echo.

echo [1/6] Checking Python...
where python >nul 2>nul
if errorlevel 1 (
    echo ERROR: Python is not on PATH. Install Python 3.12+ from python.org and re-run.
    exit /b 1
)

echo [2/6] Creating venv if missing...
if not exist .venv\Scripts\python.exe (
    python -m venv .venv
    if errorlevel 1 (
        echo ERROR: Failed to create venv.
        exit /b 1
    )
)
call .venv\Scripts\activate.bat

echo [3/6] Installing Python dependencies...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
if errorlevel 1 (
    echo ERROR: Failed to install requirements.
    exit /b 1
)

echo [4/6] Installing Playwright Chromium browser...
python -m playwright install chromium
if errorlevel 1 (
    echo WARNING: Failed to install Playwright browser. The app will try to use system Chrome.
)

echo [5/6] Killing any running ContentUploader...
taskkill /F /IM ContentUploader.exe >nul 2>&1
powershell -NoProfile -Command "Start-Sleep -Seconds 2"

REM Clean build artifacts (but NOT dist -- Defender may lock it)
if exist build rmdir /s /q build
if exist ContentUploader.spec del /q ContentUploader.spec
if exist dist_new rmdir /s /q dist_new

REM Clean any stale ContentUploader_*.exe junk files from dist
if exist dist (
    for %%F in (dist\ContentUploader_*.exe) do (
        echo Deleting stale: %%F
        del /q "%%F" 2>nul
    )
)

set ICON_FLAG=
if exist assets\icon.ico set ICON_FLAG=--icon=assets\icon.ico

echo [6/6] Building exe with PyInstaller...
REM Note: --collect-all playwright is intentionally NOT used. The 297MB bundled
REM exe gets quarantined by Windows Defender. The app uses channel="chrome" via
REM system-installed Chrome (resolved by app/browser/manager.py:_find_chrome_executable).
python -m PyInstaller --noconfirm --onefile --windowed ^
    --distpath dist_new ^
    --name "ContentUploader" ^
    %ICON_FLAG% ^
    --hidden-import apscheduler ^
    --hidden-import filetype ^
    --hidden-import playwright.sync_api ^
    main.py
if errorlevel 1 (
    echo ERROR: PyInstaller build failed.
    if exist dist_new rmdir /s /q dist_new
    exit /b 1
)

if not exist dist_new\ContentUploader.exe (
    echo ERROR: dist_new\ContentUploader.exe was not created.
    exit /b 1
)

REM Copy to Desktop (always overwrite)
for /f "usebackq tokens=*" %%D in (`powershell -NoProfile -Command "[Environment]::GetFolderPath('Desktop')"`) do set DESKTOP=%%D

if defined DESKTOP (
    echo Copying to Desktop: %DESKTOP%
    del /q "%DESKTOP%\ContentUploader.exe" 2>nul
    del /q "%DESKTOP%\ContentUploader_*.exe" 2>nul
    copy /Y "dist_new\ContentUploader.exe" "%DESKTOP%\ContentUploader.exe" >nul
    if errorlevel 1 (
        echo WARNING: Could not copy to Desktop.
    ) else (
        echo Copied to: %DESKTOP%\ContentUploader.exe
    )
) else (
    echo WARNING: Could not determine Desktop path.
)

REM Move into dist\ for consistency (best-effort, Defender may block)
if not exist dist mkdir dist
move /Y dist_new\ContentUploader.exe dist\ContentUploader.exe >nul 2>&1
if exist dist_new rmdir /s /q dist_new

echo.
echo ========================================
echo  Build successful.
echo  Output: dist\ContentUploader.exe
echo ========================================
echo.
endlocal
