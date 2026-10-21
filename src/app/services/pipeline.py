"""
Orchestrator (1 ảnh = 1 job):

  decode → dedupe → preprocess → [blur gate]
  → YOLO person + multi-band ROI → OCR mỗi crop
  → classify (filter watermark + confidence + roster)
"""

from __future__ import annotations

import io
import time

import httpx
from PIL import Image

from app.core.concurrency import get_inflight_semaphore
from app.core.config import Settings
from app.core.status import OcrJobStatus
from app.schemas.jobs import BibTag, CreateOcrJobRequest, OcrJobResult
from app.services.confidence import classify
from app.services.dedupe import check_and_register
from app.services.detector import PersonDetector, offset_candidates_bbox
from app.services.ocr_engine import OcrCandidate, OcrEngine
from app.services.preprocess import preprocess
from app.services.quality import assess_blur

_engine: OcrEngine | None = None
_detector: PersonDetector | None = None


def get_engine() -> OcrEngine:
    global _engine
    if _engine is None:
        _engine = OcrEngine()
    return _engine


def get_detector() -> PersonDetector:
    global _detector
    if _detector is None:
        _detector = PersonDetector()
    return _detector


async def fetch_image(url: str) -> bytes:
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        return resp.content


async def run_pipeline(
    req: CreateOcrJobRequest,
    settings: Settings,
    *,
    image_bytes: bytes | None = None,
) -> OcrJobResult:
    async with get_inflight_semaphore():
        return await _run(req, settings, image_bytes=image_bytes)


async def _run(
    req: CreateOcrJobRequest,
    settings: Settings,
    *,
    image_bytes: bytes | None,
) -> OcrJobResult:
    t0 = time.perf_counter()
    thr_auto = req.options.threshold_auto or settings.threshold_auto
    thr_review = req.options.threshold_review_min or settings.threshold_review_min
    flags: list[str] = []

    try:
        data = image_bytes if image_bytes is not None else await _load_bytes(req)
        image = Image.open(io.BytesIO(data))
        image.load()
    except Exception as exc:
        return _result(req, OcrJobStatus.failed, t0, reasons=[f"decode_or_fetch_error:{type(exc).__name__}"])

    dedupe = check_and_register(
        req.event_id,
        req.photo_id,
        data,
        image,
        near_dup_hamming_max=settings.near_dup_hamming_max,
        force=req.options.force,
    )
    if dedupe.is_duplicate:
        return _result(
            req,
            OcrJobStatus.duplicate,
            t0,
            duplicate_of=dedupe.duplicate_of,
            reasons=[f"duplicate_{dedupe.kind}"],
            engine={"name": get_engine().name, "sha256": dedupe.content_sha256},
        )

    pre = preprocess(image, max_side=settings.max_image_side)
    flags.extend(pre.flags)
    blur_var = None
    if not req.options.skip_blur_gate:
        q = assess_blur(pre.image, blur_min_variance=settings.blur_min_variance)
        blur_var = q.blur_variance
        if not q.ok_for_ocr:
            return _result(
                req,
                OcrJobStatus.no_bib,
                t0,
                reasons=[q.reason or "blur_too_low"],
                preprocess_flags=flags + ["blur_gate_reject"],
                engine={"name": get_engine().name, "sha256": dedupe.content_sha256},
                blur_variance=blur_var,
            )

    candidates, yolo_meta = _ocr_on_rois(pre.image, settings)
    flags.extend(yolo_meta.get("flags", []))

    # Keep roster strings as WebAPI issued them (prefix+D4); classify resolves OCR → roster.
    roster = {(b or "").strip().upper() for b in req.roster_bibs if b and str(b).strip()}
    classified = classify(
        candidates,
        roster,
        threshold_auto=thr_auto,
        threshold_review_min=thr_review,
        image_size=pre.image.size,
    )
    if yolo_meta.get("person_count", 0) == 0 and not candidates:
        if "no_person_roi" not in classified.reasons:
            classified.reasons.append("no_person_roi")

    tags = [
        BibTag(bib=b, confidence=c, bbox=box, source=get_engine().name)
        for b, c, box in classified.tags
    ]
    return _result(
        req,
        classified.status,
        t0,
        tags=tags,
        reasons=classified.reasons,
        preprocess_flags=flags,
        engine={
            "name": get_engine().name,
            "version": "0.3.0",
            "sha256": dedupe.content_sha256,
            "dhash": dedupe.dhash_hex,
            "yolo": yolo_meta,
        },
        blur_variance=blur_var,
        raw_ocr=classified.raw_texts,
    )


async def _load_bytes(req: CreateOcrJobRequest) -> bytes:
    if req.image_url is None:
        raise ValueError("image_url_or_bytes_required")
    return await fetch_image(str(req.image_url))


def _ocr_on_rois(image: Image.Image, settings: Settings) -> tuple[list[OcrCandidate], dict]:
    detector = get_detector()
    engine = get_engine()
    meta: dict = {"yolo_enabled": detector.enabled, "person_count": 0, "roi_count": 0, "flags": []}

    if detector.enabled:
        detected = detector.detect(image)
        meta["person_count"] = detected.person_count
        meta["roi_count"] = len(detected.rois)
        meta["flags"].append(f"yolo_persons_{detected.person_count}")
        meta["flags"].append(f"yolo_rois_{len(detected.rois)}")

        all_cands: list[OcrCandidate] = []
        for i, roi in enumerate(detected.rois):
            crop = roi.crop
            if max(crop.size) < 320:
                s = 320 / float(max(crop.size))
                crop = crop.resize(
                    (max(1, int(crop.size[0] * s)), max(1, int(crop.size[1] * s))),
                    Image.Resampling.LANCZOS,
                )
            cands = engine.recognize(crop)
            offset_candidates_bbox(cands, roi.bbox)
            for c in cands:
                c.confidence = min(1.0, c.confidence + 0.02)
            all_cands.extend(cands)
            meta[f"roi_{i}"] = {
                "band": roi.band,
                "person_index": roi.person_index,
                "bbox": roi.bbox,
                "det_conf": round(roi.confidence, 3),
            }

        if all_cands:
            meta["flags"].append("ocr_on_person_roi")
            return all_cands, meta

        meta["flags"].append("yolo_no_ocr_text_in_roi")
        if not settings.ocr_fullframe_fallback:
            meta["flags"].append("skip_fullframe_ocr")
            return [], meta

    if settings.ocr_fullframe_fallback or not detector.enabled:
        meta["flags"].append("ocr_fullframe_fallback" if detector.enabled else "ocr_fullframe_no_yolo")
        return engine.recognize(image), meta
    return [], meta


def _result(
    req: CreateOcrJobRequest,
    status: OcrJobStatus,
    t0: float,
    *,
    tags: list[BibTag] | None = None,
    reasons: list[str] | None = None,
    preprocess_flags: list[str] | None = None,
    engine: dict | None = None,
    duplicate_of: str | None = None,
    blur_variance: float | None = None,
    raw_ocr: list | None = None,
) -> OcrJobResult:
    return OcrJobResult(
        job_id=req.job_id,
        photo_id=req.photo_id,
        event_id=req.event_id,
        status=status,
        duplicate_of=duplicate_of,
        tags=tags or [],
        reasons=reasons or [],
        preprocess_flags=preprocess_flags or [],
        engine=engine or {},
        latency_ms=int((time.perf_counter() - t0) * 1000),
        blur_variance=blur_variance,
        raw_ocr=raw_ocr or [],
    )
