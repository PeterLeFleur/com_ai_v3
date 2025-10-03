Param(
    [string] $EnvName = ".venv",
    [string] $App = "api.main:app",
    [int]    $Port = 8000,
    [switch] $Dev = $true,
    [switch] $Multi,
    [switch] $NoInstall
)

$ErrorActionPreference = "Stop"

# Use the multi app if requested
if ($Multi) { $App = "api.main_multi:app" }

# Resolve important paths
$Root   = (Get-Location).Path
$Venv   = Join-Path $Root $EnvName
$PyExe  = Join-Path $Venv "Scripts\python.exe"
$ActPS1 = Join-Path $Venv "Scripts\Activate.ps1"
$Req    = Join-Path $Root "requirements.txt"
$ReqDev = Join-Path $Root "requirements-dev.txt"

Write-Host "Project root: $Root"
Write-Host "Virtual env : $Venv"
Write-Host "App target  : $App`n"

# Create venv if needed
if (!(Test-Path $PyExe)) {
    Write-Host "Creating virtual environment at $EnvName..."
    & py -3 -m venv $EnvName
}

# Activate venv
Write-Host "Activating virtual environment..."
. $ActPS1

# Make sure python is what we expect
Write-Host "Python: $(& $PyExe -c 'import sys; print(sys.executable)')"

# Optionally (re)install dependencies
if (-not $NoInstall) {
    Write-Host "Upgrading pip/setuptools/wheel..."
    & $PyExe -m pip install -U pip setuptools wheel

    if (Test-Path $Req) {
        Write-Host "Installing $($Req | Split-Path -Leaf)..."
        & $PyExe -m pip install -r $Req
    } else {
        Write-Host "No requirements.txt found, skipping..."
    }

    if (Test-Path $ReqDev) {
        Write-Host "Installing $($ReqDev | Split-Path -Leaf)..."
        & $PyExe -m pip install -r $ReqDev
    }
}

# Ensure uvicorn shim is correct for this venv
Write-Host "Ensuring uvicorn is installed..."
& $PyExe -m pip install --upgrade --force-reinstall "uvicorn[standard]"

# Ensure src is on Python path for imports
$env:PYTHONPATH = Join-Path $Root "src"
Write-Host "PYTHONPATH = $env:PYTHONPATH`n"

# Build uvicorn args
$args = @("uvicorn", $App, "--app-dir", "src", "--host", "0.0.0.0", "--port", "$Port")
if ($Dev) { $args += "--reload" }

Write-Host "Starting: python -m $($args -join ' ')"
& $PyExe -m $args
