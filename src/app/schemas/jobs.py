from typing import Any

from pydantic import BaseModel, Field, HttpUrl

from app.core.status import OcrJobStatus


class OcrJobOptions(BaseModel):
    threshold_auto: float | None = None
    threshold_review_min: float | None = None
    force: bool = False
    skip_blur_gate: bool = False


class CreateOcrJobRequest(BaseModel):
    job_id: str
    event_id: str
    photo_id: str
    image_url: HttpUrl | None = None
    content_sha256: str | None = None
    bib_roster_version: str | None = None
    roster_bibs: list[str] = Field(default_factory=list)
    options: OcrJobOptions = Field(default_factory=OcrJobOptions)


class BibTag(BaseModel):
    bib: str
    confidence: float
    bbox: list[float] = Field(default_factory=list)
    source: str = "paddleocr"


class OcrJobResult(BaseModel):
    job_id: str
    photo_id: str
    event_id: str
    status: OcrJobStatus
    duplicate_of: str | None = None
    tags: list[BibTag] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)
    preprocess_flags: list[str] = Field(default_factory=list)
    engine: dict[str, Any] = Field(default_factory=dict)
    latency_ms: int = 0
    blur_variance: float | None = None
    raw_ocr: list[dict[str, Any]] = Field(default_factory=list)


class CreateOcrJobResponse(BaseModel):
    job_id: str
    status: OcrJobStatus
    result: OcrJobResult | None = None


class OcrConfigUpdate(BaseModel):
    threshold_auto: float | None = None
    threshold_review_min: float | None = None
    near_dup_hamming_max: int | None = None
    blur_min_variance: float | None = None
