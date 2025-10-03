@'
@echo off
cd /d "%~dp0"
if not exist "logs" mkdir "logs"

echo [%date% %time%] Starting dev server... >> "logs\dev.log"
powershell -ExecutionPolicy Bypass -NoProfile -File ".\run.ps1" -NoInstall *>> "logs\dev.log"

echo.
echo -------- OUTPUT COPIED TO logs\dev.log --------
echo Press any key to close...
pause >nul
'@ | Set-Content -Encoding OEM .\run_log.bat
