# 01 — Business Rules (BIB Photo Finder)

Nguồn bắt buộc: Report 1 (FE-06, FE-07, LI-2), Report 2 (Photographer 3.1–3.5, Risk #4/#5), scenario Fun Run bước 9, FE mock FR-PHO-02/03/04.

---

## BR-PHO-01 — Bulk upload theo event

| Mục | Quy định |
|---|---|
| **Trigger** | Photographer chọn event → upload nhiều ảnh |
| **Input** | `event_id`, danh sách file (JPG/PNG; RAW optional phase 2), metadata zone tùy chọn |
| **Rule** | Mỗi file tạo 1 `photo_asset` + 1 `ocr_job` gắn `event_id` |
| **Giới hạn đề xuất (khớp FE mock)** | ≤ 25 MB/file; batch ≤ 500 file/lần |
| **Output** | Trạng thái upload `accepted` → job `queued` |
| **Không** | Chạy OCR đồng bộ trong request HTTP upload |

---

## BR-PHO-02 — OCR tự động phát hiện BIB

| Mục | Quy định |
|---|---|
| **Trigger** | Worker lấy job từ queue |
| **Engine** | PaddleOCR (Report 2 training: BIB region + digit recognition) |
| **Output tối thiểu** | `candidates[]` = `{ bib_raw, bib_normalized, confidence, bbox, engine }` |
| **Gắn nhãn** | Ảnh có thể có **nhiều BIB** (nhiều runner trong 1 frame) → lưu **multi-tag** |
| **Accept OCR** | Chỉ khi thỏa BR-OCR-CONF (file 02) |

---

## BR-PHO-03 — Validate BIB theo roster sự kiện

| Mục | Quy định |
|---|---|
| **Input** | `bib_normalized`, `event_id` |
| **Rule** | BIB phải khớp format event (ví dụ `A0042` hoặc số thuần) **và** thuộc danh sách BIB confirmed của event (WebAPI cung cấp snapshot/roster) |
| **Nếu format đúng nhưng không ∈ roster** | `needs_review` + lý do `bib_not_in_roster` (có thể là OCR sai hoặc BIB day-of) |
| **Nếu format sai** (O/0, I/1 lẫn…) | Thử normalize (xem BR-OCR-NORM) rồi validate lại; vẫn fail → review |

---

## BR-PHO-04 — Review OCR mismatches

| Mục | Quy định |
|---|---|
| **Ai** | Photographer (web) |
| **Vào queue khi** | `needs_review` hoặc `no_bib` (nếu photographer chọn “show untagged”) |
| **Hành động** | Confirm candidate / sửa BIB / đánh dấu “không có BIB” / bỏ ảnh |
| **Sau khi sửa** | Status → `manual_corrected`; ảnh searchable ngay theo BIB mới |
| **Không** | Runner không được sửa nhãn OCR của người khác |

---

## BR-PHO-05 — BIB Photo Finder (Runner)

| Mục | Quy định |
|---|---|
| **Input** | `bib` (+ optional `event_id`) |
| **Nguồn ảnh** | Chỉ ảnh có tag `auto_tagged` hoặc `manual_corrected` (không show `needs_review` chưa duyệt) |
| **NFR (Report 2)** | Search theo BIB **< 2 giây**; hỗ trợ ≥ 100 concurrent users (WebAPI + index, OCR async không block search) |
| **Report mismatch** | Runner gửi report → ảnh chuyển `runner_reported` → photographer review (khớp FE User + Risk #4) |

---

## BR-PHO-06 — Thống kê xem/tải

| Mục | Quy định |
|---|---|
| **Metric** | views, downloads theo event / photo / bib |
| **OCR service** | Không bắt buộc sở hữu metric; WebAPI ghi log; OCR chỉ cung cấp `processed_count`, `auto_rate`, `avg_confidence` cho màn OCR |

---

## BR-PHO-07 — Admin điều chỉnh ngưỡng AI

| Mục | Quy định |
|---|---|
| **Trigger** | Admin / Organizer kỹ thuật (scenario điểm 6 phía trên luồng) |
| **Config theo event** | `threshold_auto`, `threshold_review_min`, preprocess flags, enable/disable roster hard-check |
| **Rule** | Đổi ngưỡng **không** re-OCR tự động toàn bộ trừ khi bấm “Reprocess pending/low-confidence” |
| **Audit** | Ghi ai đổi, giá trị cũ/mới, thời điểm |

---

## BR-PHO-08 — Giới hạn chấp nhận (Limitation)

Từ Report 1 **LI-2**:

> Ảnh BIB không rõ (ánh sáng, góc, che khuất) **bắt buộc** qua sửa tay — không auto-match.

Rule kỹ thuật chi tiết: `02_ocr_confidence_pipeline.md`.

---

## Ma trận ưu tiên (MoSCoW cho OCR service)

| Priority | Item |
|---|---|
| Must | Bulk job queue, PaddleOCR detect+rec, confidence tiers, review callback, roster validate, exact+near duplicate |
| Should | Preprocess blur/occlusion, multi-BIB/photo, runner report loop, admin threshold |
| Could | RAW preview OCR, zone metadata gợi ý, active learning từ corrections |
| Won't (MVP) | Camera check-in realtime OCR gắn vào cổng xuất phát; face recognition thay BIB |
