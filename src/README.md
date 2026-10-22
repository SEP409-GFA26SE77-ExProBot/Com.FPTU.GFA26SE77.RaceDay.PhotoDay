# src - RaceDay OCR Service

Full guide (VN): [`../README.md`](../README.md)

## Fresh machine (Windows)

```powershell
cd src
# if script is blocked:
#   Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
.\setup.ps1
.\run_demo.ps1
```

Demo: http://127.0.0.1:8089/demo

## Fresh machine (Linux/macOS)

```bash
cd src
chmod +x setup.sh
./setup.sh
source .venv/bin/activate
uvicorn app.main:app --host 127.0.0.1 --port 8089
```

## Notes for teammates

- Script messages are **English/ASCII** (avoids PowerShell encoding errors with Vietnamese).
- Need **Python 3.10-3.12** and network on first run (downloads YOLO + Paddle models).
- Copy `.env` from `.env.example` is done by `setup.ps1` / `setup.sh`.
- Do not commit `.env` or `.venv`.
- **GPU is optional.** `OCR_DEVICE=auto` falls back to CPU if no CUDA — service does not crash.
- Torch CUDA (YOLO) ≠ Paddle CUDA. CPU wheel (`paddle_cpu_wheel` in `/healthz`) → Paddle stays on CPU; YOLO may still use CUDA.
- Keep `MAX_INFLIGHT` aligned with WebAPI `Photo:Ocr:WorkerMaxParallel` (default `2`).
- Full device guide: [`../README.md` §3.1](../README.md#31-device-gpucpu--không-sập-khi-thiếu-cuda).

## Layout

```
app/main.py           entry + warmup + /healthz device
app/api/jobs.py       REST (+ POST /v1/ocr/dedupe/clear)
app/core/device.py    OCR_DEVICE / YOLO_DEVICE + CPU fallback
app/services/*        pipeline, YOLO, Paddle, classify, dedupe
scripts/smoke_test.py
.env.example          -> becomes .env locally
```

## Pipeline

`dedupe -> blur -> YOLO multi-band ROI -> PaddleOCR -> classify`

Check devices after start:

```powershell
(Invoke-RestMethod http://127.0.0.1:8089/healthz).device
```
