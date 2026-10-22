"""
Resolve inference device with safe CPU fallback.

OCR_DEVICE / YOLO_DEVICE:
  auto  — use CUDA if torch/paddle reports GPU ready, else CPU (default; VPS-safe)
  cpu   — force CPU
  cuda  — prefer GPU; if unavailable or init fails → CPU + warning (never crash)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from functools import lru_cache

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DeviceInfo:
    requested: str  # auto | cpu | cuda
    resolved: str  # cpu | cuda
    cuda_available: bool
    detail: str


def _normalize_pref(raw: str | None) -> str:
    v = (raw or "auto").strip().lower()
    if v in {"gpu", "cuda:0", "0"}:
        return "cuda"
    if v in {"auto", "cpu", "cuda"}:
        return v
    logger.warning("Unknown device pref %r — using auto", raw)
    return "auto"


def probe_torch_cuda() -> tuple[bool, str]:
    try:
        import torch

        ok = bool(torch.cuda.is_available())
        if not ok:
            return False, "torch_cuda_unavailable"
        name = torch.cuda.get_device_name(0)
        return True, f"torch:{name}"
    except Exception as exc:  # pragma: no cover
        return False, f"torch_probe_error:{type(exc).__name__}"


def probe_paddle_cuda() -> tuple[bool, str]:
    try:
        import paddle

        compiled = bool(getattr(paddle, "is_compiled_with_cuda", lambda: False)())
        if not compiled:
            return False, "paddle_cpu_wheel"
        # Some builds compile with CUDA but no driver / no device.
        try:
            n = int(paddle.device.cuda.device_count())
        except Exception:
            n = 0
        if n <= 0:
            return False, "paddle_cuda_no_device"
        return True, f"paddle_cuda_devices:{n}"
    except Exception as exc:  # pragma: no cover
        return False, f"paddle_probe_error:{type(exc).__name__}"


@lru_cache
def resolve_device(preference: str = "auto") -> DeviceInfo:
    """
    Pick cpu|cuda once per process. Prefer torch probe (YOLO); paddle may be CPU-only
    even when torch has CUDA — callers must still try/except and fall back.
    """
    pref = _normalize_pref(preference)
    torch_ok, torch_detail = probe_torch_cuda()
    paddle_ok, paddle_detail = probe_paddle_cuda()
    cuda_available = torch_ok or paddle_ok
    detail = f"{torch_detail};{paddle_detail}"

    if pref == "cpu":
        return DeviceInfo(pref, "cpu", cuda_available, detail)

    if pref == "cuda":
        if cuda_available:
            return DeviceInfo(pref, "cuda", True, detail)
        logger.warning(
            "OCR_DEVICE=cuda but no usable GPU (%s) — falling back to CPU",
            detail,
        )
        return DeviceInfo(pref, "cpu", False, detail)

    # auto
    if cuda_available:
        logger.info("Device auto → cuda (%s)", detail)
        return DeviceInfo(pref, "cuda", True, detail)
    logger.info("Device auto → cpu (%s)", detail)
    return DeviceInfo(pref, "cpu", False, detail)


def clear_device_cache() -> None:
    resolve_device.cache_clear()
