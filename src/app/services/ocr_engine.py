"""PaddleOCR wrapper (fast mobile models). Mock only when OCR_MOCK=1."""

from __future__ import annotations

import logging
import os
import threading
from dataclasses import dataclass

import numpy as np
from PIL import Image

from app.core.config import get_settings
from app.core.device import resolve_device

# Avoid oneDNN PIR crash on some Windows CPU builds.
os.environ.setdefault("FLAGS_use_mkldnn", "0")
os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")

logger = logging.getLogger(__name__)
# Paddle predict không thread-safe; lock riêng — YOLO (CUDA) vẫn chạy song song được.
_paddle_lock = threading.Lock()


@dataclass
class OcrCandidate:
    bib_raw: str
    confidence: float
    bbox: list[float]


def _build_paddle(device: str, settings):
    """Create PaddleOCR on device; raise if that device cannot init."""
    from paddleocr import PaddleOCR  # type: ignore

    kwargs = dict(
        enable_mkldnn=False,
        use_doc_orientation_classify=False,
        use_doc_unwarping=False,
        use_textline_orientation=False,
        text_detection_model_name=settings.ocr_det_model,
        text_recognition_model_name=settings.ocr_rec_model,
        text_det_limit_side_len=settings.ocr_det_limit_side_len,
        text_det_limit_type="max",
    )
    # PaddleOCR 3.x: device="cpu" | "gpu:0". Older builds may ignore unknown kwargs.
    paddle_device = "gpu:0" if device == "cuda" else "cpu"
    try:
        return PaddleOCR(device=paddle_device, **kwargs)
    except TypeError:
        # Older API: use_gpu bool
        return PaddleOCR(use_gpu=(device == "cuda"), **kwargs)


class OcrEngine:
    def __init__(self) -> None:
        self._paddle = None
        self._device = "cpu"
        self._device_detail = ""
        settings = get_settings()
        if settings.ocr_mock:
            return

        info = resolve_device(settings.ocr_device)
        self._device_detail = info.detail
        # CPU wheel chấp nhận device=gpu:0 lúc init rồi crash 500 lúc infer —
        # bắt buộc CPU khi detail báo paddle_cpu_wheel.
        wanted = info.resolved
        if "paddle_cpu_wheel" in (info.detail or ""):
            if wanted == "cuda":
                logger.warning(
                    "Paddle is CPU wheel — forcing PaddleOCR device=cpu (YOLO may still use CUDA)"
                )
            wanted = "cpu"

        try:
            self._paddle = _build_paddle(wanted, settings)
            self._device = wanted
            logger.info(
                "PaddleOCR loaded device=%s (requested=%s, %s)",
                self._device,
                info.requested,
                info.detail,
            )
        except Exception as exc:
            if wanted != "cpu":
                logger.warning(
                    "PaddleOCR on %s failed (%s) — falling back to CPU",
                    wanted,
                    exc,
                )
                try:
                    self._paddle = _build_paddle("cpu", settings)
                    self._device = "cpu"
                    logger.info("PaddleOCR loaded device=cpu (fallback)")
                except Exception as exc2:
                    raise RuntimeError(
                        "PaddleOCR unavailable. Install paddleocr/paddlepaddle or set OCR_MOCK=1"
                    ) from exc2
            else:
                raise RuntimeError(
                    "PaddleOCR unavailable. Install paddleocr/paddlepaddle or set OCR_MOCK=1"
                ) from exc

    @property
    def name(self) -> str:
        return "mock" if self._paddle is None else "paddleocr-mobile"

    @property
    def device(self) -> str:
        return self._device

    @property
    def device_detail(self) -> str:
        return self._device_detail

    def warmup(self) -> None:
        if self._paddle is None:
            return
        tiny = Image.new("RGB", (64, 64), color=(255, 255, 255))
        try:
            self.recognize(tiny)
            logger.info("OCR engine warmed up on %s", self._device)
        except Exception as exc:  # pragma: no cover
            logger.warning("OCR warmup failed: %s", exc)

    def recognize(self, image: Image.Image) -> list[OcrCandidate]:
        if self._paddle is None:
            return [OcrCandidate(bib_raw="A0042", confidence=0.97, bbox=[10, 20, 120, 80])]

        arr = np.asarray(image.convert("RGB"))
        with _paddle_lock:
            results = self._paddle.predict(arr)
        return self._parse_predict(results)

    def _parse_predict(self, results) -> list[OcrCandidate]:
        candidates: list[OcrCandidate] = []
        if not results:
            return candidates

        for item in results:
            texts: list[str] = []
            scores: list[float] = []
            boxes: list = []

            if hasattr(item, "json") and isinstance(item.json, dict):
                res = item.json.get("res", item.json)
                texts = list(res.get("rec_texts") or [])
                scores = [float(x) for x in (res.get("rec_scores") or [])]
                boxes = list(res.get("rec_boxes") or res.get("dt_polys") or [])
            elif isinstance(item, dict):
                texts = list(item.get("rec_texts") or [])
                scores = [float(x) for x in (item.get("rec_scores") or [])]
                boxes = list(item.get("rec_boxes") or [])
            else:
                try:
                    for line in item or []:
                        box, (text, score) = line
                        texts.append(str(text))
                        scores.append(float(score))
                        boxes.append(box)
                except Exception:
                    continue

            for i, text in enumerate(texts):
                score = scores[i] if i < len(scores) else 0.0
                bbox = _normalize_bbox(boxes[i]) if i < len(boxes) else []
                candidates.append(
                    OcrCandidate(
                        bib_raw=str(text).strip().upper(),
                        confidence=float(score),
                        bbox=bbox,
                    )
                )
        return candidates


def _normalize_bbox(box) -> list[float]:
    try:
        arr = np.array(box, dtype=float)
        if arr.ndim == 1 and arr.size >= 4:
            return [float(arr[0]), float(arr[1]), float(arr[2]), float(arr[3])]
        if arr.ndim == 2 and arr.shape[0] >= 4:
            xs = arr[:, 0]
            ys = arr[:, 1]
            return [float(xs.min()), float(ys.min()), float(xs.max()), float(ys.max())]
    except Exception:
        return []
    return []
