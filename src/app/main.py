import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from app import __version__
from app.api.jobs import router as jobs_router
from app.core.config import get_settings

STATIC_DIR = Path(__file__).resolve().parent / "static"
logger = logging.getLogger("uvicorn.error")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Load YOLO + OCR once at startup (tránh cold-start mỗi request)."""
    settings = get_settings()
    if settings.ocr_warmup_on_start:
        from app.services.pipeline import get_detector, get_engine

        if settings.yolo_enabled:
            logger.info("Warming YOLO (%s)...", settings.yolo_model)
            get_detector().warmup()
        if not settings.ocr_mock:
            logger.info("Warming OCR (%s / %s)...", settings.ocr_det_model, settings.ocr_rec_model)
            get_engine().warmup()
        logger.info("Engines ready")
    yield


app = FastAPI(
    title="RaceDay OCR Service",
    version=__version__,
    description="Standalone BIB OCR worker (YOLO ROI → PaddleOCR). WebAPI integration deferred.",
    lifespan=lifespan,
)
app.include_router(jobs_router)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/")
def root() -> RedirectResponse:
    return RedirectResponse(url="/demo")


@app.get("/demo")
def demo_page() -> FileResponse:
    return FileResponse(STATIC_DIR / "demo.html")


@app.get("/healthz")
def healthz() -> dict:
    from app.services.pipeline import get_detector, get_engine

    settings = get_settings()
    return {
        "status": "ok",
        "version": __version__,
        "phase": "standalone_ocr_service",
        "webapi_integration": "deferred",
        "ocr_mock": settings.ocr_mock,
        "model_loaded": not settings.ocr_mock,
        "engine": "mock" if settings.ocr_mock else get_engine().name,
        "yolo_enabled": bool(settings.yolo_enabled and get_detector().enabled),
        "max_inflight": settings.max_inflight,
        "max_image_side": settings.max_image_side,
    }
