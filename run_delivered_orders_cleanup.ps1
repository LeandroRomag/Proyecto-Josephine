param(
    [int]$Hours = 24
)

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$python = Join-Path $projectRoot '.venv\Scripts\python.exe'
$managePy = Join-Path $projectRoot 'manage.py'

if (-not (Test-Path $python)) {
    throw "No se encontró el entorno virtual en $python"
}

Push-Location $projectRoot
try {
    & $python $managePy cleanup_expired_delivered_orders --hours $Hours
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}
