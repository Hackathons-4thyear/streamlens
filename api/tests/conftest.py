"""Shared fixtures.

Two rules hold for every test in this folder: nothing touches the network, and
nothing writes to the real database or upload folder.
"""

from __future__ import annotations

import io

import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlmodel import SQLModel, create_engine

from app.config import Settings, get_settings
from app.main import create_app
from app.models import set_engine
from app.questions import get_questions
from app.sites import get_sites


@pytest.fixture
def settings(tmp_path) -> Settings:
    return Settings(
        ai_provider="mock",
        gemini_api_key="",
        database_url=f"sqlite:///{tmp_path / 'test.db'}",
        upload_dir=str(tmp_path / "uploads"),
    )


@pytest.fixture
def client(settings, tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'test.db'}", connect_args={"check_same_thread": False}
    )
    set_engine(engine)
    SQLModel.metadata.create_all(engine)

    app = create_app()
    app.dependency_overrides[get_settings] = lambda: settings
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    set_engine(None)


@pytest.fixture
def questions():
    return get_questions()


@pytest.fixture
def sites():
    return get_sites()


@pytest.fixture
def site_id(sites) -> str:
    return sites.all()[0]["id"]


# --------------------------------------------------------------------------
# Image fixtures
# --------------------------------------------------------------------------

def _encode(array: np.ndarray) -> bytes:
    buffer = io.BytesIO()
    Image.fromarray(array.astype(np.uint8), mode="RGB").save(buffer, format="JPEG", quality=92)
    return buffer.getvalue()


def sharp_image(size: int = 240) -> bytes:
    """High-contrast checkerboard: lots of edges, so a high Laplacian variance."""
    rows, cols = np.indices((size, size))
    checks = (((rows // 8) + (cols // 8)) % 2) * 255
    return _encode(np.dstack([checks, checks, checks]))


def blurry_image(size: int = 240) -> bytes:
    """A smooth gradient: almost no edges, so a near-zero Laplacian variance."""
    gradient = np.linspace(40, 200, size)
    plane = np.tile(gradient, (size, 1))
    return _encode(np.dstack([plane, plane, plane]))


def dark_image(size: int = 240) -> bytes:
    rows, cols = np.indices((size, size))
    checks = (((rows // 8) + (cols // 8)) % 2) * 20
    return _encode(np.dstack([checks, checks, checks]))


def green_image(size: int = 240) -> bytes:
    """A leafy scene, so the mock provider reads vegetated banks."""
    rows, cols = np.indices((size, size))
    noise = ((rows * 7 + cols * 13) % 60).astype(float)
    red = 40 + noise * 0.4
    green = 120 + noise
    blue = 35 + noise * 0.3
    return _encode(np.dstack([red, green, blue]))


@pytest.fixture
def photos() -> dict[str, bytes]:
    return {
        "sharp": sharp_image(),
        "blurry": blurry_image(),
        "dark": dark_image(),
        "green": green_image(),
    }
