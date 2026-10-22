"""YOLO person detection → multi-band torso ROIs for bib OCR."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import numpy as np
from PIL import Image

from app.core.config import get_settings
from app.core.device import resolve_device

logger = logging.getLogger(__name__)
_PERSON_CLASS_ID = 0  # COCO person


@dataclass
class PersonRoi:
    bbox: list[float]  # full-image xyxy
    confidence: float
    crop: Image.Image
    band: str = "chest"
    person_index: int = 0


@dataclass
class DetectResult:
    rois: list[PersonRoi] = field(default_factory=list)
    person_count: int = 0
    # Full person xyxy (same order as person_index) for per-person retry OCR.
    person_boxes: list[list[float]] = field(default_factory=list)


class PersonDetector:
    def __init__(self) -> None:
        self._model = None
        self._device = "cpu"
        self._device_detail = ""
        settings = get_settings()
        if not settings.yolo_enabled:
            return
        pref = (settings.yolo_device or settings.ocr_device or "auto").strip()
        info = resolve_device(pref)
        self._device = info.resolved
        self._device_detail = info.detail
        try:
            from ultralytics import YOLO  # type: ignore

            self._model = YOLO(settings.yolo_model)
            # Force CPU path if resolved cpu (ultralytics may still prefer CUDA otherwise).
            logger.info(
                "YOLO loaded: %s device=%s (requested=%s, %s)",
                settings.yolo_model,
                self._device,
                info.requested,
                info.detail,
            )
        except Exception as exc:  # pragma: no cover
            logger.warning("YOLO unavailable (%s)", exc)
            self._model = None

    @property
    def enabled(self) -> bool:
        return self._model is not None

    @property
    def device(self) -> str:
        return self._device

    @property
    def device_detail(self) -> str:
        return self._device_detail

    def warmup(self) -> None:
        if self._model is None:
            return
        try:
            self.detect(Image.new("RGB", (64, 64), color=(128, 128, 128)))
            logger.info("YOLO warmed up on %s", self._device)
        except Exception as exc:  # pragma: no cover
            if self._device != "cpu":
                logger.warning("YOLO warmup on %s failed (%s) — retry CPU", self._device, exc)
                self._device = "cpu"
                try:
                    self.detect(Image.new("RGB", (64, 64), color=(128, 128, 128)))
                    logger.info("YOLO warmed up on cpu (fallback)")
                    return
                except Exception as exc2:
                    logger.warning("YOLO warmup failed: %s", exc2)
                    return
            logger.warning("YOLO warmup failed: %s", exc)

    def detect(self, image: Image.Image) -> DetectResult:
        if self._model is None:
            return DetectResult()

        settings = get_settings()
        predict_kw = dict(
            conf=settings.yolo_conf,
            iou=float(getattr(settings, "yolo_iou", 0.88) or 0.88),
            classes=[_PERSON_CLASS_ID],
            device=self._device,
            verbose=False,
        )
        try:
            results = self._model.predict(np.asarray(image.convert("RGB")), **predict_kw)
        except Exception as exc:
            if self._device != "cpu":
                logger.warning("YOLO predict on %s failed (%s) — fallback CPU", self._device, exc)
                self._device = "cpu"
                predict_kw["device"] = "cpu"
                results = self._model.predict(np.asarray(image.convert("RGB")), **predict_kw)
            else:
                raise
        if not results or results[0].boxes is None or len(results[0].boxes) == 0:
            return DetectResult()

        w, h = image.size
        boxes = results[0].boxes.xyxy.cpu().numpy()
        confs = results[0].boxes.conf.cpu().numpy()
        # Prefer larger people, but break ties by det confidence (occluded mid-pack).
        areas = (boxes[:, 2] - boxes[:, 0]) * (boxes[:, 3] - boxes[:, 1])
        order = np.lexsort((-confs, -areas))
        max_people = max(1, settings.yolo_max_people)

        rois: list[PersonRoi] = []
        person_boxes: list[list[float]] = []
        person_count = 0
        for person_index, idx in enumerate(order[:max_people]):
            person_count += 1
            x1, y1, x2, y2 = (float(v) for v in boxes[idx])
            conf = float(confs[idx])
            person_boxes.append(
                [
                    max(0.0, x1),
                    max(0.0, y1),
                    min(float(w), x2),
                    min(float(h), y2),
                ]
            )
            for band, box in _bib_bands(x1, y1, x2, y2, w, h, pad_ratio=settings.yolo_torso_pad):
                crop = image.crop((box[0], box[1], box[2], box[3]))
                if crop.size[0] < 16 or crop.size[1] < 16:
                    continue
                rois.append(
                    PersonRoi(
                        bbox=box,
                        confidence=conf,
                        crop=crop,
                        band=band,
                        person_index=person_index,
                    )
                )
        return DetectResult(rois=rois, person_count=person_count, person_boxes=person_boxes)


def _bib_bands(
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    img_w: int,
    img_h: int,
    *,
    pad_ratio: float,
) -> list[tuple[str, list[float]]]:
    """Chest / waist / hips bands relative to person box (bib may sit on shorts)."""
    bw, bh = x2 - x1, y2 - y1
    specs = (("chest", 0.10, 0.66), ("waist", 0.35, 0.82), ("hips", 0.55, 0.95))
    out: list[tuple[str, list[float]]] = []
    for name, top_r, bot_r in specs:
        ty1, ty2 = y1 + bh * top_r, y1 + bh * bot_r
        tx1, tx2 = x1 + bw * 0.05, x2 - bw * 0.05
        pad_x, pad_y = bw * pad_ratio, bh * pad_ratio
        out.append(
            (
                name,
                [
                    max(0.0, tx1 - pad_x),
                    max(0.0, ty1 - pad_y),
                    min(float(img_w), tx2 + pad_x),
                    min(float(img_h), ty2 + pad_y),
                ],
            )
        )
    return out


def offset_candidates_bbox(candidates: list, roi_bbox: list[float]) -> list:
    ox, oy = roi_bbox[0], roi_bbox[1]
    for c in candidates:
        if c.bbox and len(c.bbox) >= 4:
            c.bbox = [c.bbox[0] + ox, c.bbox[1] + oy, c.bbox[2] + ox, c.bbox[3] + oy]
    return candidates
