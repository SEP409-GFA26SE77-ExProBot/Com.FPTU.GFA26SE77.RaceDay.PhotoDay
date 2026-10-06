"""Lightweight preprocess flags. See rule_design/02_ocr_confidence_pipeline.md."""

from __future__ import annotations

from dataclasses import dataclass

from PIL import Image, ImageOps


@dataclass
class PreprocessResult:
    image: Image.Image
    flags: list[str]


def preprocess(image: Image.Image, *, max_side: int = 3000) -> PreprocessResult:
    flags: list[str] = []
    img = ImageOps.exif_transpose(image)
    flags.append("orient")

    w, h = img.size
    longest = max(w, h)
    if longest > max_side:
        scale = max_side / float(longest)
        img = img.resize((int(w * scale), int(h * scale)), Image.Resampling.LANCZOS)
        flags.append(f"downscale_{max_side}")

    # Keep contrast near-neutral: strong CLAHE/contrast can warp bib digits at night.
    img = img.convert("RGB")
    flags.append("rgb")

    return PreprocessResult(image=img, flags=flags)
