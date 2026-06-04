param(
    [int]$Minutes = 60
)

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$python = Join-Path $projectRoot '.venv\Scripts\python.exe'
$managePy = Join-Path $projectRoot 'manage.py'

if (-not (Test-Path $python)) {
    throw "No se encontró el entorno virtual en $python"
}

Push-Location $projectRoot
try {
    & $python $managePy cleanup_expired_pending_orders --minutes $Minutes
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}