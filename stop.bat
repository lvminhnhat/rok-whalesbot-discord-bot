@echo off
title Stop WhaleBots
echo ========================================
echo    Stopping WhaleBots System
echo ========================================
echo.

REM Kill Python processes for bot and dashboard
echo [INFO] Stopping Discord Bot and Web Dashboard...

REM Kill by window title
taskkill /FI "WINDOWTITLE eq WhaleBots Discord Bot*" /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq WhaleBots Web Dashboard*" /F >nul 2>&1

REM Also kill Python processes on ports 5000
for /f "tokens=5" %%a in ('netstat -aon ^| find ":5000" ^| find "LISTENING"') do (
    taskkill /F /PID %%a >nul 2>&1
)

echo.
echo ========================================
echo [OK] System stopped
echo ========================================
pause

