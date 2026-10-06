# 00 — Overview Rule Design (OCR Service)

## Mục tiêu service

Nhận ảnh giải chạy → phát hiện / gắn nhãn số BIB → trả kết quả + confidence.

OCR **hỗ trợ** (assistive), **không** cam kết 100% đúng — đúng Report 1 LI-2 và Report 2 Risk #4.

### Phase hiện tại vs sau

| Phase | Phạm vi |
|---|---|
| **Now** | Chỉ `SEP_Service_Photo` tự đứng (API + pipeline + rule). Không nối WebAPI/FE. |
| **Later** | WebAPI ownership ảnh, callback, FE photographer/photos gọi qua main API. |

## Phân ranh giới trách nhiệm

| Thành phần | Phase Now | Phase Later |
|---|---|---|
| **SEP_Service_Photo** | Ingest (URL/file), dedupe, blur gate, OCR, classify, lưu job local | Giữ nguyên; nhận job từ WebAPI |
| **SEP_WebAPI** | **Chưa đụng** | Ownership ảnh, RBAC, gọi OCR, search BIB |
| **FE** | **Chưa đụng** | Upload / corrections / Photo Finder |

## Pipeline chuẩn (1 ảnh) — phase Now

```
Client → POST /v1/ocr/jobs[/upload]
    → max_inflight semaphore
    → Exact/near dedupe
    → Blur gate (ảnh quá mờ)
    → Preprocess (orient / downscale)
    → YOLO person → crop vùng ngực/torso (không OCR full-frame mặc định)
    → PaddleOCR trên từng ROI (đông người = nhiều ROI)
    → Filter watermark/signage + optional roster
    → AUTO_TAG | NEED_REVIEW | NO_BIB | DUPLICATE
    → (Later) callback WebAPI
```

Chi tiết hard cases: `07_accuracy_hard_cases.md`.

## Trạng thái kết quả (enum bắt buộc)

| Status | Ý nghĩa | Ai xử lý tiếp |
|---|---|---|
| `queued` | Chờ worker | System |
| `processing` | Đang OCR | System |
| `auto_tagged` | Confidence ≥ ngưỡng AUTO và BIB ∈ roster | Searchable ngay |
| `needs_review` | Confidence thấp / format lệch / nhiều ứng viên xung đột | Photographer Corrections |
| `no_bib` | Không thấy BIB hợp lệ | Photographer (gắn tay hoặc bỏ) |
| `duplicate` | Trùng ảnh đã có trong event | System (không index lần 2) |
| `failed` | Lỗi kỹ thuật (file hỏng, timeout) | Retry / photographer re-upload |
| `manual_corrected` | Photographer đã sửa BIB | Searchable |
| `runner_reported` | Runner báo sai → quay lại review | Photographer |

## Nguyên tắc thiết kế rule

1. **Một rule = một hành vi quan sát được** (input → output → điều kiện).
2. **Ưu tiên không gắn nhầm** hơn là gắn nhiều (false positive hại hơn false negative) — cùng tinh thần ChronoTrack OCR: không “best guess” khi không chắc.
3. Mọi ngưỡng (confidence, hamming distance) **config theo event**, Admin chỉnh được (khớp scenario “điều chỉnh ngưỡng AI”).
4. Mọi thay đổi rule phải ghi `note/CHANGELOG.md` + cập nhật checklist tối ưu.

## Tài liệu liên quan

- `01_business_rules.md` — nghiệp vụ BIB Photo Finder
- `02_ocr_confidence_pipeline.md` — mờ / khuất / confidence
- `03_duplicate_handling.md` — duplicate file & near-duplicate
- `04_deployment_mode_decision.md` — batch vs cam realtime
- `05_api_contracts.md` — hợp đồng API (phần WebAPI = later)
- `06_perf_memory_stability.md` — tốc độ / RAM / tránh sập
- `07_accuracy_hard_cases.md` — đông người / khuất / tối sáng + YOLO
- `CHECKLIST_optimization.md` — kiểm tra tối ưu trước khi merge
