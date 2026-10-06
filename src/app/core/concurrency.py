"""Limit parallel OCR jobs to protect RAM/VRAM."""

from __future__ import annotations

import asyncio

from app.core.config import get_settings

_sem: asyncio.Semaphore | None = None


def get_inflight_semaphore() -> asyncio.Semaphore:
    global _sem
    if _sem is None:
        _sem = asyncio.Semaphore(max(1, get_settings().max_inflight))
    return _sem
