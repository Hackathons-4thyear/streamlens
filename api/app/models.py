"""SQLModel tables and the database session.

The design point worth noting: an answer row stores BOTH what the citizen
answered and what the AI had suggested. Keeping the two side by side is what
lets us measure later how often people disagreed with the model - which is the
honest way to report on an AI assistant, and impossible if you only store the
final answer.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from sqlmodel import Field, Session, SQLModel, create_engine

from .config import Settings, get_settings


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Observation(SQLModel, table=True):
    __tablename__ = "observation"

    id: str = Field(default_factory=_uuid, primary_key=True)
    site_id: str = Field(index=True)
    overall: str
    lang: str = "en"

    # Location comes only from the citizen's explicit share, never from a photo.
    lat: float | None = None
    lon: float | None = None
    accuracy_m: float | None = None

    emotions_json: str = "{}"
    note: str = ""
    consent_given: bool = False
    synthetic: bool = Field(default=False, index=True)
    client_id: str = ""

    ai_provider: str = ""
    ai_model: str = ""

    recorded_at: datetime = Field(default_factory=_now)
    created_at: datetime = Field(default_factory=_now)

    @property
    def emotions(self) -> dict[str, int]:
        try:
            return json.loads(self.emotions_json)
        except (ValueError, TypeError):
            return {}


class ObservationAnswer(SQLModel, table=True):
    __tablename__ = "observation_answer"

    id: int | None = Field(default=None, primary_key=True)
    observation_id: str = Field(index=True, foreign_key="observation.id")
    question_id: str = Field(index=True)
    codes_json: str = "[]"

    ai_suggested_code: str | None = None
    ai_confidence: float | None = None
    agreed_with_ai: bool | None = None

    @property
    def codes(self) -> list[str]:
        try:
            return json.loads(self.codes_json)
        except (ValueError, TypeError):
            return []


class ObservationPhoto(SQLModel, table=True):
    __tablename__ = "observation_photo"

    id: int | None = Field(default=None, primary_key=True)
    observation_id: str = Field(index=True, foreign_key="observation.id")
    role: str
    filename: str
    width: int = 0
    height: int = 0
    blur_score: float = 0.0
    brightness: float = 0.0
    exif_stripped: bool = True
    bytes_stored: int = 0


# --------------------------------------------------------------------------
# Engine / session
# --------------------------------------------------------------------------

_engine = None


def get_engine(settings: Settings | None = None):
    global _engine
    if _engine is None:
        settings = settings or get_settings()
        _engine = create_engine(
            settings.database_url,
            connect_args={"check_same_thread": False},
        )
    return _engine


def set_engine(engine) -> None:
    """Point the app at a different engine. Used by the tests."""
    global _engine
    _engine = engine


def init_db(settings: Settings | None = None) -> None:
    SQLModel.metadata.create_all(get_engine(settings))


def get_session():
    with Session(get_engine()) as session:
        yield session
