@'
@echo off
REM Quick launch wrapper for Windows double-click
REM Calls the PowerShell run.ps1 script

REM Change directory to this script’s location
cd /d "%~dp0"

REM Run run.ps1 with PowerShell, bypassing execution policy
powershell -ExecutionPolicy Bypass -NoProfile -File ".\run.ps1"
'@ | Set-Content -Encoding OEM .\run.bat
