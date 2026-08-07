# ============================================================
#  One-click start: launches the API + dashboard and opens the
#  browser. Run in PowerShell, NOT in the Python console.
# ============================================================
$ErrorActionPreference = "Stop"

if (-not (Test-Path "$PSScriptRoot\logs")) { New-Item -ItemType Directory -Path "$PSScriptRoot\logs" | Out-Null }

# Detect the primary LAN IPv4 so family members on other devices can
# reach the API. Falls back to loopback if no LAN address is found.
$lanIp = Get-NetIPConfiguration -ErrorAction SilentlyContinue |
    Where-Object { $_.IPv4DefaultGateway -and $_.IPv4Address.IPAddress -notlike "169.254.*" } |
    Select-Object -First 1 |
    ForEach-Object { $_.IPv4Address.IPAddress }
if (-not $lanIp) { $lanIp = "127.0.0.1" }

Write-Host "Starting the API server (port 8000)..."
$apiLog = "$PSScriptRoot\logs\api"
Start-Process -FilePath "python" -ArgumentList "-m", "flask", "--app", "app.main", "run", "--host", "0.0.0.0", "--port", "8000", "--no-reload" -WindowStyle Hidden -WorkingDirectory $PSScriptRoot -RedirectStandardOutput "$apiLog.out.log" -RedirectStandardError "$apiLog.err.log"

Write-Host "Starting the dashboard (port 8501)..."
$dashLog = "$PSScriptRoot\logs\dashboard"
Start-Process -FilePath "python" -ArgumentList "dashboard/dash_app.py" -WindowStyle Hidden -WorkingDirectory $PSScriptRoot -RedirectStandardOutput "$dashLog.out.log" -RedirectStandardError "$dashLog.err.log"

Write-Host "Waiting for the API to become ready..."
$ready = $false
for ($i = 0; $i -lt 30; $i++) {
    Start-Sleep -Seconds 1
    try {
        $response = Invoke-WebRequest -Uri "http://127.0.0.1:8000/api/health" -UseBasicParsing -TimeoutSec 2
        if ($response.StatusCode -eq 200) { $ready = $true; break }
    } catch { }
}

if (-not $ready) {
    Write-Warning "The API did not respond within 30 seconds. It may still be starting - retry with:  .\start.ps1"
} else {
    Start-Process "http://127.0.0.1:8501"
}

Write-Host ""
Write-Host "Dashboard  : http://127.0.0.1:8501"
Write-Host "Other devices on this Wi-Fi: http://${lanIp}:8501"
Write-Host "API health : http://127.0.0.1:8000/api/health"
Write-Host ""
Write-Host "Both servers are now running in the background."
Write-Host "To stop them later, run:  .\stop.ps1"
