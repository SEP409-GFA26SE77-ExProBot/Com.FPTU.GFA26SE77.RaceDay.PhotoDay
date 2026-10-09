# Bootstrap OCR service on a fresh machine (Windows PowerShell)
# Usage:  cd src;  .\setup.ps1
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

Write-Host "== RaceDay OCR setup ==" -ForegroundColor Cyan

$py = Get-Command python -ErrorAction SilentlyContinue
if (-not $py) {
    Write-Error "Missing Python in PATH. Install Python 3.10–3.12 from https://www.python.org/downloads/ (tick Add to PATH)."
}

$ver = & python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
Write-Host "Python: $ver"
$maj, $min = $ver.Split(".") | ForEach-Object { [int]$_ }
if ($maj -ne 3 -or $min -lt 10 -or $min -gt 12) {
    Write-Warning "Recommended Python 3.10–3.12 (PaddleOCR is most stable). Currently using $ver."
}

if (-not (Test-Path ".venv")) {
    Write-Host "Creating .venv ..."
    python -m venv .venv
}

$pip = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
& $pip -m pip install --upgrade pip
Write-Host "Installing requirements (this may take 5-15 minutes the first time)..."
& $pip -m pip install -r requirements.txt

if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "Created .env from .env.example"
} else {
    Write-Host ".env already exists - keep"
}

Write-Host ""
Write-Host "OK. Run demo:" -ForegroundColor Green
Write-Host "  .\run_demo.ps1"
Write-Host "Or:"
Write-Host "  .\.venv\Scripts\Activate.ps1"
Write-Host "  uvicorn app.main:app --host 127.0.0.1 --port 8089"
Write-Host ""
Write-Host "First time start: download YOLO yolov8n.pt + Paddle models (~a few hundred MB) to user cache."
