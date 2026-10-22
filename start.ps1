# Convenience launcher for local Windows use.
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    Write-Host "Creating virtual environment..."
    python -m venv .venv
}
$python = Join-Path $root ".venv\Scripts\python.exe"

Write-Host "Installing/updating dependencies..."
& $python -m pip install --quiet --upgrade pip
& $python -m pip install --quiet -r requirements.txt

if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "Created .env from .env.example (demo mode works without keys)."
}

$port = if ($env:SIGNALFIELD_PORT) { $env:SIGNALFIELD_PORT } else { "8790" }
Write-Host ""
Write-Host "SignalField: http://127.0.0.1:$port"
Write-Host "Press Ctrl+C to stop. No public deployment is performed."
Write-Host ""
& $python -m app
