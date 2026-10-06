# CHANGELOG — SEP_Service_Photo

Mọi lần **add / sửa / xóa** rule, doc, hoặc source đều ghi tại đây (mới nhất trên cùng).

---

## 2026-10-06 — Sửa lệch version docs (YOLOv8 vs YOLO26, Paddle 3.x vs v2.9)

### Sửa
- `README.md`: bảng **pin phiên bản**; phân biệt weights `yolov8n.pt` vs package Ultralytics vs YOLO26 trên docs
- Đổi link Paddle từ `v2.9/inference_args` → pipeline/module **version3.x**
- `rule_design/02_…`, `doc/07_…`, `.env.example`: ghi chú khớp

### Lý do
User phát hiện click link docs hiện YOLO26 / cấu hình không khớp code.

---

## 2026-10-06 — README full + gitignore + setup máy mới

### Add / Sửa
- `README.md` (root): mục đích, tích hợp WebAPI, cấu trúc, `.env`, thuật toán + **link nguồn/cấu hình**, glossary, kết quả, troubleshooting
- `.gitignore`: chặn `.env`, venv, `*.pt`/weights, cache Paddle, IDE junk
- `src/setup.ps1`, `src/setup.sh`: bootstrap máy pull về
- `src/app/core/config.py`: load `.env` theo đường dẫn `src/` (không phụ thuộc cwd)
- `doc/02_huong_dan_setup.md` + `src/README.md`: trỏ về README gốc

### Lý do
User yêu cầu tài liệu tối đa rõ để máy khác clone/cài/chạy không lỗi; kèm nguồn thuật toán & cấu hình.

---

## 2026-10-06 — PPTX: bổ sung giải thích thuật toán

### Sửa
- `doc/build_demo_pptx.py` + PPTX: mục **03** chi tiết SHA-256, dHash/Hamming, Laplacian, YOLO, multi-band, Paddle det/rec, classify dual-threshold, Semaphore
- `doc/07_…md` section 3 viết lại dạng “cách chạy” không chỉ liệt kê tên
- Giữ diagram trong `doc/pptx_assets/` (không phụ thuộc cache Cursor)

### Lý do
User: slide chưa giải thích rõ thuật toán.

---

## 2026-10-06 — PPTX thuyết trình demo

### Add
- `doc/RaceDay_OCR_Demo_Thuyet_Trinh.pptx` — slide có mục lục, sơ đồ folder/pipeline/YOLO, ảnh code
- `doc/build_demo_pptx.py` — script build lại PPTX

### Lý do
User muốn bản docx/pptx rõ mục, ảnh code/thư mục, dễ chuyển slide khi demo.

---

## 2026-10-06 — Chuẩn hóa src + guide thuyết trình demo

### Add
- `doc/07_huong_dan_demo_thuyet_trinh.md` — điểm giải thích file/dòng, thuật ngữ, thuật toán, vì sao chọn stack
- `src/scripts/smoke_test.py` — health + sample + VN assets (dedupe scene)

### Sửa
- `pipeline.py` / `detector.py` / `main.py` / `schemas/jobs.py` / `config.py` — kiến trúc rõ, version `0.3.0`
- `.env.example` + `src/README.md` khớp config YOLO/OCR thật
- `workers/runner.py` — stub rõ “deferred”, không giả wire Redis

### Xóa
- Scripts ad-hoc trùng (`api_test_*`, `probe_*`, `quick_roster_test`) — gộp vào smoke

### Lý do
User: tối ưu src đúng kiến trúc + review vị trí demo/thuật ngữ/vì sao không dùng alternative.

---

## 2026-10-06 — Multi-band ROI (chest/waist/hips)

### Sửa
- Detector cắt 3 dải trên mỗi person (ngực / bụng / đùi) — bib gắn shorts
- Upscale crop nhỏ trước OCR
- Retest: 80074/80087/80183 OK; ảnh mờ no_bib; 8634 vẫn khó (bib nhỏ + góc nghiêng)

### Lý do
So với nền tảng khác: chỉ 2/5 đúng vì ROI ngực bỏ bib ở bụng/đùi và crop nhỏ.

---

## 2026-10-06 — YOLO person ROI + chiến lược hard cases

### Add
- `rule_design/07_accuracy_hard_cases.md`
- `src/app/services/detector.py` (YOLOv8n person → torso crop)
- Pipeline: OCR trên ROI, mặc định **không** full-frame

### Sửa
- Config `YOLO_*`, `OCR_FULLFRAME_FALLBACK=false`
- Warm-up YOLO + OCR lúc start

### Lý do
User yêu cầu chính xác trên đông người / khuất / tối–sáng: bắt buộc detect ROI trước OCR.

---

## 2026-10-06 — Lọc watermark / signage (QUYNHON2026, AB)

### Sửa
- `confidence.py`: blocklist VNEXPRESS/QUYNHON/…; bỏ vùng watermark góc trên
- Chỉ nhận BIB dạng `[A]?` + 4–5 số + `[MF]?`; bỏ fallback token ngắn (AB/ON)
- Ưu tiên bbox vùng ngực runner
- Ảnh mờ chỉ có watermark → `no_bib` thay vì gắn tag sự kiện

### Lý do
Test 5 ảnh VnExpress Quy Nhon: hay trả QUYNHON2026 / AB thay vì số BIB.

---

## 2026-10-06 — Tăng tốc OCR (mobile + warmup)

### Sửa
- Đổi sang `PP-OCRv5_mobile_det` + `en_PP-OCRv5_mobile_rec`
- Tắt textline orientation / doc modules; `MAX_IMAGE_SIDE=1280`
- Warm-up model lúc start server
- Benchmark local: ~5s → ~0.4s/ảnh sau warm

---

## 2026-10-06 — Bật PaddleOCR thật + lọc BIB

### Sửa
- `OCR_MOCK=0` mặc định; cài `paddlepaddle` + `paddleocr` 3.x
- `ocr_engine.py` dùng `predict()` + tắt mkldnn (fix crash Windows)
- `confidence.py` lọc token giống BIB, bỏ chữ QC dài; trả `raw_ocr`
- Demo UI: roster `[]`, hiện raw_ocr, cảnh báo nếu còn mock

### Lý do
User test ảnh giải VN — mock luôn trả A0042 nên “không đúng chút nào”.

---

## 2026-10-06 — Demo UI cho Teams

### Add
- `src/app/static/demo.html` + route `/demo`
- `doc/06_demo_teams.md`
- `src/sample_bib.jpg` (ảnh mẫu)

### Sửa
- `main.py` redirect `/` → `/demo`

### Lý do
User cần share màn hình Teams để thuyết trình OCR.

---

## 2026-10-06 — Chốt scope standalone + perf gates

### Add
- `rule_design/06_perf_memory_stability.md`
- `doc/05_pham_vi_phase_hien_tai.md`
- `src/app/services/quality.py` (blur gate Laplacian)
- `src/app/core/concurrency.py` (`max_inflight` semaphore)
- API `POST /v1/ocr/jobs/upload` (test không cần WebAPI)
- API `GET /v1/ocr/jobs` list theo event

### Sửa
- README / overview / setup / API contracts: WebAPI = **deferred**
- Pipeline: dedupe → blur gate → preprocess → OCR; trả `result` ngay trong response
- Config: `BLUR_MIN_VARIANCE`, `MAX_IMAGE_SIDE`, `MAX_INFLIGHT`, `OCR_AUTH_DISABLED`
- `WEBAPI_CALLBACK_BASE` mặc định rỗng (không dùng phase này)

### Xóa
- (không)

### Lý do
User chốt: chỉ handle service OCR riêng; tích hợp main WebAPI để sau.

---

## 2026-10-06 — Khởi tạo service scaffold

### Add
- Thư mục `rule_design/`, `note/`, `src/`, `doc/` + skeleton FastAPI

### Chi tiết
Xem `note/2026-10-06_init_service_scaffold.md`
