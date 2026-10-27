"""
Orchestrator (1 ảnh = 1 job):

  decode → dedupe → preprocess → [blur gate]
  → YOLO person + multi-band ROI → OCR mỗi crop
  → classify (filter watermark + confidence + roster)
"""

from __future__ import annotations

import asyncio
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


_http: httpx.AsyncClient | None = None


def _http_client() -> httpx.AsyncClient:
    global _http
    if _http is None or _http.is_closed:
        _http = httpx.AsyncClient(timeout=60.0)
    return _http


async def fetch_image(url: str) -> bytes:
    resp = await _http_client().get(url)
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
    except Exception as exc:
        return _result(req, OcrJobStatus.failed, t0, reasons=[f"decode_or_fetch_error:{type(exc).__name__}"])

    # CPU-bound (YOLO/Paddle/blur) off event loop — MAX_INFLIGHT mới song song thật.
    return await asyncio.to_thread(
        _run_cpu_bound,
        req,
        settings,
        data,
        t0,
        thr_auto,
        thr_review,
        flags,
    )


def _run_cpu_bound(
    req: CreateOcrJobRequest,
    settings: Settings,
    data: bytes,
    t0: float,
    thr_auto: float,
    thr_review: float,
    flags: list[str],
) -> OcrJobResult:
    try:
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
    flags = list(flags)
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


def _upscale_min_side(crop: Image.Image, min_side: int = 320) -> Image.Image:
    if max(crop.size) >= min_side:
        return crop
    s = min_side / float(max(crop.size))
    return crop.resize(
        (max(1, int(crop.size[0] * s)), max(1, int(crop.size[1] * s))),
        Image.Resampling.LANCZOS,
    )


def _person_full_box(
    person_xyxy: list[float],
    img_w: int,
    img_h: int,
    *,
    pad_ratio: float = 0.06,
) -> list[float]:
    x1, y1, x2, y2 = person_xyxy
    bw, bh = max(1.0, x2 - x1), max(1.0, y2 - y1)
    px, py = bw * pad_ratio, bh * pad_ratio
    return [
        max(0.0, x1 - px),
        max(0.0, y1 - py),
        min(float(img_w), x2 + px),
        min(float(img_h), y2 + py),
    ]


def _ocr_on_rois(image: Image.Image, settings: Settings) -> tuple[list[OcrCandidate], dict]:
    """YOLO person → OCR torso bands. Early-exit band loop per person when bib-like hit (CPU).

    Người bị che một phần: band chest/waist có thể miss BIB dù crop solo đọc được —
    retry 1 lần OCR full-person box (không full-frame cả ảnh).
    """
    from collections import defaultdict

    from app.services.confidence import looks_like_bib

    detector = get_detector()
    engine = get_engine()
    meta: dict = {"yolo_enabled": detector.enabled, "person_count": 0, "roi_count": 0, "flags": []}
    review_floor = float(settings.threshold_review_min)
    img_w, img_h = image.size

    if detector.enabled:
        detected = detector.detect(image)
        meta["person_count"] = detected.person_count
        meta["roi_count"] = len(detected.rois)
        meta["flags"].append(f"yolo_persons_{detected.person_count}")
        meta["flags"].append(f"yolo_rois_{len(detected.rois)}")

        by_person: dict[int, list] = defaultdict(list)
        for roi in detected.rois:
            by_person[roi.person_index].append(roi)

        all_cands: list[OcrCandidate] = []
        roi_i = 0
        early_exits = 0
        person_retries = 0
        for person_index in sorted(by_person.keys()):
            person_cands: list[OcrCandidate] = []
            # Người nhỏ / det yếu / bị che → ROI khó hơn crop solo → hạ conf.
            area_frac = 0.0
            det_conf = 1.0
            if person_index < len(detected.person_boxes):
                bx = detected.person_boxes[person_index]
                area_frac = max(0.0, (bx[2] - bx[0]) * (bx[3] - bx[1])) / max(
                    1.0, float(img_w * img_h)
                )
            if by_person[person_index]:
                det_conf = float(by_person[person_index][0].confidence)
            hard_roi_penalty = 0.0
            if area_frac > 0 and area_frac < 0.04:
                hard_roi_penalty += 0.06
            if det_conf < 0.45:
                hard_roi_penalty += 0.05

            for roi in by_person[person_index]:
                crop = _upscale_min_side(roi.crop)
                cands = engine.recognize(crop)
                offset_candidates_bbox(cands, roi.bbox)
                for c in cands:
                    # Không bump +0.01 (đẩy đuôi về 0.99). Soft-cap + hard-ROI penalty.
                    c.confidence = min(0.95, max(0.0, float(c.confidence) - hard_roi_penalty))
                person_cands.extend(cands)
                all_cands.extend(cands)
                meta[f"roi_{roi_i}"] = {
                    "band": roi.band,
                    "person_index": roi.person_index,
                    "bbox": roi.bbox,
                    "det_conf": round(roi.confidence, 3),
                }
                roi_i += 1
                # Chest hit đủ rõ → bỏ waist/hips cùng người (tiết kiệm ~2× Paddle/person).
                if any(
                    looks_like_bib(c.bib_raw) and float(c.confidence) >= review_floor
                    for c in cands
                ):
                    early_exits += 1
                    break

            has_bib = any(
                looks_like_bib(c.bib_raw) and float(c.confidence) >= review_floor
                for c in person_cands
            )
            if (
                not has_bib
                and getattr(settings, "yolo_person_full_retry", True)
                and person_index < len(detected.person_boxes)
            ):
                box = _person_full_box(
                    detected.person_boxes[person_index],
                    img_w,
                    img_h,
                    pad_ratio=max(0.04, float(settings.yolo_torso_pad)),
                )
                if box[2] - box[0] >= 16 and box[3] - box[1] >= 16:
                    crop = _upscale_min_side(
                        image.crop((int(box[0]), int(box[1]), int(box[2]), int(box[3]))),
                        min_side=400,
                    )
                    cands = engine.recognize(crop)
                    offset_candidates_bbox(cands, box)
                    for c in cands:
                        # person_full = case khó (band miss / che một phần) — hạ conf rõ.
                        c.confidence = min(0.88, float(c.confidence) * 0.90)
                    all_cands.extend(cands)
                    person_retries += 1
                    meta[f"roi_{roi_i}"] = {
                        "band": "person_full",
                        "person_index": person_index,
                        "bbox": box,
                        "det_conf": None,
                    }
                    roi_i += 1

        if early_exits:
            meta["flags"].append(f"roi_band_early_exit_{early_exits}")
            meta["rois_ocr_run"] = roi_i
        if person_retries:
            meta["flags"].append(f"person_full_retry_{person_retries}")

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
