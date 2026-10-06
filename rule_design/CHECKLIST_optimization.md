# Checklist tối ưu & dễ hiểu (bắt buộc trước merge)

Dùng checklist này mỗi khi thêm/sửa rule hoặc code OCR.

## A. Rõ ràng / dễ hiểu

- [ ] Rule có ID ổn định (`BR-…`) và một hành vi duy nhất
- [ ] Có bảng Input / Điều kiện / Output / Ai xử lý tiếp
- [ ] Không dùng ngôn ngữ mơ hồ (“cố gắng”, “có thể tốt hơn”) không kèm ngưỡng
- [ ] Enum status khớp `00_overview.md`
- [ ] Đã cập nhật `note/CHANGELOG.md`

## B. Đúng nghiệp vụ SEP

- [ ] Không phá FE-06/FE-07/LI-2
- [ ] OCR vẫn async (không block upload/search)
- [ ] Low confidence → review, không silent auto-tag
- [ ] Photographer mới được sửa nhãn; runner chỉ report
- [ ] Không đưa Mode B cam check vào MVP

## C. Độ tin cậy OCR (ảnh mờ/khuất)

- [ ] Có `confidence` trên mọi candidate
- [ ] Ngưỡng AUTO/REVIEW/DROP tách bạch, config theo event
- [ ] Preprocess có flag log được
- [ ] Không best-guess partial bib
- [ ] Đo Precision@AUTO trên sample trước khi hạ ngưỡng
- [ ] Link tham chiếu ngoài vẫn còn hiệu lực (PaddleOCR / Textract / ChronoTrack)

## D. Duplicate

- [ ] Phân biệt D1 exact / D2 near / D3 cùng BIB nhiều ảnh
- [ ] SHA-256 trước OCR nặng
- [ ] Hamming threshold có số cụ thể + kế hoạch calibrate
- [ ] Test: 2 góc khác nhau không bị merge

## E. Hiệu năng & vận hành

- [ ] Queue + worker (Redis) — khớp Report 2
- [ ] Search BIB không gọi model OCR đồng bộ
- [ ] Timeout + retry có trần
- [ ] Health check model loaded
- [ ] Log `latency_ms`, `auto_rate`, `dedupe_rate`

## F. Tài liệu

- [ ] `doc/` hướng dẫn cập nhật nếu đổi setup/API
- [ ] Ví dụ request/response còn chạy được
- [ ] Quyết định kiến trúc (batch vs cam) không bị mâu thuẫn giữa các file
