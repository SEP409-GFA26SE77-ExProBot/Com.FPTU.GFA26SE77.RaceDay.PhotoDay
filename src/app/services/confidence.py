"""Confidence banding + BIB filter for noisy race photos (watermark/signage)."""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.core.config import get_settings
from app.core.status import OcrJobStatus
from app.services.bib_roster import (
    format_webapi_bib,
    normalize_alnum,
    parse_webapi_bib,
    resolve_against_roster,
)
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

# Core bib: optional category letter + N digits + optional gender M/F
# Default N = 3–6 (fun-run 3 số → marathon 5–6). Env: BIB_MIN_DIGITS / BIB_MAX_DIGITS.
# WebAPI FormatBib also: alphanumeric prefix + D4 (A0020, 210020).


def _bib_patterns() -> tuple[re.Pattern[str], re.Pattern[str]]:
    s = get_settings()
    lo = max(1, min(8, int(s.bib_min_digits)))
    hi = max(lo, min(8, int(s.bib_max_digits)))
    return (
        re.compile(rf"^([A-Z])?(\d{{{lo},{hi}}})([MF])?$"),
        re.compile(rf"\d{{{lo},{hi}}}"),
    )


# RaceDay FormatBib shapes (avoid splitting marathon cores like 80183 → 8+0183).
_LETTER_D4 = re.compile(r"^([A-Z]+-?)(\d{4})([MF])?$")
_KM_D4 = re.compile(r"^(5|10|15|21|42)(\d{4})([MF])?$")
_PURE_D4 = re.compile(r"^(\d{4})([MF])?$")


@dataclass
class ClassifiedTags:
    status: OcrJobStatus
    tags: list[tuple[str, float, list[float]]]
    reasons: list[str]
    raw_texts: list[dict]


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
    Emits digit cores + WebAPI FormatBib forms (prefix + D4) when present.
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

    def _add(token: str) -> None:
        if token and token not in out:
            out.append(token)

    # Apply digit fixes only on digit-heavy tokens
    if digit_count >= letter_count:
        fixed = norm.translate(_DIGIT_FIX)
    else:
        fixed = norm

    # RaceDay FormatBib: letter prefix / km prefix / pure D4 only (not 80183→8+0183).
    for rx, kind in ((_LETTER_D4, "letter"), (_KM_D4, "km"), (_PURE_D4, "pure")):
        wm = rx.match(fixed)
        if not wm:
            continue
        if kind == "pure":
            digits4 = wm.group(1)
            pref = ""
        else:
            pref, digits4 = wm.group(1), wm.group(2)
            pref = pref.rstrip("-")
        if _reject_digit_core(digits4):
            continue
        seq = int(digits4)
        _add(format_webapi_bib(pref, seq))
        _add(digits4)
        _add(str(seq))
        break

    bib_full, digit_run = _bib_patterns()
    m = bib_full.match(fixed)
    if m:
        prefix, digits, _gender = m.group(1), m.group(2), m.group(3)
        if _reject_digit_core(digits):
            return out
        _add(digits)
        if prefix:
            _add(f"{prefix}{digits}")
            # Letter + short seq (A20) → also FormatBib A0020 for roster resolve
            if digits.isdigit() and 1 <= int(digits) <= 9999:
                _add(format_webapi_bib(prefix, int(digits)))
        if out:
            return out

    # Embedded digit run only if token is short overall
    if len(fixed) <= 12:
        for dig in digit_run.findall(fixed):
            if _reject_digit_core(dig):
                continue
            _add(dig)
    return out


def _reject_digit_core(digits: str) -> bool:
    """Drop phone/year-like cores; giữ zero-padded bib (009, 077)."""
    if not digits:
        return True
    # SĐT dài: 09xxxxxxxx — không phải bib plate
    if digits.startswith("0") and len(digits) >= 9:
        return True
    # Zero-pad ngắn 01/02… (1–2 số sau khi có 0) quá nhiễu nếu tổng < min bib
    # 009 / 077 / 0142 = bib thật trên áo — CHO QUA khi độ dài trong range cấu hình
    if digits.startswith("0") and len(digits) < 3:
        return True
    # Watermark years 2020–2029 and OCR gluing "20"+"26"
    if digits.startswith("20") and len(digits) in {4, 5, 6}:
        return True
    return False


def looks_like_bib(text: str) -> bool:
    bib_full, _ = _bib_patterns()
    return bool(bib_full.match(normalize_alnum(text).translate(_DIGIT_FIX)))


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

    # Resolve against roster → emit WebAPI canonical bib (A0020 / 210020), not fuzzy substring.
    roster_set = {r for r in roster if r}
    resolved_best: dict[str, tuple[str, float, list[float]]] = {}
    for bib, conf, bbox, rank in prepared:
        if roster_set:
            resolved = resolve_against_roster(bib, roster_set)
            if resolved is None:
                # Keep unresolved for review path (key by original)
                key = f"?{bib}"
                prev = resolved_best.get(key)
                if prev is None or rank > prev[1]:
                    resolved_best[key] = (bib, conf, bbox)
                continue
            emit = resolved
        else:
            # No roster: keep digit cores as-is; only canonicalize letter/km FormatBib forms
            emit = bib
            parsed = parse_webapi_bib(bib)
            if parsed is not None and (
                any(ch.isalpha() for ch in parsed[0]) or parsed[0] in {"5", "10", "15", "21", "42"}
            ):
                emit = format_webapi_bib(parsed[0], parsed[1])

        prev = resolved_best.get(emit)
        if prev is None or rank > prev[1]:
            resolved_best[emit] = (emit, conf, bbox)

    # Prefer higher conf; when tied prefer roster-canonical (has prefix / longer)
    def sort_key(item: tuple[str, float, list[float]]) -> tuple:
        bib, conf, _ = item
        digits = re.sub(r"\D", "", bib)
        return (conf, len(bib), len(digits))

    max_tags = max(1, min(32, int(get_settings().bib_max_tags)))
    tags = sorted(resolved_best.values(), key=sort_key, reverse=True)[:max_tags]

    autoable: list[tuple[str, float, list[float]]] = []
    reviewable: list[tuple[str, float, list[float]]] = []

    for bib, conf, bbox in tags:
        if roster_set:
            resolved = resolve_against_roster(bib, roster_set)
            in_roster = resolved is not None
            emit = resolved if resolved is not None else bib
        else:
            in_roster = True
            emit = bib

        if conf >= threshold_auto and in_roster:
            autoable.append((emit, conf, bbox))
        elif conf >= threshold_review_min:
            reviewable.append((emit, conf, bbox))
            if roster_set and not in_roster:
                reasons.append("bib_not_in_roster")
            else:
                reasons.append("low_confidence")
        else:
            reasons.append("below_review_min")

    def _seq_key(bib: str) -> str:
        """Collapse A0020 / 0020 / 20 (and A80183 / 80183) to one runner slot."""
        digits = re.sub(r"\D", "", bib)
        if digits.isdigit():
            return str(int(digits))
        return bib

    def _prefer_emit(bib: str, pool: list[tuple[str, float, list[float]]]) -> str:
        """With roster keep canonical; without roster prefer digit-core (legacy)."""
        if roster_set:
            return bib
        core = re.sub(r"\D", "", bib)
        sk = _seq_key(bib)
        digit_hit = next(
            (t[0] for t in pool if t[0].isdigit() and _seq_key(t[0]) == sk),
            None,
        )
        if digit_hit:
            return digit_hit
        return core or bib

    # Multi-runner: one tag per sequence; roster → canonical Form; else digit-core.
    if autoable:
        autoable_sorted = sorted(autoable, key=sort_key, reverse=True)
        chosen: list[tuple[str, float, list[float]]] = []
        seen_seqs: set[str] = set()
        for bib, conf, bbox in autoable_sorted:
            sk = _seq_key(bib)
            if not sk or sk in seen_seqs:
                continue
            seen_seqs.add(sk)
            chosen.append((_prefer_emit(bib, autoable_sorted), conf, bbox))
            if len(chosen) >= max_tags:
                break
        if reviewable:
            reasons.append("mixed_confidence")
            extra_rev = [
                t for t in reviewable if _seq_key(t[0]) not in seen_seqs
            ][: max(0, max_tags - len(chosen))]
            return ClassifiedTags(OcrJobStatus.needs_review, chosen + extra_rev, reasons, raw_texts)
        return ClassifiedTags(OcrJobStatus.auto_tagged, chosen, reasons, raw_texts)

    if reviewable:
        return ClassifiedTags(OcrJobStatus.needs_review, reviewable[:max_tags], reasons, raw_texts)
    return ClassifiedTags(OcrJobStatus.no_bib, [], reasons or ["drop_guess"], raw_texts)
