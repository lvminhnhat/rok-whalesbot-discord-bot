@echo off
title WhaleBots System
echo ========================================
echo    WhaleBots Discord Bot + Dashboard
echo ========================================
echo.

echo [INFO] Starting WhaleBots system...
echo.

REM Get the directory where this batch file is located
set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%"

REM Prefer the project virtual environment if it exists
set "VENV_PY=%SCRIPT_DIR%.venv\Scripts\python.exe"
if exist "%VENV_PY%" (
    set "PYTHON_CMD=%VENV_PY%"
) else (
    set "PYTHON_CMD=python"
)

REM Start Discord Bot in a new window
echo [1/2] Starting Discord Bot...
start "WhaleBots Discord Bot" cmd /k "cd /d ""%SCRIPT_DIR%"" && ""%PYTHON_CMD%"" run_bot.py"
timeout /t 2 /nobreak >nul

REM Start Web Dashboard in a new window
echo [2/2] Starting Web Dashboard...
start "WhaleBots Web Dashboard" cmd /k "cd /d ""%SCRIPT_DIR%"" && ""%PYTHON_CMD%"" run_dashboard.py"
timeout /t 2 /nobreak >nul

echo.
echo ========================================
echo [OK] System started successfully!
echo ========================================
echo.
echo Discord Bot: Check the "WhaleBots Discord Bot" window
echo Web Dashboard: http://127.0.0.1:5000
echo.
echo Press Ctrl+C in each window to stop
echo Or run stop.bat to stop all
echo ========================================
pause

