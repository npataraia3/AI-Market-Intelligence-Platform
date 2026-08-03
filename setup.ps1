# ============================================================
#  Setup script - run this ONCE to prepare the project.
#  Run it in PowerShell, NOT in the Python interactive console
#  (the ">>>" prompt). See README.md -> Quick start.
# ============================================================
$ErrorActionPreference = "Stop"

Write-Host "Installing dependencies..."
python -m pip install -r requirements.txt

if (-not (Test-Path .env)) {
    Write-Host "Creating .env from .env.example..."
    Copy-Item .env.example .env
} else {
    Write-Host ".env already exists, leaving it unchanged."
}

Write-Host ""
Write-Host "Setup complete. Next run:  .\start.ps1"
