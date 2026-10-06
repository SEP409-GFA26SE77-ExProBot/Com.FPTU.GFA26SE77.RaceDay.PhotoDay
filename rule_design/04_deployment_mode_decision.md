# 04 — Quyết định triển khai: Batch photographer vs Camera realtime

## Câu hỏi

> OCR nên chạy sau khi photographer submit hết ảnh, hay tích hợp vào camera/check tại giải chạy?

## Kết luận (bắt buộc cho MVP / SEP)

**Chọn Mode A — Photographer bulk-upload (hoặc upload theo đợt trong/sau giải) → OCR async.**

**Không chọn Mode B — OCR gắn camera check-in / timing gate realtime** cho phạm vi hiện tại.

---

## Đối chiếu nguồn nội bộ

| Nguồn | Nói gì | Hệ quả |
|---|---|---|
| Report 1 FE-06 | “photographers **bulk-upload** race photos… OCR detect and tag” | Upload rồi mới OCR |
| Report 1 LI-2 | Ảnh kém → **manual correction** | Cần UI review, không phải cổng realtime |
| Report 1 LI-4 | Photographer **web only** | Không app cam volunteer cho OCR |
| Report 2 §3.1–3.3 | Bulk upload → Automatic OCR → Review mismatches | Pipeline 3 bước rõ |
| Report 2 Risk #4 | Background job + confidence + review | Async bắt buộc |
| Report 2 Risk #5 | Search < 2s; OCR async không block search | Tách OCR khỏi UX tìm ảnh |
| Scenario bước 9 | Photographer bulk-upload → OCR → Photo Finder | Khớp Mode A |
| FE Admin | Upload queue “processing/tagged”; OCR + Corrections pages | Đã mock Mode A |
| FE User | Search sau khi có tag | Không cần ảnh “live” lúc check-in |

---

## So sánh 2 mode

| Tiêu chí | Mode A — Batch / đợt upload | Mode B — Cam check / finish-line realtime |
|---|---|---|
| Khớp doc SEP | Có | Không (ngoài scope) |
| Độ phức tạp | Queue + worker + review | Edge device, mạng race-day, sync timing, SLA cứng |
| Ảnh mờ/khuất | Đủ thời gian preprocess + human review | Áp lực realtime → dễ gắn sai |
| Duplicate file | Hash lúc ingest | Burst burst từ cam → cần buffer mạnh |
| Trải nghiệm runner | Ảnh sẵn sau giải / vài giờ | Near-instant (đắt, khó) |
| Rủi ro đồ án | Kiểm soát được (Report 2 đã liệt kê) | Effort underestimation (Risk #1) |
| Thị trường tham chiếu | ChronoTrack On-Demand OCR trên ảnh đã upload; RaceTagger batch folder | MarathonFoto quy mô lớn + RFID/ops riêng — không phải MVP community fun-run |

Tham chiếu:

- ChronoTrack OCR trên photos đã upload: https://director.chronotrack.com/hc/en-us/articles/360038745651-How-to-Use-the-On-Demand-OCR-Bib-Tagging-Service-in-CT-Live
- RaceTagger batch workflow: https://racetagger.cloud/guides/sport-workflow-guide/how-to-tag-marathon-photos-with-ai
- MarathonFoto (ops lớn, RFID match — tham khảo ý tưởng, không copy scope): https://www.marathonfoto.com/Home/AboutUs

---

## Mode A chi tiết (áp dụng)

### A1 — Sau giải (khuyến nghị mặc định demo)

1. Photographer chụp offline / máy ảnh.
2. Về / có mạng → bulk upload web.
3. OCR queue xử lý.
4. Review mismatch.
5. Runner mở Photo Finder.

### A2 — Upload theo đợt trong ngày giải (nâng cấp nhẹ, vẫn Mode A)

- Photographer upload từng batch từ laptop/phone khi có Wi‑Fi.
- OCR chạy dần → runner có ảnh sớm hơn.
- **Vẫn không** gắn vào thiết bị check-in/RFID.

### Không làm trong OCR service

- Không thay thế QR check-in.
- Không dùng ảnh cam cổng để tính giờ.
- Không face-ID bắt buộc (ngoài FE-06).

---

## Khi nào cân nhắc Mode B (tương lai, ngoài SEP hiện tại)

Chỉ khi có **cả 3** điều kiện:

1. Hạ tầng cam + mạng race-day ổn định.
2. SLA “ảnh có trong X phút sau finish” là Must từ khách hàng.
3. Đội ngũ riêng cho edge ingest + matching timing.

Khi đó vẫn giữ OCR assistive + review; realtime chỉ là **ingest nhanh hơn**, không bỏ human-in-the-loop.

---

## Rule triển khai

| ID | Rule |
|---|---|
| BR-DEP-01 | MVP chỉ expose API ingest async + worker OCR |
| BR-DEP-02 | Mọi ảnh vào hệ thống qua photographer upload (WebAPI → storage → OCR) |
| BR-DEP-03 | Cấm dependency “camera checkpoint phải online mới có ảnh” |
| BR-DEP-04 | Cho phép A2 (upload đợt) không đổi contract API |
