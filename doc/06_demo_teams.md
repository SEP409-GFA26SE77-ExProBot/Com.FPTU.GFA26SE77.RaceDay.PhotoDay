# Demo OCR trên Microsoft Teams (share màn hình)

## Cách nhanh nhất

1. Chạy service local (xem bên dưới).
2. Mở trình duyệt: **http://127.0.0.1:8089/demo**
3. Teams → **Share** → **Screen** hoặc cửa sổ Chrome/Edge đang mở trang demo.
4. Upload ảnh → bấm **Chạy OCR** → chỉ vào `status` + `confidence` + JSON.

> **Quan trọng:** Để đọc ảnh giải VN thật, `.env` phải có `OCR_MOCK=0` và pill trên `/demo` hiện **PaddleOCR thật**.  
> `OCR_MOCK=1` luôn trả `A0042` giả — đó là lý do test ảnh VN trước đó ra sai.

## Chạy service

```powershell
cd d:\SEP\SEP_Service_Photo\src
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env   # nếu chưa có .env
uvicorn app.main:app --reload --host 127.0.0.1 --port 8089
```

Mở:

- Demo UI: http://127.0.0.1:8089/demo  
- Swagger (backup): http://127.0.0.1:8089/docs  
- Health: http://127.0.0.1:8089/healthz  

## Script gợi ý 60–90 giây trên Teams

1. Mở `/demo` — nói đây là **OCR service riêng** (chưa gắn WebAPI).  
2. Chỉ health pill **service OK** + **PaddleOCR thật** (`OCR_MOCK=0`).  
3. Upload 1 ảnh runner VN rõ BIB → **Chạy OCR** → `auto_tagged` / `needs_review` + tags.  
4. Upload **cùng file lần 2** (bỏ Force) → `duplicate` (dedupe).  
5. (Optional) Ảnh mờ / chỉ watermark → `no_bib`.  
6. Chi tiết thuyết trình code: xem `doc/07_huong_dan_demo_thuyet_trinh.md`.

## Lưu ý Teams

- Share **cửa sổ browser** hoặc **màn hình** — không share chỉ Teams window.  
- Zoom browser ~110–125% cho chữ rõ.  
- Nếu máy khác cần xem live URL: dùng cùng Wi‑Fi + `http://<IP-máy-bạn>:8089/demo` (firewall cho phép port 8089).  
- Không cần VPN/cloud cho demo local.
