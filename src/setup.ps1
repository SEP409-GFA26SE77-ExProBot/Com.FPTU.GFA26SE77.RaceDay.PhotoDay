# Bootstrap OCR service (Windows PowerShell) - ASCII/English only (avoid encoding errors)
# Usage:  cd src;  .\setup.ps1
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

# Prefer UTF-8 console when available (does not require Vietnamese text in this script)
try {
    [Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()
    $OutputEncoding = [Console]::OutputEncoding
} catch {}

Write-Host "== RaceDay OCR setup ==" -ForegroundColor Cyan

$pyCmd = $null
foreach ($name in @("python", "py")) {
    $c = Get-Command $name -ErrorAction SilentlyContinue
    if ($c) { $pyCmd = $c.Source; break }
}
if (-not $pyCmd) {
    Write-Error "Python not found in PATH. Install Python 3.10-3.12 from https://www.python.org/downloads/ (check 'Add to PATH')."
}

# Resolve version (support "py -3")
$verLine = & $pyCmd -c "import sys; print('%d.%d' % (sys.version_info.major, sys.version_info.minor))"
Write-Host "Python: $verLine  ($pyCmd)"
$parts = $verLine.Trim().Split(".")
$maj = [int]$parts[0]
$min = [int]$parts[1]
if ($maj -ne 3 -or $min -lt 10 -or $min -gt 12) {
    Write-Warning "Recommended Python 3.10-3.12 for PaddleOCR. Current: $verLine"
}

$venvPython = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    Write-Host "Creating .venv ..."
    & $pyCmd -m venv .venv
    if (-not (Test-Path $venvPython)) {
        Write-Error "Failed to create .venv. Try: $pyCmd -m venv .venv"
    }
}

Write-Host "Upgrading pip ..."
& $venvPython -m pip install --upgrade pip
Write-Host "Installing requirements (first run may take 5-15 minutes)..."
& $venvPython -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) {
    Write-Error "pip install failed (exit $LASTEXITCODE). Check Python version and network."
}

if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "Created .env from .env.example"
} else {
    Write-Host ".env already exists - keeping it"
}

Write-Host ""
Write-Host "OK. Next:" -ForegroundColor Green
Write-Host "  .\run_demo.ps1"
Write-Host "Or:"
Write-Host "  .\.venv\Scripts\Activate.ps1"
Write-Host "  uvicorn app.main:app --host 127.0.0.1 --port 8089"
Write-Host ""
Write-Host "First start downloads YOLO yolov8n.pt + Paddle models (~hundreds of MB) into user cache."
