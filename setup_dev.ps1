<# Setup development environment on Windows PowerShell #>
$venv = ".venv"
if (-not (Test-Path $venv)) {
    python -m venv $venv
}
Write-Host "Activating virtualenv and installing dependencies..."
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt

if (-not (Test-Path ".env")) {
    Copy-Item .env.example .env
    Write-Host "Created .env from .env.example — edit credentials as needed."
} else {
    Write-Host ".env already exists, skipping copy."
}

Write-Host "Setup complete. Activate with: .\.venv\Scripts\Activate.ps1"
