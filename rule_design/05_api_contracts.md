# 05 — API Contracts (OCR Service ↔ WebAPI)

> **Phase Now:** dùng các endpoint OCR service đứng riêng (`/v1/ocr/jobs`, `/upload`).  
> Phần callback / roster từ WebAPI bên dưới = **deferred** — giữ spec, chưa implement phía main API.

Hợp đồng tối thiểu khi tích hợp sau. WebAPI sẽ là nguồn sự thật cho photo ownership; OCR service là worker chuyên dụng.

Base URL ví dụ: `http://ocr-service:8089`

Auth đề xuất: service-to-service token (`X-Service-Key`) — không dùng JWT runner trực tiếp.

---

## 1. WebAPI → OCR: tạo job

`POST /v1/ocr/jobs`

```json
{
  "job_id": "uuid",
  "event_id": "uuid",
  "photo_id": "uuid",
  "image_url": "https://.../photo.jpg",
  "content_sha256": "optional-if-known",
  "bib_roster_version": "2026-10-06T10:00:00Z",
  "options": {
    "threshold_auto": 0.95,
    "threshold_review_min": 0.70,
    "force": false
  }
}
```

Response `202`:

```json
{ "job_id": "uuid", "status": "queued" }
```

---

## 2. OCR → WebAPI: callback kết quả

`POST /internal/photos/{photo_id}/ocr-result` (WebAPI)

```json
{
  "job_id": "uuid",
  "status": "auto_tagged | needs_review | no_bib | duplicate | failed",
  "duplicate_of": null,
  "tags": [
    {
      "bib": "A0042",
      "confidence": 0.982,
      "bbox": [x1, y1, x2, y2],
      "source": "paddleocr"
    }
  ],
  "reasons": ["low_confidence"],
  "preprocess_flags": ["clahe", "orient"],
  "engine": { "name": "paddleocr", "version": "x.y" },
  "latency_ms": 840
}
```

---

## 3. Roster snapshot

`GET /internal/events/{event_id}/bibs` (WebAPI → OCR cache)

```json
{
  "event_id": "uuid",
  "version": "etag-or-timestamp",
  "bibs": ["A0042", "B0117", "1234"]
}
```

OCR cache theo `version`; hết hạn hoặc mismatch → pull lại.

---

## 4. Admin threshold

`PUT /v1/events/{event_id}/ocr-config`

```json
{
  "threshold_auto": 0.93,
  "threshold_review_min": 0.65,
  "near_dup_hamming_max": 5
}
```

---

## 5. Reprocess

`POST /v1/ocr/jobs/{job_id}/reprocess`  
hoặc `POST /v1/ocr/photos/{photo_id}/reprocess`

Chỉ áp dụng theo BR-OCR-REPROCESS.

---

## 6. Health

`GET /healthz` → `{ "status": "ok", "model_loaded": true }`

---

## Quy ước lỗi

| Code | Khi |
|---|---|
| 400 | Payload thiếu `event_id` / `image_url` |
| 409 | Exact duplicate và `force=false` (optional; có thể 200 deduped) |
| 422 | Ảnh không decode được |
| 502 | Model inference crash — job `failed`, cho retry |
