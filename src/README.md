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

## Layout

```
app/main.py           entry + warmup
app/api/jobs.py       REST
app/services/*        pipeline, YOLO, Paddle, classify, dedupe
scripts/smoke_test.py
.env.example          -> becomes .env locally
```

## Pipeline

`dedupe -> blur -> YOLO multi-band ROI -> PaddleOCR -> classify`
