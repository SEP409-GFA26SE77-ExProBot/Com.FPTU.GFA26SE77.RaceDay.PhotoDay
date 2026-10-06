# One-shot: start OCR service + open demo UI
# Usage:  .\run_demo.ps1
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$port = 8089
$url = "http://127.0.0.1:$port/demo"
$python = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $python)) {
    Write-Host "Chưa có .venv. Chạy setup trước:" -ForegroundColor Yellow
    Write-Host "  .\setup.ps1"
    exit 1
}

if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "Đã copy .env.example -> .env"
}

$already = $false
try {
    $hz = Invoke-WebRequest -Uri "http://127.0.0.1:$port/healthz" -UseBasicParsing -TimeoutSec 2
    if ($hz.StatusCode -eq 200) { $already = $true }
} catch { $already = $false }

if (-not $already) {
    Write-Host "Starting OCR on :$port (warmup YOLO+OCR lần đầu có thể 20-60s)..."
    Start-Process -FilePath $python -ArgumentList @(
        "-m", "uvicorn", "app.main:app",
        "--host", "127.0.0.1",
        "--port", "$port"
    ) -WorkingDirectory $PSScriptRoot -WindowStyle Normal

    $deadline = (Get-Date).AddSeconds(120)
    do {
        Start-Sleep -Seconds 2
        try {
            $hz = Invoke-WebRequest -Uri "http://127.0.0.1:$port/healthz" -UseBasicParsing -TimeoutSec 2
            if ($hz.StatusCode -eq 200) { break }
        } catch {}
    } while ((Get-Date) -lt $deadline)
}

Write-Host "Demo: $url"
Start-Process $url
