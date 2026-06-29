@echo off
REM updater.bat - swap staged release files into the install dir, then relaunch.
REM
REM Args:
REM   %1 = staging directory (already-extracted release files)
REM   %2 = install directory (where the .exe lives)
REM   %3 = exe name to relaunch (e.g. WhalesBot.exe)
REM
REM Spawned by shared/updater.py after the user confirms an update.
REM The main exe exits immediately after spawn so this script can replace it.

setlocal
set "STAGING=%~1"
set "INSTALL_DIR=%~2"
set "EXE_NAME=%~3"

if "%STAGING%"=="" goto :missing_args
if "%INSTALL_DIR%"=="" goto :missing_args
if "%EXE_NAME%"=="" goto :missing_args

echo [updater] Waiting for %EXE_NAME% to exit...

REM Wait for the running exe to release its files. Cap at ~30s as a safety net.
set /a TRIES=0
:wait_loop
tasklist /FI "IMAGENAME eq %EXE_NAME%" 2>NUL | find /I "%EXE_NAME%" >NUL
if errorlevel 1 goto :exited
set /a TRIES+=1
if %TRIES% GEQ 30 (
    echo [updater] %EXE_NAME% did not exit in time. Aborting update.
    goto :cleanup
)
timeout /t 1 /nobreak >nul
goto :wait_loop

:exited
REM Brief extra delay so Windows fully releases file handles.
timeout /t 2 /nobreak >nul

echo [updater] Copying new files into %INSTALL_DIR%...
robocopy "%STAGING%" "%INSTALL_DIR%" /E /NFL /NDL /NJH /NJS /NP /R:2 /W:1 >nul
set RC=%ERRORLEVEL%
REM robocopy exit codes < 8 are success/info; >= 8 means real failure.
if %RC% GEQ 8 (
    echo [updater] robocopy failed with code %RC%. Files may be partially updated.
    goto :cleanup
)

echo [updater] Update applied. Relaunching %EXE_NAME%...
cd /d "%INSTALL_DIR%"
REM Use PowerShell Start-Process, not cmd's `start`: when updater.bat runs
REM detached (no console), `start` fails with "Not enough memory resources".
REM Start-Process launches reliably from any context.
powershell -NoProfile -Command "Start-Process -FilePath '%INSTALL_DIR%\%EXE_NAME%' -WorkingDirectory '%INSTALL_DIR%'"
if errorlevel 1 echo [updater] Auto-relaunch failed - please start %EXE_NAME% manually.

:cleanup
rmdir /S /Q "%STAGING%" >nul 2>&1
endlocal
exit /b 0

:missing_args
echo [updater] Missing arguments. Usage: updater.bat ^<staging^> ^<install_dir^> ^<exe_name^>
endlocal
exit /b 1
