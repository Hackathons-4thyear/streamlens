"""Deleting stored photographs once they are past their keep-by date.

The hosted demo does not store photograph bytes at all (`STORE_PHOTOS=false`),
so on that instance this sweep finds nothing, and that is the point: the promise
is kept by not having the files rather than by remembering to delete them.

An instance that does keep photographs deletes them after
`photo_retention_days`, counted from when the server received the assessment
rather than from the time the phone claimed - a clock we do not control should
not be able to extend or shorten a retention window.

What survives a sweep is the measurement: the blur score, the brightness, the
size. A reviewer needs those to judge whether an assessment rested on a usable
image; the image itself is not needed for that, and it is the part that carries
the risk.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta, timezone

from sqlmodel import Session, select

from .config import Settings
from .models import Observation, ObservationPhoto

log = logging.getLogger(__name__)

# The sweep runs at most this often per process, so a burst of submissions does
# not turn into a burst of directory scans.
MIN_INTERVAL_S = 3600.0

_last_run: float = 0.0


def reset_for_tests() -> None:
    global _last_run
    _last_run = 0.0


def sweep(session: Session, settings: Settings, *, now: datetime | None = None) -> int:
    """Delete photograph files past the retention window. Returns the count."""
    moment = now or datetime.now(timezone.utc)
    # Stored naive, as everywhere else in this schema.
    cutoff = (moment - timedelta(days=settings.photo_retention_days)).replace(tzinfo=None)

    rows = session.exec(
        select(ObservationPhoto)
        .join(Observation, Observation.id == ObservationPhoto.observation_id)
        .where(ObservationPhoto.filename != "", Observation.created_at < cutoff)
    ).all()

    deleted = 0
    for row in rows:
        path = settings.upload_path / row.filename
        try:
            path.unlink(missing_ok=True)
        except OSError as exc:  # pragma: no cover - platform dependent
            log.warning("could not delete %s: %s", path, exc)
            continue
        # The row stays, without the file: the observation keeps the evidence of
        # its own quality, and the record says plainly that the image is gone.
        row.filename = ""
        row.bytes_stored = 0
        session.add(row)
        deleted += 1

    if deleted:
        session.commit()
        log.info(
            "retention sweep deleted %d photo(s) older than %d days",
            deleted,
            settings.photo_retention_days,
        )
    return deleted


def sweep_if_due(session: Session, settings: Settings) -> int:
    """Sweep, but not more than once an hour in this process."""
    global _last_run
    if not settings.store_photos:
        return 0
    now = time.monotonic()
    if _last_run and now - _last_run < MIN_INTERVAL_S:
        return 0
    _last_run = now
    return sweep(session, settings)
