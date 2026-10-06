"""Confidence banding + BIB filter for noisy race photos (watermark/signage)."""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.core.status import OcrJobStatus
from app.services.ocr_engine import OcrCandidate

# Only fix digit lookalikes inside mostly-numeric tokens (not whole slogans).
_DIGIT_FIX = str.maketrans({"O": "0", "I": "1", "L": "1", "S": "5", "Z": "2"})

# Event / sponsor noise common on VN marathon photos (local filter, not web).
_BLOCK_SUBSTR = (
    "VNEXPRESS",
    "MARATHON",
    "QUYNHON",
    "QUYNH",
    "HIGHLAND",
    "HIGHLA",
    "EXPRESS",
    "CAMPAGNOLO",
    "BMAI",
)

# Core bib: optional category letter + 4–5 digits + optional gender M/F
# e.g. A80087M, 80087, 8684M, A 80183 F
_BIB_FULL = re.compile(r"^([A-Z])?(\d{4,5})([MF])?$")
_DIGIT_RUN = re.compile(r"\d{4,5}")


@dataclass
class ClassifiedTags:
    status: OcrJobStatus
    tags: list[tuple[str, float, list[float]]]
    reasons: list[str]
    raw_texts: list[dict]


def normalize_alnum(raw: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", raw.upper())


def normalize_bib(raw: str) -> str:
    """Public helper used by roster normalize."""
    return normalize_alnum(raw)


def _is_blocklisted(norm: str) -> bool:
    if not norm:
        return True
    if any(b in norm for b in _BLOCK_SUBSTR):
        return True
    # Pure letters / tiny tokens (AB, OU, ON, NHON…)
    if norm.isalpha() and len(norm) <= 8:
        return True
    # Year fragments often glued from watermark "20""26"
    if norm in {"2024", "2025", "2026", "2027", "2028", "2029", "2020", "2021", "2022", "2023"}:
        return True
    return False


def _in_watermark_zone(bbox: list[float], image_size: tuple[int, int] | None) -> bool:
    """VnExpress overlay sits top-left; ignore that band."""
    if not bbox or len(bbox) < 4 or not image_size:
        return False
    w, h = image_size
    if w <= 0 or h <= 0:
        return False
    x1, y1, x2, y2 = bbox[:4]
    cx = (x1 + x2) / 2.0
    cy = (y1 + y2) / 2.0
    # Top strip (watermark) or extreme top-left badge
    if cy < h * 0.14:
        return True
    if cx < w * 0.22 and cy < h * 0.22:
        return True
    return False


def _torso_bonus(bbox: list[float], image_size: tuple[int, int] | None) -> float:
    if not bbox or len(bbox) < 4 or not image_size:
        return 0.0
    w, h = image_size
    x1, y1, x2, y2 = bbox[:4]
    cx = (x1 + x2) / 2.0 / max(w, 1)
    cy = (y1 + y2) / 2.0 / max(h, 1)
    bonus = 0.0
    # Bib usually mid torso, horizontally centered-ish
    if 0.30 <= cy <= 0.78:
        bonus += 0.06
    if 0.25 <= cx <= 0.75:
        bonus += 0.03
    # Prefer reasonably large boxes (bib plate vs tiny noise)
    box_h = abs(y2 - y1) / max(h, 1)
    if box_h >= 0.03:
        bonus += 0.02
    return bonus


def extract_bib_candidates(raw: str) -> list[str]:
    """
    Extract plausible bib IDs from one OCR token.
    Returns digit-core first (80087); keeps prefixed form if category letter present.
    """
    norm = normalize_alnum(raw)
    if _is_blocklisted(norm):
        return []

    # Avoid pulling ON2026 out of QUYNHON2026 — only accept whole-token bib shape
    # or digit runs that are not embedded in long letter soup.
    letter_count = sum(ch.isalpha() for ch in norm)
    digit_count = sum(ch.isdigit() for ch in norm)
    if letter_count >= 4 and digit_count <= 4:
        # Slogan + year fragment
        return []

    out: list[str] = []

    # Apply digit fixes only on digit-heavy tokens
    if digit_count >= letter_count:
        fixed = norm.translate(_DIGIT_FIX)
    else:
        fixed = norm

    m = _BIB_FULL.match(fixed)
    if m:
        prefix, digits, _gender = m.group(1), m.group(2), m.group(3)
        if _reject_digit_core(digits):
            return []
        out.append(digits)
        if prefix:
            out.append(f"{prefix}{digits}")
        return out

    # Embedded digit run only if token is short overall
    if len(fixed) <= 10:
        for dig in _DIGIT_RUN.findall(fixed):
            if _reject_digit_core(dig):
                continue
            if dig not in out:
                out.append(dig)
    return out


def _reject_digit_core(digits: str) -> bool:
    """Drop phone/year-like cores common on VN event photos."""
    if not digits:
        return True
    # Phone fragments
    if digits.startswith("0"):
        return True
    # Watermark years 2024–2029 and OCR gluing "20"+"26"
    if digits.startswith("20") and len(digits) in {4, 5, 6}:
        return True
    return False


def looks_like_bib(text: str) -> bool:
    return bool(_BIB_FULL.match(normalize_alnum(text).translate(_DIGIT_FIX)))


def classify(
    candidates: list[OcrCandidate],
    roster: set[str],
    *,
    threshold_auto: float,
    threshold_review_min: float,
    image_size: tuple[int, int] | None = None,
) -> ClassifiedTags:
    reasons: list[str] = []
    raw_texts = [
        {"text": c.bib_raw, "confidence": round(c.confidence, 4), "bbox": c.bbox}
        for c in candidates
    ]

    if not candidates:
        return ClassifiedTags(OcrJobStatus.no_bib, [], ["no_candidate"], raw_texts)

    prepared: list[tuple[str, float, list[float], float]] = []
    skipped_wm = 0
    skipped_block = 0

    for c in candidates:
        norm = normalize_alnum(c.bib_raw)
        if _in_watermark_zone(c.bbox, image_size):
            skipped_wm += 1
            continue
        if _is_blocklisted(norm):
            skipped_block += 1
            continue

        bibs = extract_bib_candidates(c.bib_raw)
        if not bibs:
            continue

        conf = float(c.confidence) + _torso_bonus(c.bbox, image_size)
        if looks_like_bib(c.bib_raw):
            conf = min(1.0, conf + 0.03)
        conf = min(1.0, conf)

        for bib in bibs:
            # Prefer digit-only core when ranking; keep prefixed variants too.
            prepared.append((bib, conf, c.bbox, conf + (0.01 if bib.isdigit() else 0.0)))

    if skipped_wm:
        reasons.append("ignored_watermark_zone")
    if skipped_block:
        reasons.append("ignored_event_signage")

    if not prepared:
        # Do NOT fall back to AB / QUYNHON fragments — better no_bib + manual review.
        reasons.append("no_bib_like_token")
        return ClassifiedTags(OcrJobStatus.no_bib, [], reasons, raw_texts)

    # Keep best score per bib string
    best: dict[str, tuple[str, float, list[float]]] = {}
    for bib, conf, bbox, rank in prepared:
        prev = best.get(bib)
        if prev is None or rank > prev[1]:
            best[bib] = (bib, conf, bbox)

    # Prefer longer digit cores (5-digit race bibs) over short noise
    def sort_key(item: tuple[str, float, list[float]]) -> tuple:
        bib, conf, _ = item
        digits = re.sub(r"\D", "", bib)
        return (conf, len(digits), 1 if bib.isdigit() else 0)

    tags = sorted(best.values(), key=sort_key, reverse=True)[:3]

    autoable: list[tuple[str, float, list[float]]] = []
    reviewable: list[tuple[str, float, list[float]]] = []

    for bib, conf, bbox in tags:
        in_roster = not roster or bib in roster or any(
            bib == r or bib in r or r in bib for r in roster
        )
        if conf >= threshold_auto and in_roster:
            autoable.append((bib, conf, bbox))
        elif conf >= threshold_review_min:
            reviewable.append((bib, conf, bbox))
            if roster and not in_roster:
                reasons.append("bib_not_in_roster")
            else:
                reasons.append("low_confidence")
        else:
            reasons.append("below_review_min")

    # If multiple tags, prefer single best digit-only for auto
    if autoable:
        autoable_sorted = sorted(autoable, key=sort_key, reverse=True)
        # Auto only the best digit core to avoid QUYNHON-style multi spam
        primary = [autoable_sorted[0]]
        extras = [t for t in autoable_sorted[1:] if t[0].isdigit() and t[0] != primary[0][0]]
        # multi-runner photos may have 2 digit cores
        chosen = primary + extras[:1]
        if reviewable:
            reasons.append("mixed_confidence")
            return ClassifiedTags(OcrJobStatus.needs_review, chosen + reviewable, reasons, raw_texts)
        return ClassifiedTags(OcrJobStatus.auto_tagged, chosen, reasons, raw_texts)

    if reviewable:
        return ClassifiedTags(OcrJobStatus.needs_review, reviewable[:2], reasons, raw_texts)
    return ClassifiedTags(OcrJobStatus.no_bib, [], reasons or ["drop_guess"], raw_texts)
