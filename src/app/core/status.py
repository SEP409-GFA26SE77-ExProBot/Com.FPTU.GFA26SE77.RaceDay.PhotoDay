from enum import Enum


class OcrJobStatus(str, Enum):
    queued = "queued"
    processing = "processing"
    auto_tagged = "auto_tagged"
    needs_review = "needs_review"
    no_bib = "no_bib"
    duplicate = "duplicate"
    failed = "failed"
    manual_corrected = "manual_corrected"
    runner_reported = "runner_reported"
