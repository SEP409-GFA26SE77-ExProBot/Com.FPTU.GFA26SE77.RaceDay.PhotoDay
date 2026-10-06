# Nghiệp vụ BIB Photo Finder — tóm tắt cho OCR Service

## Bài toán

Sau giải chạy, photographer có hàng nghìn ảnh chưa gắn BIB. Runner muốn tìm ảnh của mình bằng số BIB thay vì lùng gallery thủ công.

RaceDay giải bằng: **OCR đọc số BIB trên áo** → index → **Photo Finder**.

## Luồng end-to-end (khớp scenario bước 9)

1. Organizer tạo event + dải BIB / wave (ngoài OCR).
2. Runner đăng ký, nhận BIB (ngoài OCR).
3. Race-day check-in / timing (ngoài OCR).
4. **Photographer bulk-upload ảnh** vào event.
5. **OCR service** detect BIB + confidence.
6. Photographer **review** ảnh thấp tin cậy / sai.
7. Runner nhập BIB tại Photo Finder → xem/tải ảnh.
8. Runner có thể **report ảnh sai** → quay lại review.

## Vai trò chạm OCR

| Role | Việc |
|---|---|
| Photographer | Upload, xem OCR, sửa BIB |
| Runner | Search + report mismatch |
| Administrator | Chỉnh ngưỡng AI / bổ sung dữ liệu (theo scenario) |
| Organizer | Gián tiếp (event, roster BIB) |

## Ràng buộc cứng từ Report 1/2

- OCR phụ thuộc chất lượng ảnh → không auto khi không rõ (LI-2).
- Background job + confidence + review (Risk #4).
- Search < 2s; OCR không block search (Risk #5).
- Stack: FastAPI OCR + PaddleOCR + Redis queue + Cloudflare Images.

## Out of scope OCR

- Thanh toán, check-in QR, RFID timing, SOS map, chứng chỉ.
- Face recognition thay BIB (không có trong FE-06).
- Camera gate realtime (xem `04_quyet_dinh_batch_vs_cam.md`).
