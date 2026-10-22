# 06 — Perf / Memory / Stability (trong phạm vi OCR service)

> **Phase hiện tại:** chỉ áp dụng trong `SEP_Service_Photo`. Không phụ thuộc WebAPI.

## Mục tiêu

- Tối đa throughput khi data lớn
- Tiết kiệm RAM/VRAM
- Tránh sập khi trùng kép / ảnh mờ / burst upload
- Giữ Precision auto-tag cao (accuracy theo band confidence)

## Cascade early-exit (bắt buộc)

```
Ingest
  → SHA-256 exact dup?     STOP → duplicate
  → dHash near-dup?        STOP → duplicate
  → Blur quá thấp?         STOP → no_bib / needs_review (không OCR)
  → Downscale
  → OCR (mock hoặc PaddleOCR)
  → Confidence + roster
```

| ID | Rule |
|---|---|
| BR-PERF-01 | Exact/near dup trước mọi inference nặng |
| BR-PERF-02 | Blur gate: Laplacian variance &lt; `blur_min_variance` → bỏ OCR |
| BR-PERF-03 | Max cạnh ảnh ≤ `max_image_side` trước OCR |
| BR-PERF-04 | `max_inflight` semaphore — không chạy song song vượt RAM |
| BR-PERF-05 | Model load 1 lần / process |
| BR-PERF-06 | Kết quả job lưu local (memory/dev); callback WebAPI = phase sau |

## Accuracy (trong service)

Giữ `02_ocr_confidence_pipeline.md`:

- ≥ `threshold_auto` → `auto_tagged`
- [`threshold_review_min`, `threshold_auto`) → `needs_review`
- &lt; `threshold_review_min` hoặc blur reject → `no_bib` / review, **không đoán**

## Config mặc định

| Key | Default (khớp `.env.example` / `config.py`) |
|---|---|
| `MAX_INFLIGHT` | 2 (khớp WebAPI `Photo:Ocr:WorkerMaxParallel`) |
| `MAX_IMAGE_SIDE` | 1600 |
| `BLUR_MIN_VARIANCE` | 40 |
| `NEAR_DUP_HAMMING_MAX` | 5 |
| `THRESHOLD_AUTO` | 0.85 |
| `THRESHOLD_REVIEW_MIN` | 0.50 |
| `OCR_DEVICE` | `auto` (không GPU → CPU, không crash) |

Device GPU/CUDA cấu hình trên **OCR service**, không trên Host WebAPI. Chi tiết: `README.md` §3.1.

Calibrate blur threshold trên sample thật trước khi demo.
