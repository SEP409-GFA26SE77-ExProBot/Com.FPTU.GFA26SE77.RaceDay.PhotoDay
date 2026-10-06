# Research — OCR ảnh mờ / khuất & độ tin cậy

## Kết luận kỹ thuật (áp dụng RaceDay)

1. **Luôn có confidence** trên mỗi lần đọc BIB (`rec_score` PaddleOCR).
2. **Ngưỡng phân tầng**: auto-tag / human review / không đoán.
3. **Preprocess vừa phải** (orient, contrast); blur nặng → đưa review, không cố “bịa” nét.
4. **Validate roster BIB** của event để giảm gắn số ảo.
5. **OCR assistive** — photographer corrections là phần của sản phẩm, không phải “lỗi tạm”.

Cách làm này trùng hướng nền tảng lớn: AWS Textract + A2I (confidence → human loop), ChronoTrack OCR (không tag khi không chắc), RaceTagger (flag folded/covered).

---

## 1) PaddleOCR (engine chọn trong Report 2)

- Output recognition có `rec_score`:  
  https://www.paddleocr.ai/latest/en/version3.x/module_usage/text_recognition.html
- Tham số lọc theo điểm: `text_rec_score_thresh`, các `text_det_*`:  
  https://www.paddleocr.ai/v2.9/en/ppocr/blog/inference_args.html
- PP-OCRv5 train có augment **blurring / rotation / geometric** — phù hợp ảnh field:  
  https://arxiv.org/html/2507.05595
- Tip vận hành: kiểm tra confidence thấp để review; ảnh kém nên đủ độ phân giải:  
  https://github.com/PaddlePaddle/PaddleOCR/blob/1903e73d/skills/paddleocr-text-recognition/SKILL.md

**Áp dụng:** map `rec_score` → band AUTO/REVIEW; Admin chỉnh ngưỡng theo event.

---

## 2) AWS Textract + Amazon A2I (mẫu human-in-the-loop)

- Best practice: dùng confidence; app nhạy sai số → ngưỡng cao (vd 90%+), dưới ngưỡng thì discard hoặc human review:  
  https://docs.aws.amazon.com/textract/latest/dg/textract-best-practices.html
- A2I kích hoạt human loop khi confidence trong khoảng cấu hình:  
  https://docs.aws.amazon.com/sagemaker/latest/dg/a2i-textract-task-type.html
- Blog: UI review khi text mờ/che:  
  https://aws.amazon.com/blogs/machine-learning/automate-digitization-of-transactional-documents-with-human-oversight-using-amazon-textract-and-amazon-a2i/

**Áp dụng:** màn `/photographer/corrections` chính là human loop nội bộ; không cần mua A2I.

---

## 3) Thực tế ngành race photo

- ChronoTrack On-Demand OCR: chạy trên ảnh đã upload; bib phải nhìn rõ; không đọc được thì **để untagged** (không best guess):  
  https://director.chronotrack.com/hc/en-us/articles/360038745651-How-to-Use-the-On-Demand-OCR-Bib-Tagging-Service-in-CT-Live
- RaceTagger: batch folder + start-list; folded/covered/crowded → flag review:  
  https://racetagger.cloud/guides/problem-solution/bib-detection-in-marathon-photography  
  https://racetagger.cloud/guides/sport-workflow-guide/how-to-tag-marathon-photos-with-ai

**Áp dụng:** Mode batch + roster BIB + review queue — đúng FE-06 và Risk #4.

---

## 4) Duplicate ảnh (kèm research)

- dHash + Hamming + cấu trúc tìm kiếm:  
  https://benhoyt.com/writings/duplicate-image-detection/
- Khoảng cách pHash gần / gray zone:  
  https://mixpeek.com/guides/perceptual-image-hashing-near-duplicate-detection
- LibrePhotos pHash duplicates:  
  https://github.com/LibrePhotos/librephotos/blob/dev/apps/docs/docs/user-guide/duplicate-detection.md

Chi tiết rule: `rule_design/03_duplicate_handling.md`.

---

## Ma trận xử lý nhanh (ops)

| Tình huống ảnh | Hệ thống làm gì |
|---|---|
| Rõ, conf ≥ 0.95, BIB ∈ roster | `auto_tagged` |
| Hơi mờ/lệch, 0.70–0.95 | `needs_review` |
| Che khuất một phần số | `needs_review` + `partial_read` — không đoán đủ số |
| Blur nặng / không thấy BIB | `no_bib` |
| File upload trùng | `duplicate` — bỏ OCR |
| Runner báo sai | `runner_reported` → corrections |
