# Hướng dẫn setup

> **Đầy đủ & cập nhật:** xem [`../README.md`](../README.md) mục **§2 Cài & chạy** và **§3 Cấu hình `.env`**.

## Tóm tắt Windows

```powershell
cd SEP_Service_Photo\src
.\setup.ps1
.\run_demo.ps1
```

- Python **3.10–3.12**
- Copy `.env.example` → `.env` (script làm sẵn)
- Lần đầu cần mạng để tải YOLO + Paddle models

## Không commit

`.env`, `.venv/`, `*.pt` — đã có root [`.gitignore`](../.gitignore).
