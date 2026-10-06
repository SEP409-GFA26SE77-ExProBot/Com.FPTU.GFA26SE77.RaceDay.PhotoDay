"""Cheap image quality gates before OCR. See rule_design/06_perf_memory_stability.md."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from PIL import Image


@dataclass
class QualityDecision:
    ok_for_ocr: bool
    blur_variance: float
    reason: str | None = None


def laplacian_variance(image: Image.Image) -> float:
    gray = np.asarray(image.convert("L"), dtype=np.float32)
    # 3x3 Laplacian kernel without OpenCV dependency.
    kernel = np.array([[0, 1, 0], [1, -4, 1], [0, 1, 0]], dtype=np.float32)
    # pad + convolve via FFT-ish simple sliding; use correlate for small images
    from numpy.lib.stride_tricks import sliding_window_view

    if gray.shape[0] < 3 or gray.shape[1] < 3:
        return 0.0
    windows = sliding_window_view(gray, (3, 3))
    conv = (windows * kernel).sum(axis=(-1, -2))
    return float(conv.var())


def assess_blur(image: Image.Image, *, blur_min_variance: float) -> QualityDecision:
    var = laplacian_variance(image)
    if var < blur_min_variance:
        return QualityDecision(False, var, "blur_too_low")
    return QualityDecision(True, var, None)
