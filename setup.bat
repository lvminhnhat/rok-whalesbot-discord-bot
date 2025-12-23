@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

echo ============================================
echo    ROK WhalesBot Discord Bot - Setup
echo ============================================
echo.

:: Check Python installation
echo [1/5] Kiem tra Python...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [LOI] Python chua duoc cai dat!
    echo Vui long tai Python tu: https://www.python.org/downloads/
    echo Nho chon "Add Python to PATH" khi cai dat.
    pause
    exit /b 1
)

for /f "tokens=2" %%i in ('python --version 2^>^&1') do set PYTHON_VERSION=%%i
echo [OK] Python %PYTHON_VERSION% da duoc cai dat

:: Check pip
echo.
echo [2/5] Kiem tra pip...
python -m pip --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [LOI] pip chua duoc cai dat!
    pause
    exit /b 1
)
echo [OK] pip da san sang

:: Create virtual environment
echo.
echo [3/5] Tao moi truong ao (.venv)...
if exist .venv (
    echo [INFO] Moi truong ao da ton tai. Ban co muon tao lai khong?
    set /p RECREATE="Nhap Y de tao lai, N de bo qua (Y/N): "
    if /i "!RECREATE!"=="Y" (
        echo Dang xoa moi truong ao cu...
        rmdir /s /q .venv
        python -m venv .venv
        echo [OK] Da tao lai moi truong ao
    ) else (
        echo [SKIP] Giu nguyen moi truong ao hien tai
    )
) else (
    python -m venv .venv
    echo [OK] Da tao moi truong ao tai .venv
)

:: Activate virtual environment and install dependencies
echo.
echo [4/5] Cai dat cac thu vien can thiet...
call .venv\Scripts\activate.bat

:: Upgrade pip first
python -m pip install --upgrade pip >nul 2>&1

:: Install requirements
echo Dang cai dat dependencies tu requirements.txt...
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo [LOI] Khong the cai dat dependencies!
    pause
    exit /b 1
)
echo [OK] Da cai dat tat ca dependencies

:: Setup configuration files
echo.
echo [5/5] Thiet lap cac file cau hinh...

:: Create .env if not exists
if not exist .env (
    if exist .env.example (
        copy .env.example .env >nul
        echo [OK] Da tao file .env tu .env.example
        echo [QUAN TRONG] Vui long chinh sua file .env voi thong tin cua ban!
    ) else if exist env_example.txt (
        copy env_example.txt .env >nul
        echo [OK] Da tao file .env tu env_example.txt
        echo [QUAN TRONG] Vui long chinh sua file .env voi thong tin cua ban!
    ) else (
        echo [CANH BAO] Khong tim thay file .env.example hoac env_example.txt
    )
) else (
    echo [SKIP] File .env da ton tai
)

:: Create data directory and files
if not exist data mkdir data

if not exist data\users.json (
    echo {} > data\users.json
    echo [OK] Da tao data\users.json
)

if not exist data\config.json (
    echo {"admin_users": [], "allowed_guilds": [], "allowed_channels": []} > data\config.json
    echo [OK] Da tao data\config.json
    echo [QUAN TRONG] Them Discord User ID cua ban vao admin_users trong data\config.json
)

if not exist data\audit_logs.json (
    echo [] > data\audit_logs.json
    echo [OK] Da tao data\audit_logs.json
)

:: Summary
echo.
echo ============================================
echo           SETUP HOAN TAT!
echo ============================================
echo.
echo Cac buoc tiep theo:
echo   1. Chinh sua file .env:
echo      - DISCORD_BOT_TOKEN=your_bot_token_here
echo      - WHALEBOTS_PATH=path\to\WhaleBots
echo.
echo   2. Chinh sua file data\config.json:
echo      - Them Discord User ID vao "admin_users"
echo.
echo   3. Chay bot:
echo      - Dung lenh: run.bat
echo      - Hoac kich hoat venv va chay thu cong:
echo        .venv\Scripts\activate
echo        python run_bot.py
echo.
echo ============================================
pause
