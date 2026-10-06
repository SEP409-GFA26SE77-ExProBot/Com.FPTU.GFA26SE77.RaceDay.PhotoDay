# src — RaceDay OCR Service

> Hướng dẫn **đầy đủ** (mục đích, tích hợp WebAPI, thuật toán + link, thuật ngữ, troubleshooting):  
> **[`../README.md`](../README.md)**

## Máy mới — 2 lệnh

```powershell
cd src
.\setup.ps1
.\run_demo.ps1
```

Demo: http://127.0.0.1:8089/demo

## Cấu trúc ngắn

```
app/main.py          entry + warmup
app/api/jobs.py      REST
app/services/*       pipeline · YOLO · Paddle · classify · dedupe
scripts/smoke_test.py
.env.example         → copy thành .env (không commit .env)
```

## Pipeline

`dedupe → blur → YOLO multi-band ROI → PaddleOCR → classify`
