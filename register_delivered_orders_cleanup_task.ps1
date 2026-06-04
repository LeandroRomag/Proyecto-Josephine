param(
    [string]$TaskName = 'Josephine - Cleanup Expired Delivered Orders',
    [int]$Hours = 24
)

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$runnerScript = Join-Path $projectRoot 'run_delivered_orders_cleanup.ps1'

if (-not (Test-Path $runnerScript)) {
    throw "No se encontró el script ejecutable en $runnerScript"
}

schtasks.exe /Create /TN $TaskName /SC HOURLY /MO 1 /TR "powershell.exe -NoProfile -ExecutionPolicy Bypass -File `"$runnerScript`" -Hours $Hours" /F

Write-Host "Tarea programada creada: $TaskName"
