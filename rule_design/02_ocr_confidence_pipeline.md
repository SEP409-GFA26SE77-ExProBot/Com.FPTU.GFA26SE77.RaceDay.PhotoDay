# 02 — OCR Confidence Pipeline (ảnh mờ / khuất / lệch góc)

## Vấn đề

Ảnh marathon thường gặp: chuyển động mờ, BIB gập, tay/áo che, ngược sáng, góc nghiêng, chữ số dễ nhầm (`O/0`, `I/1`, `B/8`).

Report 2 Risk #4 yêu cầu:

1. OCR chạy **background job**
2. Có **confidence score**
3. Low-confidence → màn **Review OCR mismatches**
4. **Image pre-processing**
5. Runner được **report ảnh sai**
6. OCR là **assistive**, không 100%

---

## Tham chiếu ngoài (bắt buộc đọc khi chỉnh ngưỡng)

| Chủ đề | Nguồn | Link |
|---|---|---|
| PaddleOCR `rec_score` / text recognition | PaddleOCR docs | https://www.paddleocr.ai/latest/en/version3.x/module_usage/text_recognition.html |
| Tham số `text_rec_score_thresh`, det thresh | PaddleOCR inference args | https://www.paddleocr.ai/v2.9/en/ppocr/blog/inference_args.html |
| Augment blur/rotate trong PP-OCRv5 | PaddleOCR 3.0 Technical Report | https://arxiv.org/html/2507.05595 |
| Tip: check confidence, ảnh ≥300 DPI khi kém | PaddleOCR skill tips | https://github.com/PaddlePaddle/PaddleOCR/blob/1903e73d/skills/paddleocr-text-recognition/SKILL.md |
| Confidence + human review khi thấp | AWS Textract best practices | https://docs.aws.amazon.com/textract/latest/dg/textract-best-practices.html |
| Human loop theo ngưỡng confidence | Amazon A2I + Textract | https://docs.aws.amazon.com/sagemaker/latest/dg/a2i-textract-task-type.html |
| OCR bib: không guess khi không đọc được | ChronoTrack Live OCR | https://director.chronotrack.com/hc/en-us/articles/360038745651-How-to-Use-the-On-Demand-OCR-Bib-Tagging-Service-in-CT-Live |
| Folded / covered / crowded bibs → flag review | RaceTagger bib detection | https://racetagger.cloud/guides/problem-solution/bib-detection-in-marathon-photography |
| Workflow batch tag bib + start-list | RaceTagger AI tagging guide | https://racetagger.cloud/guides/sport-workflow-guide/how-to-tag-marathon-photos-with-ai |

---

## BR-OCR-PRE — Preprocess (trước khi OCR)

Áp dụng theo thứ tự; mỗi bước log `preprocess_flags[]`.

| Bước | Khi nào | Mục đích |
|---|---|---|
| EXIF orient | Luôn | Ảnh quay ngang/dọc |
| Downscale cap cạnh dài (vd 3000px) | Ảnh rất lớn | Tốc độ; giữ đủ chi tiết BIB |
| Contrast / CLAHE nhẹ | Ảnh ngược sáng | Tăng tương phản số BIB |
| Sharpen nhẹ | Blur nhẹ (Laplacian variance thấp vừa) | Không over-sharpen ảnh đã rõ |
| Không upscale quá đà | Blur nặng | Upscale không “bịa” nét — đưa review sớm |
| Multi-crop ROI | Detect nhiều vùng số | Crop quanh runner/torso nếu có detector phụ (phase 2) |

**Quy tắc tối ưu:** Preprocess chỉ được bật nếu A/B trên sample set **không giảm** precision auto_tagged.

---

## BR-OCR-DET — Detection

Dùng PaddleOCR detector:

- Giữ `text_det_limit_side_len` đủ cao để số BIB nhỏ không bị mất khi downscale (xem inference args).
- Mỗi box có `det_score`.
- Lọc box quá nhỏ / aspect ratio không giống bib plate (config theo event).

---

## BR-OCR-REC — Recognition + điểm tin cậy

Mỗi candidate:

```
confidence = rec_score ∈ [0,1]   # từ PaddleOCR
```

Có thể kết hợp (phase 2):

```
final_confidence = w1*rec_score + w2*det_score + w3*roster_bonus
```

MVP: dùng `rec_score` sau normalize; `roster_bonus` chỉ là rule cứng (pass/fail), chưa trộn điểm.

---

## BR-OCR-NORM — Chuẩn hóa chữ dễ nhầm

Áp dụng **có điều kiện** (chỉ khi sau normalize khớp roster):

| Raw | Thử thay | Ghi chú |
|---|---|---|
| `O` trong vị trí digit | `0` | |
| `I` / `l` trong digit | `1` | |
| `B` lẫn `8` | giữ raw + tạo candidate phụ | Đưa cả 2 nếu cả hai ∈ roster → `needs_review` xung đột |

Không silent-fix nếu cả raw và normalized đều ∈ roster khác nhau → **conflict → review**.

---

## BR-OCR-CONF — Ngưỡng phân tầng (mặc định)

Khớp UI FE Admin (xanh ≥95, vàng ≥88, đỏ thấp) và tinh thần AWS: ngưỡng cao khi sai gây hại.

| Band | Điều kiện mặc định | Status |
|---|---|---|
| AUTO | `confidence ≥ 0.95` AND đúng format AND ∈ roster AND không conflict | `auto_tagged` |
| REVIEW | `0.70 ≤ confidence < 0.95` OR format lệch OR conflict OR not-in-roster | `needs_review` |
| DROP_GUESS | `confidence < 0.70` | `needs_review` / `no_bib` — **không** gắn auto |
| NO_BIB | Không candidate nào sau filter | `no_bib` |

Admin được chỉnh `threshold_auto` / `threshold_review_min` theo event (BR-PHO-07).

**Nguyên tắc ChronoTrack:** nếu không đọc chắc → để untagged, không best-guess.

---

## BR-OCR-OCCLUDE — Che khuất / một phần BIB

| Tín hiệu | Hành vi |
|---|---|
| Text nhận được 1 phần (vd `A00??`) | Không expand thành full BIB bằng đoán; `needs_review` + `partial_read` |
| Nhiều box chồng / crowd | Tag multi-BIB nếu mỗi box đủ conf; box thấp → review riêng |
| Không đọc được vì gập/che | `no_bib` — photographer gắn tay nếu cần |

---

## BR-OCR-MULTI — Nhiều BIB một ảnh

- Lưu **N tags** / photo.
- Photo Finder: ảnh xuất hiện khi runner search **bất kỳ** BIB đã tag trên ảnh.
- Duplicate tag cùng BIB trên cùng ảnh: gộp, giữ conf cao nhất.

---

## BR-OCR-REPROCESS

- Chỉ reprocess: `needs_review`, `no_bib`, `failed`, hoặc toàn bộ khi đổi model.
- Ảnh `manual_corrected` **không** bị OCR ghi đè trừ khi photographer bấm “Re-run OCR”.

---

## Checklist tối ưu riêng pipeline (bắt buộc trước khi tăng threshold)

Xem thêm `CHECKLIST_optimization.md`.

1. Đo trên ≥ 200 ảnh thật (hoặc synthetic bib) theo 4 nhóm: rõ / mờ / khuất / góc lệch.
2. Báo cáo Precision@AUTO, Recall@AUTO, % đưa vào review.
3. Ưu tiên Precision AUTO ≥ 98% trước khi hạ ngưỡng để giảm review.
4. Mọi thay đổi ngưỡng ghi `note/`.
