# ============================================================
#  One-click start: launches the API + dashboard and opens the
#  browser. Run in PowerShell, NOT in the Python console.
# ============================================================
$ErrorActionPreference = "Stop"

Write-Host "Starting the API server (port 8000)..."
Start-Process -FilePath "python" -ArgumentList "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000" -WindowStyle Hidden

Write-Host "Starting the dashboard (port 8501)..."
Start-Process -FilePath "python" -ArgumentList "-m", "streamlit", "run", "dashboard/streamlit_app.py", "--server.headless", "true", "--server.port", "8501" -WindowStyle Hidden

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
Write-Host "API docs   : http://127.0.0.1:8000/docs"
Write-Host ""
Write-Host "Both servers are now running in the background."
Write-Host "To stop them later, run:  .\stop.ps1"
