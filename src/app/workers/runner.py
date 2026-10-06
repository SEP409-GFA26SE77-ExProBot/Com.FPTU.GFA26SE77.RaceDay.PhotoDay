"""Redis worker stub (deferred).

Production (Report 2 / WebAPI phase):
1. WebAPI enqueue job → Redis
2. Worker BLPOP payload
3. `run_pipeline(...)`
4. Callback `WEBAPI_CALLBACK_BASE`

MVP hiện tại: xử lý đồng bộ trong `POST /v1/ocr/jobs` (+ `/upload`).
Không implement queue ở phase standalone — tránh lệch kiến trúc.
"""

from __future__ import annotations


def main() -> None:
    raise SystemExit(
        "Worker chưa wire. Phase hiện tại dùng inline API "
        "(uvicorn app.main:app). Redis consumer = phase WebAPI."
    )


if __name__ == "__main__":
    main()
