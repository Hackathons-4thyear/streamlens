"""StreamLens API."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .models import init_db
from .routers import assess, catalog, observations

logging.basicConfig(level=logging.INFO)

DESCRIPTION = """
StreamLens helps a volunteer assess an urban stream from photographs.

**The AI suggests; the citizen decides.** `/assess/suggest` returns draft answers
with a confidence and a reason. Every one is validated against the published
question set before it is returned, and the overall Good/Moderate/Poor rating is
never suggested - it is stored only as the citizen's own answer.

Photos have their EXIF metadata, including any embedded GPS, stripped before
storage, and are downscaled to 1600 px.
"""


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="StreamLens API",
        version=catalog.VERSION,
        description=DESCRIPTION,
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(catalog.router)
    app.include_router(assess.router)
    app.include_router(observations.router)
    return app


app = create_app()
