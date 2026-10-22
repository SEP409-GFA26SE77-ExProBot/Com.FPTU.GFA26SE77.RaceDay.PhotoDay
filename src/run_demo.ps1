# Start OCR service + open demo UI - ASCII/English only
# Usage:  .\run_demo.ps1
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

try {
    [Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()
    $OutputEncoding = [Console]::OutputEncoding
} catch {}

$port = 8089
$url = "http://127.0.0.1:$port/demo"
$python = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $python)) {
    Write-Host "No .venv found. Run setup first:" -ForegroundColor Yellow
    Write-Host "  .\setup.ps1"
    exit 1
}

if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "Copied .env.example -> .env"
}

$already = $false
try {
    $hz = Invoke-WebRequest -Uri "http://127.0.0.1:$port/healthz" -UseBasicParsing -TimeoutSec 2
    if ($hz.StatusCode -eq 200) { $already = $true }
} catch { $already = $false }

if (-not $already) {
    Write-Host "Starting OCR on :$port (first warmup may take 20-60s)..."
    Start-Process -FilePath $python -ArgumentList @(
        "-m", "uvicorn", "app.main:app",
        "--host", "0.0.0.0",
        "--port", "$port"
    ) -WorkingDirectory $PSScriptRoot -WindowStyle Normal

    $deadline = (Get-Date).AddSeconds(180)
    $ok = $false
    do {
        Start-Sleep -Seconds 2
        try {
            $hz = Invoke-WebRequest -Uri "http://127.0.0.1:$port/healthz" -UseBasicParsing -TimeoutSec 2
            if ($hz.StatusCode -eq 200) { $ok = $true; break }
        } catch {}
    } while ((Get-Date) -lt $deadline)

    if (-not $ok) {
        Write-Warning "Server did not become healthy within timeout. Check the uvicorn window for errors."
        Write-Host "Manual: .\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port $port"
        exit 1
    }
}

Write-Host "Demo: $url"
Start-Process $url
