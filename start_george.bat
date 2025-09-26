@echo off
setlocal enabledelayedexpansion

echo.
echo ========================================
echo  Starting COM-AI v3 - George's Brain
echo ========================================
echo.

REM Go to repo root (where this .bat lives)
set "REPO=%~dp0"
cd /d "%REPO%" || (
    echo [ERROR] Could not change to repository directory: %REPO%
    pause
    exit /b 1
)

REM Ensure virtual environment exists
if not exist ".venv\Scripts\activate.bat" (
    echo [INFO] Creating virtual environment...
    python -m venv .venv
    if errorlevel 1 (
        echo [ERROR] Failed to create virtual environment
        pause
        exit /b 1
    )
)

REM Activate virtual environment
echo [INFO] Activating virtual environment...
call ".venv\Scripts\activate.bat" || (
    echo [ERROR] Failed to activate virtual environment
    pause
    exit /b 1
)

REM Install/update dependencies
echo [INFO] Installing dependencies...
pip install -r requirements.txt
if errorlevel 1 (
    echo [WARNING] Some dependencies may have failed to install
)

REM Make imports stable
set "PYTHONPATH=%REPO%;%REPO%\src;%PYTHONPATH%"

REM Warn if .env missing
if not exist ".env" (
    echo [WARNING] .env file not found. Copy .env.example to .env and configure your API keys.
)

REM Validate registry before starting
echo [INFO] Validating project registry...
python tools\registry_validate.py
if errorlevel 1 (
    echo [WARNING] Registry validation failed, but continuing...
)

REM Windows console + Python in UTF-8 to avoid emoji/codec issues
chcp 65001 >nul
set "PYTHONIOENCODING=utf-8"
set "PYTHONUTF8=1"

echo [INFO] Starting George's Brain...
echo [INFO] Server: http://127.0.0.1:8000
echo [INFO] Docs:   http://127.0.0.1:8000/docs
echo [INFO] Press Ctrl+C to stop the server
echo.

REM Launch inside venv, NO reload-exclude to avoid Windows glob expansion
python -m uvicorn "src.api.main_multi:app" ^
  --env-file ".env" ^
  --host 127.0.0.1 ^
  --port 8000 ^
  --reload ^
  --reload-dir "src" ^
  --reload-dir "tools"

echo.
echo [INFO] George's Brain has stopped.
pause
