# Note — 2026-10-06 Init service scaffold

## Bối cảnh

Workspace `SEP_Service_Photo` trống. Cần dựng service OCR riêng dựa trên:

- Report 1 / Report 2 (ưu tiên)
- Scenario Fun Run bước 9 (+ admin chỉnh ngưỡng AI)
- FE Admin photographer (upload/ocr/corrections)
- FE User photos (search + report)
- WebAPI hiện **chưa** có module Photo/OCR (chỉ BIB registration) → service này chuẩn bị contract để tích hợp sau

## Việc đã làm

1. Phân tích nghiệp vụ FE-06/FE-07/LI-2, Photographer 3.1–3.5, Risk #4/#5, stack FastAPI+PaddleOCR+Redis+Cloudflare.
2. Research bên ngoài: PaddleOCR confidence, AWS Textract/A2I human loop, ChronoTrack/RaceTagger race OCR, perceptual hash duplicate.
3. Viết rule_design rõ ID + checklist tối ưu.
4. Trả lời kiến trúc: **batch photographer**, không cam check realtime MVP.
5. Scaffold `src/` với API/job/pipeline stub (chưa gắn model thật — bước implement tiếp).

## Việc chưa làm (backlog)

- [ ] Cài PaddleOCR thật + sample ảnh test
- [ ] Worker Redis consume job
- [ ] Callback ký số với WebAPI
- [ ] Endpoint Photo module phía WebAPI
- [ ] Nối FE upload mock → API thật
