@echo off
title Check WhaleBots System
echo ========================================
echo    WhaleBots System Check
echo ========================================
echo.

REM Check Python
echo [1/6] Checking Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found! Please install Python 3.11+
) else (
    python --version
)
echo.

REM Check .env file
echo [2/6] Checking .env file...
if exist .env (
    echo [OK] .env file exists
) else (
    echo [ERROR] .env file not found!
    echo Please create .env file from .env.example
)
echo.

REM Check data directory
echo [3/6] Checking data directory...
if exist data (
    echo [OK] data/ directory exists
    if exist data\config.json (
        echo [OK] data\config.json exists
    ) else (
        echo [ERROR] data\config.json not found!
    )
    if exist data\users.json (
        echo [OK] data\users.json exists
    ) else (
        echo [ERROR] data\users.json not found!
    )
    if exist data\audit_logs.json (
        echo [OK] data\audit_logs.json exists
    ) else (
        echo [ERROR] data\audit_logs.json not found!
    )
) else (
    echo [ERROR] data/ directory not found!
)
echo.

REM Check modules
echo [4/6] Checking modules...
if exist discord_bot (
    echo [OK] discord_bot/ exists
) else (
    echo [ERROR] discord_bot/ not found!
)
if exist web_dashboard (
    echo [OK] web_dashboard/ exists
) else (
    echo [ERROR] web_dashboard/ not found!
)
if exist shared (
    echo [OK] shared/ exists
) else (
    echo [ERROR] shared/ not found!
)
if exist whalebots_automation (
    echo [OK] whalebots_automation/ exists
) else (
    echo [ERROR] whalebots_automation/ not found!
)
echo.

REM Check dependencies
echo [5/6] Checking Python packages...
python -c "import discord" >nul 2>&1
if errorlevel 1 (
    echo [ERROR] py-cord not installed
) else (
    echo [OK] py-cord installed
)
python -c "import flask" >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Flask not installed
) else (
    echo [OK] Flask installed
)
python -c "import dotenv" >nul 2>&1
if errorlevel 1 (
    echo [ERROR] python-dotenv not installed
) else (
    echo [OK] python-dotenv installed
)
echo.

REM Summary
echo [6/6] System Status
echo ========================================
echo If all checks passed, run: run.bat
echo If errors exist, fix them first
echo ========================================
echo.
pause

