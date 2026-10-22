$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root
$python = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    throw "Run start.ps1 once to create .venv, or: python -m venv .venv"
}
Write-Host "== Unit and integration tests =="
& $python -m pytest
Write-Host ""
Write-Host "== A/B/C replay evaluation =="
& $python -m evaluation.run_replay
