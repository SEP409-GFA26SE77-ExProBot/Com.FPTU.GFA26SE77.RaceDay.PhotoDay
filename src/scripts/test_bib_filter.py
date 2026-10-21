"""Quick check filter against known OCR tokens from VN photos + WebAPI FormatBib roster."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import get_settings
from app.services.bib_roster import resolve_against_roster
from app.services.confidence import classify, extract_bib_candidates
from app.services.ocr_engine import OcrCandidate

get_settings.cache_clear()

cases = [
    # watermark noise
    [
        OcrCandidate("QUY NHON20", 0.7, [9, 16, 154, 62]),
        OcrCandidate("VNEXPRESS MARATHON", 0.99, [14, 12, 145, 27]),
    ],
    # good bib
    [
        OcrCandidate("QUY NHON", 0.72, [9, 18, 152, 60]),
        OcrCandidate("VNEXPRESS MARATHON", 0.99, [14, 12, 145, 27]),
        OcrCandidate("A 80183 F", 0.85, [475, 346, 533, 375]),
        OcrCandidate("OU", 0.73, [365, 381, 435, 417]),
        OcrCandidate("ON", 0.99, [542, 380, 605, 428]),
    ],
    # misread but digit core
    [
        OcrCandidate("QUY NHON20", 0.69, [9, 16, 154, 62]),
        OcrCandidate("10074M", 0.86, [502, 412, 555, 449]),
    ],
    # phone + bib-ish
    [
        OcrCandidate("098", 0.96, [966, 257, 1023, 289]),
        OcrCandidate("30087 M", 0.87, [531, 410, 558, 420]),
        OcrCandidate("HIGHLA", 0.97, [445, 390, 490, 406]),
    ],
    # 3-digit fun-run bib (trước đây bị lọc vì chỉ nhận 4–5 số)
    [
        OcrCandidate("318", 0.92, [480, 350, 530, 390]),
        OcrCandidate("VNEXPRESS", 0.99, [14, 12, 145, 27]),
    ],
    # multi runner: 2 digit cores
    [
        OcrCandidate("318", 0.90, [200, 340, 250, 380]),
        OcrCandidate("80183", 0.91, [500, 340, 560, 380]),
    ],
    # crowd: zero-padded + many 3-digit (giống Race-Strategy-2)
    [
        OcrCandidate("MARATHON", 0.99, [10, 10, 100, 30]),
        OcrCandidate("009", 0.99, [100, 300, 140, 340]),
        OcrCandidate("077", 0.99, [200, 300, 240, 340]),
        OcrCandidate("102", 0.99, [300, 300, 340, 340]),
        OcrCandidate("101", 0.99, [400, 300, 440, 340]),
        OcrCandidate("199", 0.99, [500, 300, 540, 340]),
        OcrCandidate("457", 0.99, [600, 300, 640, 340]),
        OcrCandidate("314", 0.99, [700, 300, 740, 340]),
    ],
]

size = (1024, 682)
for i, cands in enumerate(cases, 1):
    r = classify(cands, set(), threshold_auto=0.85, threshold_review_min=0.5, image_size=size)
    print(i, r.status.value, [t[0] for t in r.tags], r.reasons)

# --- WebAPI FormatBib (prefix + D4) ---
hm_roster = {f"A{n:04d}" for n in range(20, 91)}
assert resolve_against_roster("0020", hm_roster) == "A0020"
assert resolve_against_roster("20", hm_roster) == "A0020"
assert resolve_against_roster("A0020", hm_roster) == "A0020"
assert resolve_against_roster("A20", hm_roster) == "A0020"
assert resolve_against_roster("0099", hm_roster) is None  # outside HM seed range

km_roster = {f"21{n:04d}" for n in range(20, 91)}
assert resolve_against_roster("0020", km_roster) == "210020"
assert resolve_against_roster("210020", km_roster) == "210020"
assert resolve_against_roster("20", km_roster) == "210020"

# Ambiguous: same sequence under two prefixes → no auto resolve
amb = {"A0020", "210020"}
assert resolve_against_roster("0020", amb) is None

print("extract A0020", extract_bib_candidates("A0020"))
print("extract 210020", extract_bib_candidates("210020"))

r_hm = classify(
    [OcrCandidate("0020", 0.95, [400, 350, 480, 400])],
    hm_roster,
    threshold_auto=0.85,
    threshold_review_min=0.5,
    image_size=size,
)
assert r_hm.status.value == "auto_tagged", r_hm
assert r_hm.tags[0][0] == "A0020", r_hm.tags
print("roster HM OCR 0020 ->", r_hm.status.value, [t[0] for t in r_hm.tags])

r_km = classify(
    [OcrCandidate("210020", 0.94, [400, 350, 500, 410])],
    km_roster,
    threshold_auto=0.85,
    threshold_review_min=0.5,
    image_size=size,
)
assert r_km.tags[0][0] == "210020", r_km.tags
print("roster 21 OCR 210020 ->", r_km.status.value, [t[0] for t in r_km.tags])
print("OK webapi bib resolve")
