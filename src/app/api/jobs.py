import json
import uuid

from fastapi import APIRouter, File, Form, Header, HTTPException, UploadFile

from app.core.config import Settings, get_settings
from app.schemas.jobs import (
    CreateOcrJobRequest,
    CreateOcrJobResponse,
    OcrConfigUpdate,
    OcrJobOptions,
    OcrJobResult,
)
from app.services.pipeline import run_pipeline

router = APIRouter(prefix="/v1", tags=["ocr"])

# Standalone in-memory store (WebAPI persistence = later phase).
_JOBS: dict[str, OcrJobResult] = {}
_EVENT_CONFIG: dict[str, dict[str, float | int]] = {}


def _auth(settings: Settings, key: str | None) -> None:
    if settings.ocr_auth_disabled:
        return
    if key != settings.ocr_service_key:
        raise HTTPException(status_code=401, detail="invalid service key")


def _apply_event_config(body: CreateOcrJobRequest, settings: Settings) -> Settings:
    cfg = _EVENT_CONFIG.get(body.event_id, {})
    if body.options.threshold_auto is None and "threshold_auto" in cfg:
        body.options.threshold_auto = float(cfg["threshold_auto"])
    if body.options.threshold_review_min is None and "threshold_review_min" in cfg:
        body.options.threshold_review_min = float(cfg["threshold_review_min"])
    updates: dict[str, float | int] = {}
    if "near_dup_hamming_max" in cfg:
        updates["near_dup_hamming_max"] = int(cfg["near_dup_hamming_max"])
    if "blur_min_variance" in cfg:
        updates["blur_min_variance"] = float(cfg["blur_min_variance"])
    return settings.model_copy(update=updates) if updates else settings


@router.post("/ocr/jobs", response_model=CreateOcrJobResponse)
async def create_job_json(
    body: CreateOcrJobRequest,
    x_service_key: str | None = Header(default=None),
) -> CreateOcrJobResponse:
    """Process by image_url. Standalone: returns full result immediately."""
    settings = get_settings()
    _auth(settings, x_service_key)
    if body.image_url is None:
        raise HTTPException(status_code=400, detail="image_url required for JSON create")
    settings = _apply_event_config(body, settings)
    result = await run_pipeline(body, settings)
    _JOBS[body.job_id] = result
    return CreateOcrJobResponse(job_id=body.job_id, status=result.status, result=result)


@router.post("/ocr/jobs/upload", response_model=CreateOcrJobResponse)
async def create_job_upload(
    file: UploadFile = File(...),
    event_id: str = Form(...),
    photo_id: str | None = Form(default=None),
    job_id: str | None = Form(default=None),
    roster_bibs: str = Form(default="[]"),
    force: bool = Form(default=False),
    skip_blur_gate: bool = Form(default=False),
    x_service_key: str | None = Header(default=None),
) -> CreateOcrJobResponse:
    """Upload file trực tiếp — không cần WebAPI/Cloudflare ở phase này."""
    settings = get_settings()
    _auth(settings, x_service_key)

    try:
        roster = json.loads(roster_bibs)
        if not isinstance(roster, list):
            raise ValueError("roster must be list")
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"roster_bibs invalid JSON: {exc}") from exc

    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="empty file")

    body = CreateOcrJobRequest(
        job_id=job_id or str(uuid.uuid4()),
        event_id=event_id,
        photo_id=photo_id or str(uuid.uuid4()),
        image_url=None,
        roster_bibs=[str(x) for x in roster],
        options=OcrJobOptions(force=force, skip_blur_gate=skip_blur_gate),
    )
    settings = _apply_event_config(body, settings)
    result = await run_pipeline(body, settings, image_bytes=data)
    _JOBS[body.job_id] = result
    return CreateOcrJobResponse(job_id=body.job_id, status=result.status, result=result)


@router.get("/ocr/jobs/{job_id}", response_model=OcrJobResult)
async def get_job(
    job_id: str,
    x_service_key: str | None = Header(default=None),
) -> OcrJobResult:
    settings = get_settings()
    _auth(settings, x_service_key)
    result = _JOBS.get(job_id)
    if not result:
        raise HTTPException(status_code=404, detail="job not found")
    return result


@router.get("/ocr/jobs", response_model=list[OcrJobResult])
async def list_jobs(
    event_id: str | None = None,
    x_service_key: str | None = Header(default=None),
) -> list[OcrJobResult]:
    settings = get_settings()
    _auth(settings, x_service_key)
    items = list(_JOBS.values())
    if event_id:
        items = [j for j in items if j.event_id == event_id]
    return items


@router.put("/events/{event_id}/ocr-config")
async def update_config(
    event_id: str,
    body: OcrConfigUpdate,
    x_service_key: str | None = Header(default=None),
) -> dict:
    settings = get_settings()
    _auth(settings, x_service_key)
    cfg = _EVENT_CONFIG.setdefault(event_id, {})
    if body.threshold_auto is not None:
        cfg["threshold_auto"] = body.threshold_auto
    if body.threshold_review_min is not None:
        cfg["threshold_review_min"] = body.threshold_review_min
    if body.near_dup_hamming_max is not None:
        cfg["near_dup_hamming_max"] = body.near_dup_hamming_max
    if body.blur_min_variance is not None:
        cfg["blur_min_variance"] = body.blur_min_variance
    return {"event_id": event_id, "config": cfg}


@router.post("/ocr/dedupe/clear")
async def clear_dedupe_index(
    event_id: str | None = None,
    x_service_key: str | None = Header(default=None),
) -> dict:
    """Dev/retest: xóa SHA/dhash in-memory (Postgres truncate không đụng cache này)."""
    from app.services.dedupe import clear_dedupe

    settings = get_settings()
    _auth(settings, x_service_key)
    cleared = clear_dedupe(event_id)
    return {"ok": True, "cleared": cleared, "event_id": event_id}
