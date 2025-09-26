@echo off
setlocal enabledelayedexpansion

echo.
echo ========================================
echo  Starting COM-AI v3 - George's Brain
echo ========================================
echo.

rem Get the directory where this script is located
set "REPO=%~dp0"
cd /d "%REPO%" || (
    echo [ERROR] Could not change to repository directory: %REPO%
    pause
    exit /b 1
)

rem Check if virtual environment exists
if not exist ".venv\Scripts\activate.bat" (
    echo [INFO] Creating virtual environment...
    python -m venv .venv
    if errorlevel 1 (
        echo [ERROR] Failed to create virtual environment
        pause
        exit /b 1
    )
)

rem Activate virtual environment
echo [INFO] Activating virtual environment...
call ".venv\Scripts\activate.bat" || (
    echo [ERROR] Failed to activate virtual environment
    pause
    exit /b 1
)

rem Install/update dependencies
echo [INFO] Installing dependencies...
pip install -r requirements.txt
if errorlevel 1 (
    echo [WARNING] Some dependencies may have failed to install
)

rem Set Python path for clean imports
set "PYTHONPATH=%REPO%;%REPO%\src;%PYTHONPATH%"

rem Check if .env exists
if not exist ".env" (
    echo [WARNING] .env file not found. Copy .env.example to .env and configure your API keys.
    echo [INFO] Continuing with example configuration...
)

rem Validate registry before starting
echo [INFO] Validating project registry...
python tools\registry_validate.py
if errorlevel 1 (
    echo [WARNING] Registry validation failed, but continuing...
)

rem Start the server
echo [INFO] Starting George's Brain...
echo [INFO] Server will be available at: http://localhost:8000
echo [INFO] API Documentation: http://localhost:8000/docs
echo [INFO] Press Ctrl+C to stop the server
echo.

uvicorn src.api.main_multi:app --env-file .env --reload --reload-exclude ".venv/*" --host 0.0.0.0 --port 8000

echo.
echo [INFO] George's Brain has stopped.
pause