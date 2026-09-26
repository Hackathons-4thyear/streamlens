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
    # Pseudonymous id generated on the phone. Never a name or an email.
    client_id: str = ""
    # Optional free-text team or school code, typed by the citizen. Used only to
    # group a leaderboard; it is not an account and is not verified.
    team: str = ""
    # The quest this assessment answered, if any.
    completed_quest: str = ""

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


class WeatherCache(SQLModel, table=True):
    """The last Open-Meteo response for a site.

    Cached so the app does not hammer a free service, and kept so that a phone
    with no signal beside a stream can still show a forecast - clearly marked
    with when it was fetched.
    """

    __tablename__ = "weather_cache"

    site_id: str = Field(primary_key=True)
    payload_json: str = ""
    fetched_at: datetime = Field(default_factory=_now)


class AiUsage(SQLModel, table=True):
    """How many real AI calls have been made on a given day.

    In the database rather than in memory so it survives restarts and is shared
    between workers. This is the counter that actually protects a free-tier key
    from being exhausted by a demo left open in somebody's browser tab.
    """

    __tablename__ = "ai_usage"

    day: str = Field(primary_key=True, description="UTC date, YYYY-MM-DD")
    calls: int = 0


# --------------------------------------------------------------------------
# Engine / session
# --------------------------------------------------------------------------

_engine = None


def get_engine(settings: Settings | None = None):
    global _engine
    if _engine is None:
        settings = settings or get_settings()
        _engine = create_engine(
            settings.resolved_database_url,
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
