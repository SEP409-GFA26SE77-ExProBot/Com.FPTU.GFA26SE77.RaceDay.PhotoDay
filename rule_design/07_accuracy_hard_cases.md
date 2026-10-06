# 07 — Độ chính xác trên mọi tình huống khó

## Mục tiêu thực tế

**Tối đa Precision auto-tag + tối đa ảnh được gắn đúng sau review.**  
Không cam kết 100% auto trên mọi ảnh (LI-2 / Risk #4). Ảnh không đọc được → `no_bib` / `needs_review`, **không đoán**.

## Ma trận tình huống → hành vi bắt buộc

| Tình huống | Detect (YOLO) | OCR | Kết quả mong đợi |
|---|---|---|---|
| Đông người (nhiều runner) | Nhiều box person/bib | OCR từng ROI | Multi-tag nhiều BIB |
| Khuất ít (một phần số còn đọc) | Có box | OCR + conf trung bình | `needs_review` nếu conf thấp / partial |
| Khuất nhiều / gập bib | Có/không box | Không đủ số | `no_bib` hoặc review tay |
| Trời tối / flash / ngược sáng | ROI người/bib | OCR trên crop (ít nhiễu đèn nền) | Ưu tiên crop; không OCR full watermark |
| Trời sáng đẹp, bib rõ | Box rõ | Conf cao + ∈ roster | `auto_tagged` |
| Chỉ watermark / biển QC | Không box hợp lệ hoặc filter | Không gắn slogan | `no_bib` |
| Ảnh cực mờ | Blur gate / không box | Skip | `no_bib` |

## Pipeline chuẩn (accuracy-first)

```
Ảnh
 → Dedupe
 → (optional) blur gate toàn ảnh
 → YOLO: person và/hoặc bib plate
 → Với mỗi ROI (ưu tiên vùng ngực / thẻ bib):
      → pad box nhẹ
      → (optional) enhance nhẹ trên crop tối
      → PaddleOCR chỉ trên crop
 → Gộp candidate + filter watermark/signage
 → Roster DB (WebAPI truyền vào)
 → AUTO / REVIEW / NO_BIB
 → Photographer corrections + runner report
```

## Vì sao bắt buộc YOLO (hoặc detector tương đương)

OCR full-frame đọc mọi chữ (logo giải, `QUY NHON`, biển số điện thoại) → sai dù model OCR tốt.  
Detect ROI = điều kiện cần để “chỉ đọc bib trên người/thẻ”.

| Detector | Vai trò |
|---|---|
| YOLO `person` (COCO) | Nhanh có sẵn; crop thân trên → OCR |
| YOLO `bib` (finetune / pretrained race) | Chính xác hơn trên thẻ; mục tiêu phase tiếp |
| Person + Bib 2 tầng | Tốt nhất khi đông + nhiễu nền |

## Roster = lớp bắt buộc thứ hai

OCR đúng format vẫn có thể sai số → phải thuộc danh sách BIB event (WebAPI cung cấp).  
Không có trong roster → không `auto_tagged`.

## Đo chất lượng (trước khi hạ ngưỡng)

Gom sample VN theo bucket: rõ / tối / đông / khuất nhẹ / khuất nặng.  
Báo cáo:

- Precision@AUTO  
- % `needs_review`  
- % `no_bib`  
- Không được tối ưu bằng cách gắn watermark thành BIB  

## Phase triển khai trong service này

| Phase | Việc |
|---|---|
| **P1 (now)** | YOLO person → crop torso → OCR ROI; cấm phụ thuộc full-frame làm mặc định |
| **P2** | YOLO bib plate chuyên biệt; multi-pass crop khi conf thấp |
| **P3** | Calibrate ngưỡng trên dataset giải VN + active learning từ corrections |

## Nguyên tắc vàng

1. Không đọc được rõ → để review / no_bib  
2. Không OCR toàn ảnh khi đã có detector  
3. Đông người = nhiều ROI, không gộp thành 1 số  
4. Độ chính xác “cao nhất có thể” = **pipeline + roster + người**, không chỉ model
