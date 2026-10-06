# 03 — Duplicate Handling

Có **3 loại “trùng”** — không được gộp chung một rule.

| Loại | Ý nghĩa | Xử lý |
|---|---|---|
| **D1 Exact duplicate file** | Cùng bytes / cùng content hash | Reject hoặc link alias, không OCR lại |
| **D2 Near-duplicate ảnh** | Resize/recompress/crop nhẹ cùng khung hình | Flag duplicate group, giữ 1 bản primary |
| **D3 Cùng BIB nhiều ảnh** | Nhiều khoảnh khắc khác nhau | **Không phải duplicate** — giữ tất cả |

---

## Tham chiếu ngoài

| Chủ đề | Nguồn | Link |
|---|---|---|
| dHash + Hamming + BK-tree | Ben Hoyt — Duplicate image detection | https://benhoyt.com/writings/duplicate-image-detection/ |
| pHash khoảng cách điển hình 0–5 / gray zone | Mixpeek perceptual hashing guide | https://mixpeek.com/guides/perceptual-image-hashing-near-duplicate-detection |
| pHash trong photo library | LibrePhotos duplicate detection | https://github.com/LibrePhotos/librephotos/blob/dev/apps/docs/docs/user-guide/duplicate-detection.md |
| Ngưỡng hasher khuyến nghị | Perception (Thorn) deduplication | https://perception.thorn.engineering/examples/deduplication.html |
| So sánh AHash/DHash/PHash vs deep embedding | MDPI Electronics 2026 | https://www.mdpi.com/2079-9292/15/7/1493 |

---

## BR-DUP-01 — Exact duplicate (SHA-256)

| Mục | Quy định |
|---|---|
| **Khi** | Ngay sau upload, trước queue OCR nặng |
| **Hash** | `sha256` toàn file (hoặc của object trên Cloudflare) |
| **Scope** | Trong cùng `event_id` |
| **Nếu trùng** | Status `duplicate`; `duplicate_of = photo_id` gốc; **không** enqueue OCR |
| **Response upload** | HTTP 200 với `deduped: true` (idempotent) — không coi là lỗi cứng |

---

## BR-DUP-02 — Near-duplicate (perceptual hash)

| Mục | Quy định |
|---|---|
| **Khi** | Sau khi có decode ảnh (worker hoặc post-upload nhẹ) |
| **Thuật toán MVP** | `dHash` 64-bit (nhanh) + optional `pHash` xác nhận |
| **So sánh** | Hamming distance trong cùng `event_id` |
| **Ngưỡng mặc định** | `hamming ≤ 5` → near-duplicate (calibrate theo sample; Hoyt dùng ≤2 cho 128-bit dHash rất chặt) |
| **Hành vi** | Gán vào `duplicate_group_id`; giữ ảnh **đầu tiên** làm primary; ảnh sau `duplicate` (có thể vẫn lưu file nhưng không index search) |
| **Gray zone** | `6–10` → không auto-merge; log `possible_near_dup` cho photographer (Should) |

**Lưu ý MDPI:** perceptual hash tốt cho exact/near file; **không** dùng để gộp 2 góc máy khác nhau của cùng runner.

---

## BR-DUP-03 — Upload lại có chủ đích

| Mục | Quy định |
|---|---|
| Photographer force re-upload | Header/flag `force=true` → tạo bản mới, bỏ qua D2 (vẫn chặn D1 exact nếu muốn tiết kiệm storage) |
| Re-OCR primary | Không tạo photo mới |

---

## BR-DUP-04 — Duplicate tag OCR (cùng ảnh)

| Mục | Quy định |
|---|---|
| Cùng `photo_id` + cùng `bib` nhiều candidate | Giữ candidate `confidence` cao nhất |
| Hai BIB khác nhau đủ conf | Multi-tag (hợp lệ) |

---

## BR-DUP-05 — Không nhầm với duplicate scan checkpoint

Report 2 Risk #3 nói **duplicate QR/RFID scan** ở checkpoint — thuộc **timing module WebAPI**, **không** thuộc OCR service.

OCR service chỉ xử lý D1/D2/D4 ảnh.

---

## Luồng tóm tắt

```
Upload
  → SHA-256 hit? → duplicate (stop)
  → Decode → dHash/pHash
  → Hamming ≤ T trong event? → duplicate group (stop OCR)
  → Else → OCR pipeline
```

## Checklist tối ưu duplicate

1. Đo false-positive: 2 ảnh khác góc cùng runner **không** bị merge.
2. Đo false-negative: JPEG quality 95→80 cùng ảnh **phải** bị bắt.
3. Index hash theo `event_id` (không full-table scan toàn hệ thống).
4. Ghi metric `% deduped` trên màn analytics photographer.
