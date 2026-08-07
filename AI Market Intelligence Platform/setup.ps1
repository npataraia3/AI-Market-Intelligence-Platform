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

$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if ($isAdmin) {
    Write-Host "Configuring Windows Firewall so other devices on the network can open the dashboard..."
    netsh advfirewall firewall add rule name="AI Market Intelligence API" dir=in action=allow protocol=TCP localport=8000
    netsh advfirewall firewall add rule name="AI Market Intelligence Dashboard" dir=in action=allow protocol=TCP localport=8501
} else {
    Write-Host ""
    Write-Host "NOTE: To let other devices on your Wi-Fi open the dashboard, run this once as"
    Write-Host "Administrator (right-click PowerShell -> Run as administrator):"
    Write-Host ""
    Write-Host '  netsh advfirewall firewall add rule name="AI API" dir=in action=allow protocol=TCP localport=8000'
    Write-Host '  netsh advfirewall firewall add rule name="AI Dashboard" dir=in action=allow protocol=TCP localport=8501'
}

Write-Host ""
Write-Host "Setup complete. Next run:  .\start.ps1"
