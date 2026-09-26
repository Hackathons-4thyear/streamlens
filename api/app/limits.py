"""Keeping a free-tier API key inside its free tier.

StreamLens runs on Gemini's unpaid quota and there is no billing account behind
it. That has one hard consequence: when the quota is gone, it is gone. So the
job here is to make sure the demo degrades to the labelled mock provider with a
visible notice, and never to an error page and never to a surprise bill.

Two limits, both deliberately crude:

- **Per caller, per hour.** An in-memory sliding window keyed by client id, or
  by IP when no client id is sent. In memory is enough: the worst case after a
  restart is that one caller gets their allowance back early, which costs a
  handful of requests, and the daily cap below still holds the line.
- **Everyone, per day.** A counter in the database, so it survives restarts and
  is shared across workers. This is the one that actually protects the key.

Neither limit rejects the request. Hitting one means the answer comes from the
mock, marked `quota`, which the interface already knows how to show.
"""

from __future__ import annotations

import threading
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlmodel import Session, select

from .models import AiUsage

_WINDOW_SECONDS = 3600

# client/IP -> timestamps of recent AI calls. Process-local by design.
_recent: dict[str, deque[float]] = defaultdict(deque)
_lock = threading.Lock()


@dataclass
class Decision:
    allowed: bool
    reason: str = ""
    # Shown to the citizen. Plain, and never blaming them.
    message: str = ""
    used_today: int = 0
    daily_cap: int = 0
    used_this_hour: int = 0
    hourly_cap: int = 0

    @property
    def remaining_today(self) -> int:
        return max(0, self.daily_cap - self.used_today)


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _prune(key: str, now: float) -> deque[float]:
    seen = _recent[key]
    while seen and now - seen[0] > _WINDOW_SECONDS:
        seen.popleft()
    return seen


def check(
    session: Session,
    caller: str,
    *,
    per_hour: int,
    per_day: int,
    now: float | None = None,
) -> Decision:
    """Decide whether this caller may use the real AI right now.

    Does NOT record the call - see `record` - so a request that fails before it
    reaches the provider does not consume anybody's allowance.
    """
    import time

    now = now if now is not None else time.time()
    day = _today()

    row = session.get(AiUsage, day)
    used_today = row.calls if row else 0

    with _lock:
        seen = _prune(caller or "anonymous", now)
        used_hour = len(seen)

    if per_day > 0 and used_today >= per_day:
        return Decision(
            allowed=False,
            reason="daily_cap",
            message=(
                "StreamLens has used up today's free allowance of AI suggestions. "
                "The questions below are filled in by the offline demo helper "
                "instead - answer them yourself as usual, and the AI will be back "
                "tomorrow."
            ),
            used_today=used_today, daily_cap=per_day,
            used_this_hour=used_hour, hourly_cap=per_hour,
        )

    if per_hour > 0 and used_hour >= per_hour:
        return Decision(
            allowed=False,
            reason="hourly_cap",
            message=(
                f"You have used {used_hour} AI suggestions in the last hour, which "
                "is this demo's limit. The questions below come from the offline "
                "demo helper instead. Your own answers are unaffected."
            ),
            used_today=used_today, daily_cap=per_day,
            used_this_hour=used_hour, hourly_cap=per_hour,
        )

    return Decision(
        allowed=True,
        used_today=used_today, daily_cap=per_day,
        used_this_hour=used_hour, hourly_cap=per_hour,
    )


def record(session: Session, caller: str, now: float | None = None) -> None:
    """Count one real AI call, against both limits."""
    import time

    now = now if now is not None else time.time()
    with _lock:
        _prune(caller or "anonymous", now).append(now)

    day = _today()
    row = session.get(AiUsage, day)
    if row is None:
        row = AiUsage(day=day, calls=1)
    else:
        row.calls += 1
    session.add(row)
    session.commit()


def usage_today(session: Session) -> int:
    row = session.get(AiUsage, _today())
    return row.calls if row else 0


def reset_for_tests() -> None:
    with _lock:
        _recent.clear()


def purge_old_usage(session: Session, keep_days: int = 60) -> int:
    """Housekeeping; the counters are tiny but unbounded growth is untidy."""
    rows = session.exec(select(AiUsage)).all()
    cutoff = datetime.now(timezone.utc).toordinal() - keep_days
    removed = 0
    for row in rows:
        try:
            ordinal = datetime.strptime(row.day, "%Y-%m-%d").toordinal()
        except ValueError:
            continue
        if ordinal < cutoff:
            session.delete(row)
            removed += 1
    if removed:
        session.commit()
    return removed
