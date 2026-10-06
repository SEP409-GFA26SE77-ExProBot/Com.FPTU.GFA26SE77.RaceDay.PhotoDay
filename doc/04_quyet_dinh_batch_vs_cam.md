# Nên áp dụng thế nào? Batch photographer hay cam check realtime?

## Trả lời ngắn

**Nên để photographer submit ảnh (bulk / theo đợt) rồi OCR service xử lý nền — không tích hợp OCR vào camera check-in tại giải cho giai đoạn hiện tại.**

Có thể upload **nhiều đợt trong ngày giải** (khi có mạng) để runner thấy ảnh sớm hơn, nhưng vẫn là cùng mô hình ingest → queue → OCR → review.

---

## Vì sao không gắn cam check / timing?

1. **Doc bắt buộc Mode batch:** Report 1 FE-06, Report 2 mục Photographer 3.1–3.3, scenario bước 9 đều mô tả *bulk-upload rồi OCR*.
2. **OCR không đủ tin cậy realtime:** LI-2 + Risk #4 yêu cầu confidence + sửa tay — cổng check-in không chờ photographer.
3. **Phân tách domain:** Check-in/RFID là tính giờ; Photo Finder là phân phối ảnh. Trộn hai hệ = tăng rủi ro đồ án (Risk #1 effort).
4. **FE đã thiết kế sẵn:** Upload → OCR Recognition → BIB Corrections; User Photos search sau khi có tag.
5. **Thực tế ngành MVP:** ChronoTrack/RaceTagger cũng OCR trên ảnh đã upload/batch; hệ “ảnh xong ngay tại đích” kiểu MarathonFoto là ops + hạ tầng lớn, không phải scope fun-run community.

---

## Cách vận hành đề xuất cho RaceDay

```
[Chụp trên đường chạy]
        │
        ▼
[Photographer upload web — 1 lần sau giải hoặc nhiều batch]
        │
        ▼
[Cloudflare lưu ảnh + WebAPI tạo job]
        │
        ▼
[OCR Service: preprocess → PaddleOCR → confidence → roster check]
        │
        ├─ conf cao → auto tag → Runner tìm thấy ngay
        └─ conf thấp / khuất → Corrections UI
```

### Nên

- Bulk sau giải cho demo ổn định.
- Upload theo đợt nếu muốn “gần realtime” về trải nghiệm runner.
- Giữ màn review + chỉnh ngưỡng Admin.

### Không nên (MVP)

- Gắn model OCR vào app scan QR cổng start.
- Coi cam finish như nguồn timing.
- Bỏ human review vì “AI đủ ngon”.

---

## Lộ trình sau này (optional)

| Phase | Việc |
|---|---|
| Now | Mode A batch + async OCR |
| Next | Upload đợt từ điện thoại photographer (vẫn Mode A) |
| Later (ngoài SEP nếu có resource) | Ingest cam chuyên dụng + matching phụ bằng thời điểm checkpoint — vẫn cần review |

Rule formal: `rule_design/04_deployment_mode_decision.md`.
