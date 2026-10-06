"""Quick check filter against known OCR tokens from VN photos."""

from app.services.confidence import classify
from app.services.ocr_engine import OcrCandidate

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
]

size = (1024, 682)
for i, cands in enumerate(cases, 1):
    r = classify(cands, set(), threshold_auto=0.85, threshold_review_min=0.5, image_size=size)
    print(i, r.status.value, [t[0] for t in r.tags], r.reasons)
