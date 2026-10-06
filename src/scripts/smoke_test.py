"""Smoke: /healthz + upload sample_bib + (optional) VN assets.

Usage (server đang chạy):
  cd src
  .\\.venv\\Scripts\\python.exe scripts\\smoke_test.py

Env:
  OCR_BASE=http://127.0.0.1:8089
  ASSETS_DIR=...   (mặc định Cursor assets nếu có)
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
BASE = os.environ.get("OCR_BASE", "http://127.0.0.1:8089").rstrip("/")
DEFAULT_ASSETS = Path(r"C:\Users\ASUS\.cursor\projects\d-SEP-SEP-Service-Photo\assets")
ASSETS = Path(os.environ.get("ASSETS_DIR", str(DEFAULT_ASSETS)))

# Marker trong tên file Cursor → 1 ảnh đại diện / scene
_VN_MARKERS = ("01_14", "01_36", "01_40", "01_68", "01_69")


def _pick_vn_photos() -> list[Path]:
    if not ASSETS.is_dir():
        return []
    chosen: list[Path] = []
    for marker in _VN_MARKERS:
        matches = sorted(ASSETS.glob(f"*{marker}*.jpg"), key=lambda p: p.stat().st_mtime, reverse=True)
        if matches:
            chosen.append(matches[0])
    return chosen


def _upload(client: httpx.Client, path: Path, *, event_id: str, force: bool = True) -> dict:
    with path.open("rb") as fh:
        r = client.post(
            f"{BASE}/v1/ocr/jobs/upload",
            data={
                "event_id": event_id,
                "roster_bibs": "[]",
                "skip_blur_gate": "false",
                "force": "true" if force else "false",
            },
            files={"file": (path.name, fh, "image/jpeg")},
        )
    r.raise_for_status()
    return r.json().get("result", r.json())


def main() -> int:
    print(f"BASE={BASE}")
    with httpx.Client(timeout=180.0) as client:
        hz = client.get(f"{BASE}/healthz")
        hz.raise_for_status()
        health = hz.json()
        print("healthz:", health.get("status"), "engine=", health.get("engine"), "yolo=", health.get("yolo_enabled"))

        sample = ROOT / "sample_bib.jpg"
        if sample.exists():
            res = _upload(client, sample, event_id="smoke-sample")
            print(
                "sample_bib =>",
                res.get("status"),
                [t["bib"] for t in res.get("tags", [])],
                f"{res.get('latency_ms')}ms",
                "persons=",
                (res.get("engine") or {}).get("yolo", {}).get("person_count"),
            )
        else:
            print("sample_bib.jpg missing — skip")

        vn = _pick_vn_photos()
        if not vn:
            print("No VN assets found — skip batch")
            return 0

        print(f"VN photos ({len(vn)} unique scenes):")
        for path in vn:
            short = re.search(r"(01_\d+)", path.name)
            label = short.group(1) if short else path.name[-40:]
            res = _upload(client, path, event_id="smoke-vn")
            yolo = (res.get("engine") or {}).get("yolo") or {}
            print(
                f"  {label} =>",
                res.get("status"),
                [t["bib"] for t in res.get("tags", [])],
                f"conf={[round(t['confidence'], 3) for t in res.get('tags', [])]}",
                f"{res.get('latency_ms')}ms",
                f"persons={yolo.get('person_count')}",
                f"flags={res.get('preprocess_flags')}",
            )
    return 0


if __name__ == "__main__":
    sys.exit(main())
