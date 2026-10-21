from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Always load src/.env even if process cwd is repo root.
_SRC_DIR = Path(__file__).resolve().parents[2]
_ENV_FILE = _SRC_DIR / ".env"


class Settings(BaseSettings):
    """Env-driven settings. Copy `src/.env.example` → `src/.env` for local demo."""

    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE) if _ENV_FILE.exists() else ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    ocr_service_key: str = "dev-ocr-key-change-me"
    ocr_auth_disabled: bool = False

    # Deferred (WebAPI phase) — kept for contract compatibility only.
    redis_url: str = ""
    webapi_callback_base: str = ""

    threshold_auto: float = 0.85
    threshold_review_min: float = 0.50
    near_dup_hamming_max: int = 5
    blur_min_variance: float = 40.0
    max_image_side: int = 1600
    max_inflight: int = 1
    # BIB digit length: 3–6 covers fun-run 3 số + marathon 4–6. 1–2 digits = nhiều nhiễu.
    bib_min_digits: int = 3
    bib_max_digits: int = 6
    # Max distinct bib tags per photo (đám đông / nhiều runner).
    bib_max_tags: int = 8

    ocr_det_model: str = "PP-OCRv5_mobile_det"
    ocr_rec_model: str = "en_PP-OCRv5_mobile_rec"
    ocr_det_limit_side_len: int = 1280
    ocr_warmup_on_start: bool = True
    ocr_mock: bool = False

    yolo_enabled: bool = True
    yolo_model: str = "yolov8n.pt"
    yolo_conf: float = 0.25
    yolo_max_people: int = 8
    yolo_torso_pad: float = 0.08
    ocr_fullframe_fallback: bool = False

    host: str = "0.0.0.0"
    port: int = 8089


@lru_cache
def get_settings() -> Settings:
    return Settings()
