# Hướng dẫn thuyết trình demo — RaceDay OCR Service

Tài liệu “điểm vào code”: **folder / file / nhóm dòng**, **thuật ngữ**, **thuật toán + công nghệ**, **vì sao chọn A chứ không B**.  
Dùng kèm UI `/demo` hoặc `scripts/smoke_test.py`.

**Bản trình chiếu (PPTX):** [`RaceDay_OCR_Demo_Thuyet_Trinh.pptx`](./RaceDay_OCR_Demo_Thuyet_Trinh.pptx)  
Build lại: `python doc/build_demo_pptx.py` (từ repo root hoặc `src` với path `..\doc\...`).

---

## 0. Bản đồ thư mục (mở Explorer khi demo)

| Folder | Vai trò khi nói |
|---|---|
| `rule_design/` | Quyết định kỹ thuật (confidence, dedupe, YOLO ROI…) — “chúng tôi đã chốt rule trước khi code” |
| `doc/` | Nghiệp vụ + research + phạm vi phase + **file này** |
| `note/CHANGELOG.md` | Lịch sử thay đổi ngắn |
| `src/app/` | Code chạy thật |
| `src/scripts/` | Smoke / unit filter — không phải production path |

**Không demo sâu:** `src/app/workers/runner.py` (stub Redis), Redis/callback env — phase WebAPI sau.

---

## 1. Flow demo 3 phút (nói + chỉ màn hình)

1. Mở `/healthz` → `ocr_mock: false`, `yolo_enabled: true`, `engine: paddleocr-mobile`.  
2. Mở `/demo` → upload ảnh VN rõ BIB → `auto_tagged` / `needs_review` + `tags` + `raw_ocr`.  
3. Upload lại **cùng file**, bỏ Force → `duplicate` (SHA-256 / dHash).  
4. Ảnh mờ / chỉ watermark → `no_bib` (đúng: không gắn QUYNHON/AB).  
5. Nhắc: **Photographer Corrections** (UI Web) vẫn bắt buộc theo doc — OCR không thay review thủ công 100%.

---

## 2. Điểm giải thích theo file (ưu tiên khi share code)

### 2.1 Entry + warmup — `src/app/main.py`

| Nhóm dòng | Nói gì |
|---|---|
| `lifespan` ~L17–31 | Load **YOLO + PaddleOCR một lần** lúc start → tránh cold-start 5–10s mỗi request |
| `app.include_router` + `/demo` | API `/v1` + UI tĩnh tách biệt |
| `/healthz` ~L54–70 | Chứng minh mock off / YOLO on khi demo |

**Thuật ngữ:** *warm-up* = chạy 1 lần predict giả để nạp model vào RAM.

**Vì sao không lazy-load mỗi request?** CPU OCR nặng; warmup đổi “chậm lần đầu” thành “chậm lúc start server” (chấp nhận được cho worker).

---

### 2.2 API contract — `src/app/api/jobs.py`

| Nhóm dòng | Nói gì |
|---|---|
| `_JOBS` in-memory ~L18–19 | Standalone: chưa Postgres/Redis — đủ demo |
| `POST /ocr/jobs` | Contract JSON + `image_url` (WebAPI sẽ gọi kiểu này) |
| `POST /ocr/jobs/upload` ~L60–97 | Demo local không cần CDN |
| `PUT .../ocr-config` | Ngưỡng theo event (`threshold_auto`, blur, hamming) |

**Thuật ngữ:** *service key* (`X-Service-Key`) = auth máy–máy, không phải login runner.

**Vì sao không JWT user?** OCR worker là internal service; auth user thuộc WebAPI.

---

### 2.3 Orchestrator — `src/app/services/pipeline.py` ⭐ (slide chính)

Thứ tự cố định (comment đầu file + `_run`):

```
decode → dedupe → preprocess → blur gate
→ YOLO multi-band ROI → OCR mỗi crop → classify
```

| Nhóm dòng | Thuật ngữ / việc làm |
|---|---|
| `run_pipeline` + semaphore ~L54–61 | `MAX_INFLIGHT` — giới hạn job song song (RAM) |
| Dedupe ~L82–98 | Exact SHA-256 + near dHash |
| Blur gate ~L103–115 | Laplacian variance; ảnh quá mờ → `no_bib` sớm |
| `_ocr_on_rois` ~L160–205 | Chỉ OCR trên ROI người; mặc định **không** full-frame |
| Upscale crop nhỏ ~L174–180 | Crop torso < 320px → phóng LANCZOS trước OCR |
| `classify(...)` ~L120–126 | Lọc watermark + band confidence + roster hint |

**Vì sao không OCR full-frame mặc định?** Ảnh marathon VN đầy watermark/biển QC → OCR “tự tin” đọc QUYNHON/AB thay vì BIB.  
**Vì sao không tắt YOLO?** Đông người / góc xa: full-frame nhiễu; ROI ngực–đùi tập trung chữ số.

---

### 2.4 YOLO person + multi-band — `src/app/services/detector.py` ⭐

| Nhóm dòng | Nói gì |
|---|---|
| `PersonDetector.detect` ~L60–99 | YOLOv8n, class COCO `person=0` |
| Sort theo diện tích box ~L77 | Ưu tiên runner lớn (gần camera) |
| `_bib_bands` ~L102–131 | 3 dải: **chest / waist / hips** (bib có thể ở quần) |
| `offset_candidates_bbox` | Đưa bbox crop về tọa độ ảnh gốc |

**Công nghệ:** weights **`yolov8n.pt`** (kiến trúc YOLOv8 nano) qua package Ultralytics — nhanh CPU.  
Docs Ultralytics có thể hiện YOLO26: đó là model mới hơn, **không** phải mặc định repo (`YOLO_MODEL=yolov8n.pt`).

| Không dùng | Lý do |
|---|---|
| YOLO large / pose full | Chậm, overkill cho demo CPU |
| Chỉ crop ngực cố định | Miss bib gắn bụng/đùi (case VN đã gặp) |
| Train detector “bib plate” riêng | Cần dataset gắn nhãn VN — phase sau |
| OpenCV Haar | Không ổn định đám đông / góc nghiêng |

---

### 2.5 PaddleOCR — `src/app/services/ocr_engine.py`

| Nhóm dòng | Nói gì |
|---|---|
| Env `FLAGS_use_mkldnn=0` | Tránh crash oneDNN trên Windows CPU |
| `PaddleOCR(...)` ~L38–47 | Mobile det/rec; tắt doc orientation / unwarp |
| `OCR_MOCK` → luôn `A0042` | Chỉ smoke API — **không** demo ảnh thật |
| `_parse_predict` | Chuẩn hóa output PaddleOCR 3.x → `OcrCandidate` |

**Công nghệ:** **PP-OCRv5 mobile** (`PP-OCRv5_mobile_det` + `en_PP-OCRv5_mobile_rec`).

| Không dùng | Lý do |
|---|---|
| Server / heavy OCR | Chậm CPU, RAM lớn |
| Tesseract | Yếu chữ nghiêng / ảnh race thật |
| EasyOCR / cloud Vision API | Nặng hoặc phụ thuộc mạng; NFR offline sau cache |
| `OCR_MOCK=1` khi demo VN | Luôn A0042 → hiểu nhầm “OCR sai” |

---

### 2.6 Confidence + filter BIB — `src/app/services/confidence.py` ⭐

| Nhóm dòng | Thuật ngữ |
|---|---|
| `_BLOCK_SUBSTR` ~L15–25 | Blocklist watermark/sponsor (VNEXPRESS, QUYNHON…) |
| `_bib_patterns()` | Shape BIB: `[A]?` + **3–6 số** (`BIB_MIN/MAX_DIGITS`) + `[MF]?` |
| `_in_watermark_zone` ~L64–79 | Bỏ chữ góc trên / top-left |
| `_torso_bonus` | Cộng nhẹ confidence nếu bbox vùng thân |
| `extract_bib_candidates` | Lấy core số; bỏ year/phone |
| `classify` bands ~L235–265 | `threshold_auto` / `threshold_review_min` → status |

**Thuật ngữ status:**

| Status | Nghĩa demo |
|---|---|
| `auto_tagged` | Đủ tin + (nếu có) khớp roster hint |
| `needs_review` | Có ứng viên nhưng thấp / lệch roster → UI photographer |
| `no_bib` | Không có token giống BIB (hoặc blur) |
| `duplicate` | Trùng ảnh đã xử lý |
| `failed` | Decode/fetch lỗi |

**Quan trọng nói rõ:** `confidence ≈ 1.0` = model **tự tin về chuỗi đọc được**, không = “đúng BIB tuyệt đối”. Roster WebAPI + review vẫn cần.

| Không dùng | Lý do |
|---|---|
| Chỉ lấy token OCR score cao nhất | Watermark thường score cao hơn BIB nhỏ |
| Fuzzy match mọi chữ số 3–6 | Nhiều false positive (năm, SĐT) |
| Auto-tag khi sai roster | Gắn nhầm ảnh cho runner khác |

---

### 2.7 Dedupe — `src/app/services/dedupe.py`

| Cơ chế | Việc làm |
|---|---|
| SHA-256 bytes | Trùng file bit-identical |
| dHash + Hamming ≤ `NEAR_DUP_HAMMING_MAX` | Near-duplicate (resize/recompress nhẹ) |

**Vì sao không chỉ filename?** Photographer đổi tên / re-export.  
**Vì sao không perceptual hash nặng (pHash + ML)?** dHash đủ MVP; index Redis theo `event_id` phase sau.

---

### 2.8 Preprocess + blur — `preprocess.py`, `quality.py`

| File | Việc |
|---|---|
| `preprocess` | EXIF orient + downscale `MAX_IMAGE_SIDE` (mặc định 1600) |
| `laplacian_variance` | Gate ảnh quá mờ trước khi tốn YOLO/OCR |

**Vì sao không CLAHE mạnh?** Dễ méo digit đêm/đèn flash (đã ghi trong preprocess).

---

### 2.9 Config — `src/app/core/config.py` + `.env`

Chỉ các knob hay nhắc khi Q&A:

- `THRESHOLD_AUTO` / `THRESHOLD_REVIEW_MIN` — band auto vs review  
- `YOLO_*` / `OCR_FULLFRAME_FALLBACK=false` — ROI strategy  
- `MAX_INFLIGHT=1` — ổn định RAM 1 worker  
- `OCR_MOCK` — bật tắt đọc thật  

---

## 3. Thuật toán — giải thích (không chỉ tên)

> Bản trình chiếu PPTX mục **03** đi sâu từng thuật toán (ý tưởng → cách chạy → ngưỡng → file).

### 3.1 SHA-256 (exact duplicate)
- **Input:** toàn bộ bytes file. **Output:** hex digest.
- Index `event_id → digest → photo_id`. Trùng digest → `duplicate`, bỏ OCR.
- **Không** bắt resize/recompress → cần dHash.

### 3.2 dHash + Hamming (near-duplicate)
- Resize nhỏ, so sánh pixel kề → chuỗi bit. **Hamming** = số bit khác.
- `hamming ≤ 5` → near-dup. Hai góc máy khác → Hamming lớn → **không** gộp (đúng: nhiều ảnh cùng BIB).

### 3.3 Laplacian variance (blur gate)
- `var = Var(ảnh ∗ Laplacian 3×3)`. Ảnh nét → var cao; mờ → thấp.
- `var < BLUR_MIN_VARIANCE (40)` → `no_bib` sớm, không chạy YOLO/OCR.

### 3.4 YOLOv8n person
- Det 1-stage, class COCO `person=0`, lấy tối đa N box theo diện tích.
- Mục đích: thu hẹp vùng trước OCR (tránh watermark full-frame).

### 3.5 Multi-band ROI
- Với mỗi person: cắt **chest / waist / hips** theo % chiều cao box (+ pad).
- Crop &lt; 320px → upscale. Lý do: bib VN hay ở bụng/đùi, 1 band ngực miss.

### 3.6 PP-OCRv5 mobile
- **Det** tìm chữ + **Rec** đọc chuỗi + `rec_score ∈ [0,1]`.
- `rec_score` cao ≠ đúng BIB (slogan có thể 0.99) → bắt buộc classify.

### 3.7 Classify (filter + dual threshold)
1. Bỏ watermark zone + blocklist (QUYNHON, VNEXPRESS…).
2. Regex BIB `[A]?` + **3–6 số** (`BIB_MIN/MAX_DIGITS`) + `[MF]?`; bỏ năm/SĐT.
3. `conf ≥ 0.85` (+ roster) → `auto_tagged`; `≥ 0.50` → `needs_review`; dưới → loại.

### 3.8 Semaphore `MAX_INFLIGHT`
- Trong 1 process chỉ N job OCR đồng thời (mặc định 1). Scale = thêm worker, không tăng inflight bừa.

| Cheat-sheet | Mục đích |
|---|---|
| SHA-256 | Exact dup |
| dHash+Hamming | Near dup |
| Laplacian | Blur gate |
| YOLOv8n | Person boxes |
| Multi-band | Crop bib |
| PP-OCRv5 | Đọc chữ + score |
| Dual threshold | auto vs review |
| Semaphore | Bảo vệ RAM |

---

## 4. “Vì sao stack này?” — câu trả lời sẵn

1. **FastAPI** — API async mỏng, dễ gắn WebAPI sau; không cần Django full stack.  
2. **PaddleOCR mobile** — cân bằng tốc độ/độ chính xác offline CPU; hơn Tesseract trên ảnh race.  
3. **YOLO rồi OCR** — giảm nhiễu full-frame; chuẩn bài toán “chữ nhỏ trên người”.  
4. **Không RFID trong service này** — RFID thuộc timing/WebAPI; OCR gắn **ảnh** với BIB.  
5. **Batch photographer > cam realtime** — xem `doc/04_quyet_dinh_batch_vs_cam.md` (ổn định, review được, NFR search <2s là query đã index).  
6. **Roster chỉ hint ở OCR** — ownership validation nằm WebAPI (tránh lệch source of truth).  
7. **Chưa Redis worker** — tránh over-engineer trước khi có queue production; stub giữ chỗ.

---

## 5. Câu hỏi thường gặp khi demo

| Câu hỏi | Trả lời ngắn | Chỉ vào |
|---|---|---|
| Conf = 1 có chắc đúng? | Không — là score nhận dạng chuỗi | `confidence.py` classify |
| Sao trước chỉ 2/5? | ROI ngực + watermark; đã multi-band + filter | `detector._bib_bands`, blocklist |
| Ảnh không có người? | `no_person_roi` / `no_bib` | `pipeline._ocr_on_rois` |
| Scale 10 photographer? | Nhiều worker + queue Redis; `MAX_INFLIGHT` mỗi process | `concurrency.py`, worker stub |
| Offline? | Sau khi cache model YOLO + Paddle | warmup + cache paddle/ultralytics |
| Ai sửa sai? | Photographer Corrections trên Web | doc nghiệp vụ — ngoài src OCR |

---

## 6. Lệnh kiểm tra nhanh trước giờ demo

```powershell
cd d:\SEP\SEP_Service_Photo\src
.\.venv\Scripts\Activate.ps1
# .env: OCR_MOCK=0, YOLO_ENABLED=true
uvicorn app.main:app --host 127.0.0.1 --port 8089
# terminal khác:
python scripts\smoke_test.py
python scripts\test_bib_filter.py
```

Checklist: health OK · mock off · ít nhất 1 ảnh VN ra đúng core số BIB · ảnh watermark-only không ra tag sự kiện.
