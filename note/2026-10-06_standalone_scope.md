# Note — 2026-10-06 Standalone scope

## Quyết định user

Chỉ handle trong `SEP_Service_Photo`. Tích hợp Main WebAPI để sau.

## Thay đổi chính

- Doc phạm vi phase (`doc/05_...`)
- Perf/stability rules + blur gate + max_inflight trong code
- Upload multipart để tự test không cần Cloudflare/WebAPI
- Callback WebAPI / Redis consumer = deferred (giữ spec trong `05_api_contracts.md`)
