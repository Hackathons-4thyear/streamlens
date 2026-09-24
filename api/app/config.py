"""Settings, read from api/.env. Secrets never live anywhere else."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

API_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = API_DIR.parent
DATA_DIR = REPO_ROOT / "data"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=API_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- AI provider -------------------------------------------------------
    ai_provider: str = "mock"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.5-flash-lite"
    # A citizen standing in the rain does not wait indefinitely for a model.
    gemini_timeout_s: float = 20.0
    # Number of RETRIES after the first attempt, so 1 means two attempts.
    gemini_retries: int = 1
    # Base for exponential backoff between retries, with jitter.
    gemini_backoff_base_s: float = 0.6
    # Which prompt in app/ai/prompts/ to use, without the .md.
    assess_prompt: str = "assess_v2"

    # --- Storage -----------------------------------------------------------
    database_url: str = "sqlite:///./streamlens.db"
    upload_dir: str = "./uploads"

    # --- CORS --------------------------------------------------------------
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # --- Photo handling ----------------------------------------------------
    max_image_px: int = 1600
    blur_threshold: float = 100.0
    dark_threshold: float = 45.0
    bright_threshold: float = 225.0

    # How far from the recorded site coordinates we start warning, in metres.
    gps_warn_m: float = 250.0

    # Below this confidence a suggestion is flagged for the citizen's attention.
    low_confidence: float = 0.55

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def upload_path(self) -> Path:
        path = Path(self.upload_dir)
        if not path.is_absolute():
            path = API_DIR / path
        return path

    @property
    def use_gemini(self) -> bool:
        """Gemini is used only when it is both asked for and actually usable.

        Anything else falls back to the mock provider, which the UI labels.
        """
        return self.ai_provider.lower() == "gemini" and bool(self.gemini_api_key.strip())


@lru_cache
def get_settings() -> Settings:
    return Settings()
