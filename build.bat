@echo off
chcp 65001 >nul
title Build WhalesBot.exe
echo ========================================
echo    Building WhalesBot.exe
echo ========================================
echo.

set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%"

REM Pick Python: prefer .venv, then venv, then system
if exist "%SCRIPT_DIR%.venv\Scripts\python.exe" (
    set "PY=%SCRIPT_DIR%.venv\Scripts\python.exe"
    echo [OK] Using .venv Python
) else if exist "%SCRIPT_DIR%venv\Scripts\python.exe" (
    set "PY=%SCRIPT_DIR%venv\Scripts\python.exe"
    echo [OK] Using venv Python
) else (
    where python >nul 2>&1
    if errorlevel 1 (
        echo [ERROR] Python not found. Run setup.bat first.
        pause
        exit /b 1
    )
    set "PY=python"
    echo [WARN] Using system Python
)

REM Install project dependencies into the same Python PyInstaller will use,
REM otherwise PyInstaller can't bundle imports it doesn't see.
if exist "%SCRIPT_DIR%requirements.txt" (
    echo [INFO] Installing project dependencies...
    "%PY%" -m pip install -r "%SCRIPT_DIR%requirements.txt"
    if errorlevel 1 (
        echo [ERROR] Failed to install dependencies.
        pause
        exit /b 1
    )
)

REM Make sure pyinstaller is installed
"%PY%" -m PyInstaller --version >nul 2>&1
if errorlevel 1 (
    echo [INFO] PyInstaller not found. Installing...
    "%PY%" -m pip install pyinstaller
    if errorlevel 1 (
        echo [ERROR] Failed to install PyInstaller.
        pause
        exit /b 1
    )
)

REM Clean previous build artifacts so the new exe is fresh
if exist "%SCRIPT_DIR%build" rmdir /S /Q "%SCRIPT_DIR%build"
if exist "%SCRIPT_DIR%dist" rmdir /S /Q "%SCRIPT_DIR%dist"
if exist "%SCRIPT_DIR%WhalesBot.spec" del /F /Q "%SCRIPT_DIR%WhalesBot.spec"

echo.
echo [INFO] Running PyInstaller...
echo.

REM --collect-all winsdk: bundle the WinRT OCR projections the freeze watchdog
REM uses (PyInstaller misses them otherwise and OCR fails at runtime).
"%PY%" -m PyInstaller --onefile --name WhalesBot ^
    --add-data "VERSION;." ^
    --add-data "updater.bat;." ^
    --collect-all winsdk ^
    run_bot.py

if errorlevel 1 (
    echo.
    echo [ERROR] Build failed.
    pause
    exit /b 1
)

echo.
echo ========================================
echo [OK] Build complete!
echo Output: %SCRIPT_DIR%dist\WhalesBot.exe
echo ========================================
echo.
pause
