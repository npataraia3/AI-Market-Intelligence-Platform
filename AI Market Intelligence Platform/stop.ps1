# ============================================================
#  Stops the background API + dashboard servers started by
#  start.ps1. Run in PowerShell.
# ============================================================
$processes = Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object {
    $_.CommandLine -like "*dash_app*" -or $_.CommandLine -like "*flask*"
}

if ($processes) {
    $processes | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
    Write-Host "Stopped $($processes.Count) server process(es)."
} else {
    Write-Host "No running dashboard/API servers found."
}
