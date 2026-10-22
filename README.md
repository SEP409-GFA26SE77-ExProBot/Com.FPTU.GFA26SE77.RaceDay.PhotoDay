# SEP_Service_Photo — RaceDay OCR / BIB Photo Service

Service **độc lập** (FastAPI) nhận ảnh giải chạy → phát hiện số **BIB** → trả tag + độ tin cậy, phục vụ **BIB Photo Finder** của RaceDay.

| | |
|---|---|
| Phase hiện tại | Standalone OCR worker (chạy được không cần WebAPI) |
| Stack | FastAPI · **YOLOv8n weights** (`yolov8n.pt`) qua package Ultralytics · PaddleOCR 3.x (PP-OCRv5 mobile) |
| Demo UI | `http://127.0.0.1:8089/demo` |
| Port mặc định | `8089` |
| Phiên bản app | `0.3.0` (`src/app/__init__.py`) |

### Pin phiên bản (đọc trước khi click docs ngoài)

Site Ultralytics / Paddle thường **quảng cáo bản mới nhất** (vd YOLO26, PaddleOCR mới). Repo này **cố định** theo bảng dưới — đừng đổi model chỉ vì trang chủ docs hiện số khác.

| Thành phần | Giá trị đang dùng trong code / `.env` | Ghi chú tránh nhầm |
|---|---|---|
| **Weights detect người** | `YOLO_MODEL=yolov8n.pt` | Đây là **kiến trúc YOLOv8 nano**, không phải “YOLO version = số package” |
| **Package Python** | `ultralytics>=8.3` (máy dev từng chạy ~8.4.x) | Package 8.x vẫn load được `yolov8n.pt`. Docs trang chủ có thể nói YOLO11/YOLO26 — **bỏ qua** trừ khi đổi `YOLO_MODEL` có chủ đích |
| **OCR engine** | `paddleocr>=3.0` + `paddlepaddle>=3.0` | Dùng API / docs **version3.x**, không dùng guide v2.9 làm chuẩn cấu hình |
| **OCR models** | `PP-OCRv5_mobile_det` + `en_PP-OCRv5_mobile_rec` | Mobile (nhanh CPU), không phải server/heavy |
| **Nguồn sự thật cấu hình** | `src/.env.example` + `src/app/core/config.py` | Luôn đối chiếu file này trước link ngoài |

---

## Mục lục

1. [Mục đích & phạm vi](#1-mục-đích--phạm-vi)
2. [Máy khác pull về — cài & chạy (checklist)](#2-máy-khác-pull-về--cài--chạy-checklist)
3. [Cấu hình môi trường (`.env`)](#3-cấu-hình-môi-trường-env) · [§3.1 Device GPU/CPU](#31-device-gpucpu--không-sập-khi-thiếu-cuda)
4. [Cấu trúc thư mục & file](#4-cấu-trúc-thư-mục--file)
5. [API nhanh](#5-api-nhanh)
6. [Tích hợp vào RaceDay WebAPI](#6-tích-hợp-vào-raceday-webapi)
7. [Pipeline & thuật toán (chi tiết + nguồn + link cấu hình)](#7-pipeline--thuật-toán-chi tiết--nguồn--link-cấu-hình)
8. [Thuật ngữ / viết tắt trong code](#8-thuật-ngữ--viết-tắt-trong-code)
9. [Kết quả đạt được](#9-kết-quả-đạt-được)
10. [Lưu ý & sự cố thường gặp](#10-lưu-ý--sự-cố-thường-gặp)
11. [Tài liệu liên quan](#11-tài-liệu-liên-quan)

---

## 1. Mục đích & phạm vi

### Việc service này làm

- Nhận ảnh (upload multipart hoặc `image_url`).
- Loại ảnh trùng (exact / near-duplicate).
- Bỏ ảnh quá mờ (blur gate).
- Tìm người (YOLO) → cắt ROI ngực/bụng/đùi → OCR số BIB (Paddle).
- Lọc watermark/signage → band confidence → status (`auto_tagged` / `needs_review` / `no_bib` / …).

### Việc service này **không** làm (thuộc WebAPI / FE)

- Auth photographer/runner (JWT/RBAC).
- Lưu trữ ảnh production (Cloudflare/R2) & ownership photo.
- Photo Finder search production (query DB đã index).
- **Photographer Corrections** UI (bắt buộc theo doc nghiệp vụ — OCR chỉ assistive).
- RFID / timing.

### Quyết định nghiệp vụ

**Photographer bulk-upload → OCR nền**, không cam check-in realtime.  
Chi tiết: [`doc/04_quyet_dinh_batch_vs_cam.md`](doc/04_quyet_dinh_batch_vs_cam.md).

---

## 2. Máy khác pull về — cài & chạy (checklist)

> Mục tiêu: clone repo → vài lệnh → mở `/demo` không lỗi.

### Yêu cầu máy

| Thành phần | Khuyến nghị |
|---|---|
| OS | Windows 10/11 (đã test), Linux/macOS (script `setup.sh`) |
| Python | **3.10 – 3.12** (3.11 ideal). Tránh 3.13 nếu Paddle chưa hỗ trợ |
| RAM | ≥ 8 GB (khuyến nghị 16 GB khi bật YOLO+OCR thật) |
| Disk | ≥ 3 GB trống (venv + model cache) |
| Mạng lần đầu | Cần tải `yolov8n.pt` + PaddleOCR models (sau đó offline được) |
| **GPU** | **Không bắt buộc.** Không CUDA / VPS CPU-only → vẫn chạy (`OCR_DEVICE=auto` fallback CPU). Có NVIDIA + torch CUDA → YOLO nhanh hơn; Paddle thường vẫn CPU nếu cài `paddlepaddle` (CPU wheel) — xem [§3 Device](#31-device-gpucpu--không-sập-khi-thiếu-cuda) |

### Windows (khuyến nghị)

> Script `setup.ps1` / `run_demo.ps1` dùng **tiếng Anh (ASCII)** để tránh lỗi encoding PowerShell khi teammate pull.

```powershell
git clone <URL_REPO> SEP_Service_Photo
cd SEP_Service_Photo\src

# If blocked: Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
.\setup.ps1
.\run_demo.ps1
```

Thủ công tương đương:

```powershell
cd SEP_Service_Photo\src
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
copy .env.example .env
# Kiểm tra .env: OCR_MOCK=0, YOLO_ENABLED=true
uvicorn app.main:app --host 127.0.0.1 --port 8089
```

Mở: [http://127.0.0.1:8089/demo](http://127.0.0.1:8089/demo) · Health: [http://127.0.0.1:8089/healthz](http://127.0.0.1:8089/healthz)

### Linux / macOS

```bash
cd SEP_Service_Photo/src
chmod +x setup.sh
./setup.sh
source .venv/bin/activate
uvicorn app.main:app --host 127.0.0.1 --port 8089
```

### Kiểm tra sau khi lên

```powershell
# PowerShell
Invoke-RestMethod http://127.0.0.1:8089/healthz

# Kỳ vọng: status=ok, ocr_mock=false, engine=paddleocr-mobile, yolo_enabled=true
# device.yolo / device.paddle = cpu|cuda; detail có thể chứa paddle_cpu_wheel
# Máy không GPU: cuda_available=false, cả hai thường = cpu — vẫn ok
.\.venv\Scripts\python.exe scripts\smoke_test.py
.\.venv\Scripts\python.exe scripts\test_bib_filter.py
```

### Những gì **không** commit (đã có `.gitignore`)

- `.env` (secret) — chỉ commit `.env.example`
- `.venv/`
- Model `*.pt` / Paddle weights (tự tải lần đầu)
- `__pycache__`, logs, IDE junk

---

## 3. Cấu hình môi trường (`.env`)

File mẫu: [`src/.env.example`](src/.env.example) → copy thành `src/.env` (local, không commit).

| Biến | Mặc định gợi ý | Ý nghĩa |
|---|---|---|
| `OCR_SERVICE_KEY` | `dev-ocr-key-change-me` | Key máy–máy (`X-Service-Key`) |
| `OCR_AUTH_DISABLED` | `true` (local) | `true` = bỏ check key (chỉ demo) |
| `OCR_MOCK` | `0` | `1` = luôn trả BIB giả `A0042` — **không** dùng khi demo ảnh thật |
| `HOST` / `PORT` | `0.0.0.0` / `8089` | Bind server |
| `THRESHOLD_AUTO` | `0.85` | ≥ ngưỡng → có thể `auto_tagged` |
| `THRESHOLD_REVIEW_MIN` | `0.50` | ≥ ngưỡng → `needs_review` |
| `NEAR_DUP_HAMMING_MAX` | `5` | dHash gần giống nếu Hamming ≤ giá trị này |
| `BLUR_MIN_VARIANCE` | `40` | Laplacian variance dưới mức → bỏ ảnh mờ |
| `MAX_IMAGE_SIDE` | `1600` | Cạnh dài tối đa sau downscale |
| `MAX_INFLIGHT` | `2` | Job OCR song song / process. **Khớp** WebAPI `Photo:Ocr:WorkerMaxParallel`. ≤2 khi Paddle còn CPU; GPU YOLO + Paddle CUDA mới cân nhắc 3–4 |
| `BIB_MIN_DIGITS` | `3` | Độ dài số BIB tối thiểu (3 = hỗ trợ fun-run 3 số) |
| `BIB_MAX_DIGITS` | `6` | Độ dài số BIB tối đa |
| `BIB_MAX_TAGS` | `8` | Số BIB tối đa / ảnh (đám đông nhiều runner) |
| `OCR_DET_MODEL` | `PP-OCRv5_mobile_det` | Model detect chữ |
| `OCR_REC_MODEL` | `en_PP-OCRv5_mobile_rec` | Model nhận dạng chữ |
| `OCR_DET_LIMIT_SIDE_LEN` | `1280` | Giới hạn cạnh khi detect text |
| `OCR_WARMUP_ON_START` | `true` | Load model lúc start |
| `OCR_DEVICE` | `auto` | `auto` \| `cpu` \| `cuda` — chọn device ưu tiên (xem §3.1) |
| `YOLO_DEVICE` | *(trống)* | Override riêng YOLO; trống = theo `OCR_DEVICE`. Ví dụ YOLO CUDA + Paddle CPU wheel |
| `YOLO_ENABLED` | `true` | Bật detect người trước OCR |
| `YOLO_MODEL` | `yolov8n.pt` | File weights **YOLOv8n** (auto-download). Không phải YOLO26 trừ khi đổi tay |
| `YOLO_CONF` | `0.25` | Ngưỡng conf person box |
| `YOLO_IOU` | `0.88` | IoU NMS — cao hơn giữ box chồng (người bị che một phần) |
| `YOLO_MAX_PEOPLE` | `10` | Tối đa người/ảnh |
| `YOLO_TORSO_PAD` | `0.08` | Pad quanh band ROI |
| `YOLO_PERSON_FULL_RETRY` | `true` | Band torso không ra BIB → thử thêm 1 crop full-person (không full-frame ảnh) |
| `OCR_FULLFRAME_FALLBACK` | `false` | `false` = không OCR cả khung (tránh watermark) |
| `REDIS_URL` | *(trống)* | **Chưa dùng** — phase WebAPI |
| `WEBAPI_CALLBACK_BASE` | *(trống)* | **Chưa dùng** — phase WebAPI |

Đổi `.env` → **restart** uvicorn (settings được cache).

### 3.1 Device (GPU/CPU) — không sập khi thiếu CUDA

Cấu hình device **chỉ thuộc service này** (`core/device.py`, `detector.py`, `ocr_engine.py`). WebAPI RaceDay chỉ gọi HTTP + `WorkerMaxParallel` — **không** cài CUDA trong BE.

| Tình huống | Hành vi |
|---|---|
| Không GPU / torch không CUDA | `OCR_DEVICE=auto` → **CPU**; process **không crash** |
| `OCR_DEVICE=cuda` nhưng không có GPU | Warning + **fallback CPU** |
| Torch CUDA OK, Paddle cài **CPU wheel** (`paddlepaddle` thường gặp) | `/healthz` → `detail` chứa `paddle_cpu_wheel`. **YOLO có thể `cuda`**, **Paddle bắt buộc `cpu`** (ép trong `ocr_engine` — tránh init `gpu:0` rồi infer 500) |
| YOLO predict/warmup CUDA lỗi giữa chừng | Tự retry **CPU** rồi chạy tiếp |
| Paddle init CUDA fail | Fallback build **CPU**; chỉ fail cứng nếu CPU wheel cũng không load được (thiếu package) |

Kiểm tra nhanh:

```powershell
(Invoke-RestMethod http://127.0.0.1:8089/healthz).device
# requested, resolved_pref, cuda_available, yolo, paddle, detail
```

**Cài GPU (tùy chọn, máy có NVIDIA):**

1. Cài [CUDA toolkit / driver](https://developer.nvidia.com/cuda-downloads) phù hợp.
2. Torch CUDA (YOLO): theo [pytorch.org](https://pytorch.org/get-started/locally/) — ví dụ cu124 — **trong `.venv`**, thay bản CPU nếu cần.
3. Paddle GPU: chỉ khi cài đúng **paddlepaddle-gpu** khớp CUDA. Nếu vẫn CPU wheel → để nguyên; YOLO GPU + Paddle CPU vẫn ổn định hơn ép Paddle `cuda`.
4. Local demo thường: `OCR_DEVICE=cuda` + `YOLO_DEVICE=cuda` (hoặc để `auto`). VPS không GPU: giữ `OCR_DEVICE=auto`.

### Link cấu hình engine (khớp version đang dùng)

| Chủ đề | Link đúng phiên bản repo | Tránh nhầm |
|---|---|---|
| **YOLOv8** model card (`yolov8n.pt`…) | https://docs.ultralytics.com/models/yolov8/ | Không lấy trang YOLO26/YOLO11 làm chuẩn trừ khi đổi weights |
| YOLOv8 detect + predict API | https://docs.ultralytics.com/models/yolov8/#usage-examples · https://docs.ultralytics.com/modes/predict/ | Ví dụ generic có thể dùng model mới — vẫn truyền `"yolov8n.pt"` như code |
| Ultralytics Python package | https://docs.ultralytics.com/usage/python/ | Version package ≠ tên kiến trúc weights |
| **PaddleOCR 3.x** OCR pipeline (`text_det_limit_side_len`, …) | https://www.paddleocr.ai/latest/en/version3.x/pipeline_usage/OCR.html | **Thay** cho guide v2.9 cũ |
| PaddleOCR 3.x text recognition / score | https://www.paddleocr.ai/latest/en/version3.x/module_usage/text_recognition.html | |
| PaddleOCR 3.x text detection module | https://www.paddleocr.ai/latest/en/version3.x/module_usage/text_detection.html | Tham số `limit_side_len` / `limit_type` |
| PP-OCRv5 technical report | https://arxiv.org/html/2507.05595 | |
| FastAPI deploy | https://fastapi.tiangolo.com/deployment/manually/ | |
| Uvicorn | https://www.uvicorn.org/settings/ | |
| Pydantic Settings | https://docs.pydantic.dev/latest/concepts/pydantic_settings/ | |

---

## 4. Cấu trúc thư mục & file

```
SEP_Service_Photo/
├── README.md                 ← File này (hướng dẫn full)
├── .gitignore                ← chặn .env, venv, model weights, cache
├── rule_design/              ← Quy tắc kỹ thuật đã chốt (BR-*)
│   ├── 00_overview.md
│   ├── 02_ocr_confidence_pipeline.md
│   ├── 03_duplicate_handling.md
│   ├── 05_api_contracts.md
│   ├── 06_perf_memory_stability.md
│   └── 07_accuracy_hard_cases.md
├── doc/                      ← Hướng dẫn & thuyết trình
│   ├── 01_nghiep_vu_…md … 07_huong_dan_demo_thuyet_trinh.md
│   ├── RaceDay_OCR_Demo_Thuyet_Trinh.pptx
│   ├── build_demo_pptx.py
│   └── pptx_assets/          ← diagram dùng build slide
├── note/CHANGELOG.md         ← nhật ký thay đổi
└── src/                      ← CODE CHẠY
    ├── setup.ps1 / setup.sh  ← bootstrap máy mới
    ├── run_demo.ps1          ← 1 lệnh: server + UI
    ├── .env.example          ← mẫu cấu hình (commit)
    ├── .env                  ← local (KHÔNG commit)
    ├── requirements.txt
    ├── sample_bib.jpg        ← ảnh smoke nhỏ
    ├── README.md             ← tóm tắt src
    ├── scripts/
    │   ├── smoke_test.py
    │   └── test_bib_filter.py
    └── app/
        ├── main.py           ← FastAPI entry, warmup, /demo, /healthz
        ├── api/jobs.py       ← REST /v1/ocr/*
        ├── core/
        │   ├── config.py     ← Settings từ .env
        │   ├── concurrency.py← MAX_INFLIGHT semaphore
        │   ├── device.py     ← OCR_DEVICE / YOLO_DEVICE + CPU fallback
        │   └── status.py     ← OcrJobStatus enum
        ├── schemas/jobs.py   ← Pydantic request/response
        ├── services/
        │   ├── pipeline.py   ← orchestrator
        │   ├── detector.py   ← YOLO + multi-band ROI
        │   ├── ocr_engine.py ← PaddleOCR wrapper
        │   ├── confidence.py ← filter + dual threshold
        │   ├── dedupe.py     ← SHA-256 + dHash
        │   ├── preprocess.py
        │   └── quality.py    ← Laplacian blur
        ├── workers/runner.py ← stub Redis (deferred)
        └── static/demo.html  ← UI demo
```

---

## 5. API nhanh

Base: `http://127.0.0.1:8089`  
Header (khi `OCR_AUTH_DISABLED=false`): `X-Service-Key: <OCR_SERVICE_KEY>`

| Method | Path | Mô tả |
|---|---|---|
| `GET` | `/healthz` | Health + engine + `device.{yolo,paddle,detail}` + `max_inflight` |
| `GET` | `/demo` | UI upload demo |
| `POST` | `/v1/ocr/jobs` | JSON + `image_url` → trả `result` (phase standalone) |
| `POST` | `/v1/ocr/jobs/upload` | Multipart file (local/demo) |
| `GET` | `/v1/ocr/jobs/{job_id}` | Kết quả in-memory |
| `GET` | `/v1/ocr/jobs?event_id=` | List theo event |
| `PUT` | `/v1/events/{event_id}/ocr-config` | Ngưỡng theo event |
| `POST` | `/v1/ocr/dedupe/clear` | Dev: xóa index SHA/dhash in-memory (sau khi truncate DB WebAPI) |

Swagger: `http://127.0.0.1:8089/docs`

Hợp đồng đầy đủ khi nối WebAPI: [`rule_design/05_api_contracts.md`](rule_design/05_api_contracts.md).

---

## 6. Tích hợp vào RaceDay WebAPI

### Nguyên tắc performance (tránh đơ / sập)

1. **WebAPI không chạy YOLO/Paddle trong request upload.**  
2. Upload → lưu storage → ghi `Photo(status=pending)` → **enqueue job** → trả `202` ngay.  
3. OCR workers lấy job từ queue (Redis) hoặc (tạm) WebAPI gọi OCR service async.  
4. Kết quả callback/internal API → WebAPI ghi tags + index search.  
5. Runner search BIB chỉ **đọc DB** (SLO &lt;2s) — không chờ OCR đồng bộ.  
6. Mỗi OCR process: `MAX_INFLIGHT=2` (mặc định) — **đồng bộ** với WebAPI `Photo:Ocr:WorkerMaxParallel`. Scale thêm instance worker khi cần; đừng tăng concurrency bừa khi Paddle còn CPU.  
7. Device GPU/CUDA cấu hình **trên OCR service** (`OCR_DEVICE` / `YOLO_DEVICE`), không trong Host WebAPI.

### Luồng đề xuất

```
Photographer → WebAPI upload → R2/CDN + DB pending
            → Queue {job_id, event_id, photo_id, image_url, roster_version}
OCR Service → pipeline → callback WebAPI /internal/photos/{id}/ocr-result
WebAPI      → persist tags, needs_review queue, search index
FE          → Corrections UI sửa tay khi needs_review / sai
```

### Phân quyền dữ liệu

| Bên | Source of truth |
|---|---|
| WebAPI | Photo ownership, roster BIB event, public tags |
| OCR | Gợi ý đọc BIB + confidence (roster chỉ **hint**) |

### Auth

- OCR ↔ WebAPI: `X-Service-Key` (service-to-service).  
- Không đưa JWT runner vào OCR service.

### Phase hiện tại vs production

| | Now (repo này) | Production |
|---|---|---|
| Xử lý job | Inline trong `POST /v1/ocr/jobs` | Redis worker (`workers/runner.py` stub) |
| Persist job | In-memory `_JOBS` | WebAPI DB |
| Callback | Chưa | `WEBAPI_CALLBACK_BASE` |

---

## 7. Pipeline & thuật toán (chi tiết + nguồn + link cấu hình)

### 7.0 Thứ tự pipeline

```
decode
 → dedupe (SHA-256 → dHash)
 → preprocess (EXIF + downscale)
 → blur gate (Laplacian)
 → YOLO person + multi-band ROI
 → PaddleOCR mỗi crop
 → classify (watermark filter + regex BIB + dual threshold + roster hint)
 → status + tags[]
```

Orchestrator: `src/app/services/pipeline.py`.

---

### 7.1 Exact duplicate — SHA-256

| | |
|---|---|
| **Ý tưởng** | Hash mật mã trên toàn bộ bytes → cùng file = cùng digest |
| **Cách chạy** | `digest = sha256(file_bytes)`; index theo `event_id`; trùng → `duplicate` |
| **Cấu hình** | Không có ngưỡng; bật qua luồng dedupe (flag `force=true` bỏ chặn) |
| **File** | `services/dedupe.py` |
| **Nguồn / đọc thêm** | [NIST — hash functions overview](https://csrc.nist.gov/projects/hash-functions) · Python [`hashlib`](https://docs.python.org/3/library/hashlib.html) |
| **Rule nội bộ** | [`rule_design/03_duplicate_handling.md`](rule_design/03_duplicate_handling.md) BR-DUP-01 |

---

### 7.2 Near-duplicate — dHash + Hamming

| | |
|---|---|
| **Ý tưởng** | Perceptual hash: ảnh trông giống (recompress/resize) dù bytes khác |
| **Cách chạy** | Resize nhỏ → so sánh pixel kề → bitstring; **Hamming** = số bit khác; `≤ NEAR_DUP_HAMMING_MAX` → near-dup |
| **Cấu hình** | `NEAR_DUP_HAMMING_MAX` (mặc định `5`) |
| **File** | `services/dedupe.py` (+ thư viện `imagehash`) |
| **Nguồn** | [Ben Hoyt — Duplicate image detection (dHash)](https://benhoyt.com/writings/duplicate-image-detection/) · [Mixpeek — perceptual hashing](https://mixpeek.com/guides/perceptual-image-hashing-near-duplicate-detection) · [imagehash PyPI](https://pypi.org/project/ImageHash/) |
| **Lưu ý** | Nhiều góc máy khác nhau của cùng runner **không** phải near-dup |

---

### 7.3 Blur gate — Laplacian variance

| | |
|---|---|
| **Ý tưởng** | Ảnh nét có cạnh mạnh → variance Laplacian cao; ảnh mờ → thấp |
| **Cách chạy** | `var = Var(gray ∗ Laplacian_3×3)`; nếu `var < BLUR_MIN_VARIANCE` → `no_bib` |
| **Cấu hình** | `BLUR_MIN_VARIANCE` (mặc định `40`) — calibrate theo sample event |
| **File** | `services/quality.py` |
| **Nguồn** | [OpenCV docs — Laplace operator](https://docs.opencv.org/4.x/d5/db5/tutorial_laplace_operator.html) (ý tưởng; code dùng NumPy, không bắt buộc OpenCV) · [pyimagesearch — blur detection](https://pyimagesearch.com/2015/09/07/blur-detection-with-opencv/) |

---

### 7.4 Person detection — YOLOv8n (`yolov8n.pt`)

| | |
|---|---|
| **Ý tưởng** | Object detection 1-stage tìm box người trong đám đông |
| **Cách chạy** | `YOLO("yolov8n.pt").predict(...)`, class COCO `person=0`, sort theo diện tích, lấy ≤ `YOLO_MAX_PEOPLE` |
| **Cấu hình** | `YOLO_ENABLED`, `YOLO_MODEL=yolov8n.pt`, `YOLO_CONF`, `YOLO_IOU`, `YOLO_MAX_PEOPLE`, `YOLO_DEVICE` / `OCR_DEVICE` |
| **File** | `services/detector.py` · probe `core/device.py` |
| **Nguồn / cấu hình** | [YOLOv8 docs](https://docs.ultralytics.com/models/yolov8/) (bảng có `yolov8n.pt`) · [Predict mode](https://docs.ultralytics.com/modes/predict/) |
| **Lưu ý docs** | Trang chủ Ultralytics có thể hiện **YOLO26** — đó là model family mới hơn; **repo này chưa dùng**. Chỉ đổi khi đổi `YOLO_MODEL` có chủ đích. |
| **Device** | `predict(device=cpu\|cuda)`; không GPU / lỗi CUDA → fallback CPU (warmup + predict). |

---

### 7.5 Multi-band torso ROI

| | |
|---|---|
| **Ý tưởng** | BIB có thể ở ngực / bụng / đùi — không chỉ 1 crop ngực |
| **Cách chạy** | Với mỗi person box cắt 3 band theo % chiều cao: chest `10–66%`, waist `35–82%`, hips `55–95%` + `YOLO_TORSO_PAD`; crop &lt;320px → upscale |
| **Cấu hình** | `YOLO_TORSO_PAD`, `OCR_FULLFRAME_FALLBACK=false` |
| **File** | `services/detector.py` → `_bib_bands` |
| **Rule** | [`rule_design/07_accuracy_hard_cases.md`](rule_design/07_accuracy_hard_cases.md) |

---

### 7.6 OCR — PP-OCRv5 mobile (PaddleOCR)

| | |
|---|---|
| **Ý tưởng** | Det tìm chữ + Rec đọc chuỗi + `rec_score ∈ [0,1]` |
| **Cách chạy** | `PaddleOCR(det=PP-OCRv5_mobile_det, rec=en_PP-OCRv5_mobile_rec)` trên mỗi crop; tắt doc orientation/unwarp; `enable_mkldnn=False` (ổn định Windows) |
| **Cấu hình** | `OCR_DET_MODEL`, `OCR_REC_MODEL`, `OCR_DET_LIMIT_SIDE_LEN`, `OCR_MOCK`, `OCR_WARMUP_ON_START`, `OCR_DEVICE` |
| **File** | `services/ocr_engine.py` · probe `core/device.py` |
| **Nguồn / cấu hình** | [OCR pipeline 3.x](https://www.paddleocr.ai/latest/en/version3.x/pipeline_usage/OCR.html) · [Text recognition](https://www.paddleocr.ai/latest/en/version3.x/module_usage/text_recognition.html) · [Text detection](https://www.paddleocr.ai/latest/en/version3.x/module_usage/text_detection.html) · [PP-OCRv5 report](https://arxiv.org/html/2507.05595) |
| **Lưu ý docs** | Không dùng trang **v2.9 inference_args** làm chuẩn — API 3.x dùng tên `text_det_limit_side_len` (khớp `OCR_DET_LIMIT_SIDE_LEN` trong `.env`) |
| **Device** | PaddleOCR 3.x: `device=cpu` \| `gpu:0`. Nếu probe báo `paddle_cpu_wheel` → **ép CPU** dù `OCR_DEVICE=cuda` (tránh 500 lúc infer). Init CUDA fail → retry CPU. |
| **Quan trọng** | `rec_score` cao ≠ đúng BIB (watermark có thể 0.99) |

Cache model lần đầu (Windows ví dụ): `%USERPROFILE%\.paddlex\official_models\` và YOLO cache Ultralytics.

---

### 7.7 Classify — filter + dual threshold

| | |
|---|---|
| **Ý tưởng** | OCR trả nhiều chữ → chỉ giữ token giống BIB; quyết định auto vs review |
| **Cách chạy** | (1) bỏ watermark zone + blocklist slogan (2) regex `[A]?`+**3–6 số** (`BIB_MIN/MAX_DIGITS`)+`[MF]?` (3) `conf ≥ THRESHOLD_AUTO` (+ roster) → `auto_tagged`; `≥ THRESHOLD_REVIEW_MIN` → `needs_review` |
| **Cấu hình** | `THRESHOLD_AUTO`, `THRESHOLD_REVIEW_MIN` · override theo event qua `PUT /v1/events/{id}/ocr-config` |
| **File** | `services/confidence.py` |
| **Nguồn tham chiếu nghiệp vụ** | [AWS Textract best practices — confidence](https://docs.aws.amazon.com/textract/latest/dg/textract-best-practices.html) · [ChronoTrack OCR bib tagging](https://director.chronotrack.com/hc/en-us/articles/360038745651-How-to-Use-the-On-Demand-OCR-Bib-Tagging-Service-in-CT-Live) · [RaceTagger — problem bibs](https://racetagger.cloud/guides/problem-solution/bib-detection-in-marathon-photography) |
| **Rule** | [`rule_design/02_ocr_confidence_pipeline.md`](rule_design/02_ocr_confidence_pipeline.md) |

---

### 7.8 Backpressure — Semaphore / `MAX_INFLIGHT`

| | |
|---|---|
| **Ý tưởng** | Giới hạn job OCR đồng thời trong 1 process để tránh OOM/đơ |
| **Cách chạy** | `asyncio.Semaphore(MAX_INFLIGHT)` bọc `run_pipeline` |
| **Cấu hình** | `MAX_INFLIGHT` (mặc định `2`; khớp WebAPI `WorkerMaxParallel`) |
| **File** | `core/concurrency.py` |
| **Nguồn** | [Python asyncio.Semaphore](https://docs.python.org/3/library/asyncio-sync.html#asyncio.Semaphore) · rule [`06_perf_memory_stability.md`](rule_design/06_perf_memory_stability.md) |

---

## 8. Thuật ngữ / viết tắt trong code

| Từ khóa | Nghĩa |
|---|---|
| **BIB** | Số báo danh gắn trên áo/quần runner |
| **OCR** | Optical Character Recognition — nhận dạng chữ trên ảnh |
| **ROI** | Region of Interest — vùng cắt để OCR (torso bands) |
| **YOLO** | You Only Look Once — họ mô hình detect object |
| **YOLOv8n** | Bản **nano** của kiến trúc **YOLOv8** — file `yolov8n.pt` (đang dùng) |
| **ultralytics (package)** | Thư viện Python chạy YOLO; số version package (8.4.x) ≠ “đang dùng YOLO26” |
| **YOLO26 / YOLO11** | Model family mới hơn trên docs Ultralytics — **chưa** phải cấu hình mặc định repo này |
| **COCO** | Dataset chuẩn; class `0` = person |
| **PaddleOCR / PP-OCR** | Engine OCR của PaddlePaddle |
| **det / rec** | Detection (tìm chữ) / Recognition (đọc chữ) |
| **rec_score / confidence** | Điểm tin cậy chuỗi OCR ∈ [0,1] — **không** = đúng tuyệt đối |
| **SHA-256** | Secure Hash Algorithm 256-bit — exact file fingerprint |
| **dHash** | Difference hash — perceptual hash ảnh |
| **Hamming distance** | Số bit khác nhau giữa 2 hash |
| **Laplacian variance** | Độ đo nét ảnh (blur gate) |
| **EXIF** | Metadata ảnh (hướng xoay…) |
| **dual threshold** | Hai ngưỡng AUTO / REVIEW |
| **auto_tagged** | Đủ tin để gắn tag tự động (vẫn có thể sai — cần monitor) |
| **needs_review** | Có ứng viên nhưng đưa photographer sửa |
| **no_bib** | Không có BIB hợp lệ / blur / không person |
| **duplicate** | Trùng exact hoặc near-dup |
| **roster** | Danh sách BIB hợp lệ của event (WebAPI sở hữu) |
| **MAX_INFLIGHT** | Số job OCR song song tối đa / process (khớp WebAPI `WorkerMaxParallel`) |
| **OCR_DEVICE** | `auto` \| `cpu` \| `cuda` — preference device toàn pipeline |
| **YOLO_DEVICE** | Override device riêng YOLO (trống = theo `OCR_DEVICE`) |
| **paddle_cpu_wheel** | Chuỗi trong `healthz.device.detail`: Paddle build không CUDA → OCR chữ chạy CPU |
| **warmup** | Chạy predict giả lúc start để nạp model vào RAM |
| **full-frame** | OCR cả ảnh (thường tắt — nhiễu watermark) |
| **service key** | Secret máy–máy, khác JWT user |
| **MVP** | Minimum Viable Product — bản đủ dùng phase hiện tại |
| **NFR** | Non-Functional Requirement (vd search &lt;2s) |
| **WebAPI** | Backend chính RaceDay (ownership, search, FE) |

Status enum: `src/app/core/status.py`.

---

## 9. Kết quả đạt được (phase hiện tại)

| Hạng mục | Kết quả |
|---|---|
| Service đứng riêng | FastAPI + `/demo` + `/healthz` + upload API |
| Pipeline đầy đủ | Dedupe → blur → YOLO multi-band → Paddle → classify |
| Tốc độ sau warm-up | Thường ~0.5–2s/ảnh CPU (tùy ảnh/số người); YOLO CUDA + Paddle CPU nhanh hơn đoạn detect |
| GPU optional | Không CUDA vẫn chạy; `/healthz` báo `yolo`/`paddle` thực tế |
| Ảnh VN sample (smoke) | Đúng core BIB trên các case rõ (vd 80074 / 80087 / 80183); case mờ/khó → `no_bib` |
| Watermark | Không gắn tag `QUYNHON` / slogan sự kiện |
| Tài liệu | `rule_design/` + `doc/` + PPTX thuyết trình thuật toán |
| An toàn repo | `.gitignore` chặn `.env`, venv, weights |

**Chưa đạt (phase sau):** Redis worker production, callback WebAPI, persist DB, FE Corrections gắn thật, scale multi-photographer có queue.

---

## 10. Lưu ý & sự cố thường gặp

| Triệu chứng | Cách xử lý |
|---|---|
| Luôn ra BIB `A0042` | Đang `OCR_MOCK=1` → đổi `0` và restart |
| Port 8089 chiếm | Tắt process cũ hoặc đổi `PORT` |
| Paddle crash oneDNN (Windows) | Code đã set `enable_mkldnn=False` / `FLAGS_use_mkldnn=0` |
| Lần đầu rất chậm | Đang tải model — chờ warmup xong; lần sau dùng cache |
| `ModuleNotFoundError` | Chạy trong `.venv` và `cd src` trước `uvicorn` |
| YOLO không tải | Cần mạng lần đầu; hoặc copy `yolov8n.pt` vào cwd `src/` |
| Máy không GPU / sợ sập | Giữ `OCR_DEVICE=auto` (hoặc `cpu`). Code fallback CPU — **không** cần CUDA để chạy |
| `healthz`: `paddle=cuda` nhưng `detail` có `paddle_cpu_wheel` | Bản cũ; restart service sau khi pull — Paddle phải ép `cpu`. Nếu vẫn GPU → kiểm tra `ocr_engine.py` |
| OCR job HTTP 500 sau khi bật `OCR_DEVICE=cuda` | Thường Paddle CPU wheel bị ép GPU. Restart bản có force CPU; hoặc tạm `OCR_DEVICE=cpu` / `YOLO_DEVICE=cuda` |
| `cuda_available=false` dù có card | Torch đang bản CPU — cài lại torch CUDA trong `.venv` (xem §3.1) |
| WebAPI chỉ xử lý 2 ảnh/lúc | Đúng: `MAX_INFLIGHT=2` + `WorkerMaxParallel=2`. Tăng **cả hai** nếu muốn thử 3–4 (risk RAM khi Paddle CPU) |
| Upload lại báo trùng sau truncate DB | `POST /v1/ocr/dedupe/clear` + header `X-Service-Key` (index SHA/dhash in-memory) |
| Ảnh không người → `no_bib` | Đúng kỳ vọng khi `OCR_FULLFRAME_FALLBACK=false` |
| Conf = 1.0 nhưng sai | Bình thường với watermark/nhầm số — dùng review + roster WebAPI |
| PowerShell chặn `.ps1` | `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` |
| Python 3.13 lỗi Paddle | Đổi sang 3.11/3.12 |
| Commit nhầm `.env` | Xóa khỏi git history; rotate `OCR_SERVICE_KEY` |

### Offline sau cache

Khi đã có YOLO weights + `%USERPROFILE%\.paddlex\official_models\` (hoặc tương đương Linux `~/.paddlex`), có thể chạy không mạng.

### Copy sang máy khác

Copy cả repo (không cần `.venv`). Trên máy mới chạy lại `setup.ps1`. Model cache **không** nằm trong repo — máy mới tải lại lần đầu (hoặc copy thủ công thư mục `.paddlex` + file `.pt`).

---

## 11. Tài liệu liên quan

| File | Nội dung |
|---|---|
| [`doc/07_huong_dan_demo_thuyet_trinh.md`](doc/07_huong_dan_demo_thuyet_trinh.md) | Điểm giải thích khi demo + thuật toán |
| [`doc/RaceDay_OCR_Demo_Thuyet_Trinh.pptx`](doc/RaceDay_OCR_Demo_Thuyet_Trinh.pptx) | Slide thuyết trình |
| [`doc/05_pham_vi_phase_hien_tai.md`](doc/05_pham_vi_phase_hien_tai.md) | In/out scope |
| [`doc/06_demo_teams.md`](doc/06_demo_teams.md) | Demo trên Teams |
| [`rule_design/`](rule_design/) | BR / contracts / perf |
| [`note/CHANGELOG.md`](note/CHANGELOG.md) | Lịch sử thay đổi |
| [`src/README.md`](src/README.md) | Tóm tắt chạy nhanh src |

---

## License / sở hữu

Nội bộ dự án SEP RaceDay — không publish model weights/secrets.  
Mọi thay đổi code/rule/doc: ghi [`note/CHANGELOG.md`](note/CHANGELOG.md).
