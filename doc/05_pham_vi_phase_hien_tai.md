# Phạm vi phase hiện tại

## Trong scope (làm ngay trong SEP_Service_Photo)

- Rule design OCR / confidence / duplicate / perf
- API tự đứng: tạo job, lấy kết quả, chỉnh ngưỡng event
- Nhận ảnh bằng `image_url` **hoặc upload file multipart** (test không cần WebAPI)
- Pipeline: dedupe → blur gate → preprocess → OCR (mock/Paddle) → classify
- Giới hạn `max_inflight` tránh sập khi burst

## Ngoài scope (để sau — Main WebAPI / FE)

- Module Photo ownership trên WebAPI
- Upload photographer thật → Cloudflare/R2 → gọi OCR
- Callback `ocr-result` về WebAPI
- JWT / RBAC photographer-runner
- Photo Finder search production
- Redis worker production (có thể thêm trong service sau, chưa bắt buộc nối main API)

## Hợp đồng giữ sẵn, chưa nối

`rule_design/05_api_contracts.md` mô tả tương lai WebAPI ↔ OCR.  
Phase này OCR **trả kết quả qua GET job** (và response process), không gọi ngược WebAPI.
