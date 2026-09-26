"""Open-Meteo forecasts, cached, with an honest offline fallback.

Two rules shape this file:

1. **The cache is served when the network is gone, and its age is always
   reported.** A forecast from yesterday is still useful beside a stream with no
   signal - but only if the screen says it is from yesterday. `fetched_at` and
   `stale` travel with every response.
2. **A weather failure never breaks a page.** If there is no forecast and no
   cache, the alert engine is told so and simply produces no weather-based
   alerts, rather than the site page failing to load.

No API key: Open-Meteo is free for non-commercial use and asks only for
attribution, which the UI carries.
"""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from sqlmodel import Session, select

from .models import WeatherCache

logger = logging.getLogger(__name__)

API_URL = "https://api.open-meteo.com/v1/forecast"
ATTRIBUTION = "Weather data by Open-Meteo.com (CC-BY-4.0)"
TIMEOUT_S = 12.0


@dataclass
class Forecast:
    """The 48-hour summary the alert rules need."""

    site_id: str
    rain_mm_48h: float = 0.0
    # Rain that has already fallen in the last 48 hours. Quests ask "did it rain
    # here on Tuesday?", which the forecast half of the window cannot answer.
    rain_mm_past_48h: float = 0.0
    temp_max_c: float | None = None
    temp_min_c: float | None = None
    fetched_at: datetime | None = None
    stale: bool = False
    age_seconds: int = 0
    available: bool = True
    error: str = ""
    source: str = ATTRIBUTION
    # True when this forecast was planted by the demo seeder rather than
    # fetched. The API returns it and the UI badges it; a demo must never
    # show invented weather as though it were real.
    synthetic: bool = False
    hourly: list[dict] = field(default_factory=list)

    @property
    def summary(self) -> str:
        if not self.available:
            return "No forecast available."
        parts = [f"{self.rain_mm_48h:.0f} mm rain forecast over 48 h"]
        if self.temp_max_c is not None:
            parts.append(f"up to {self.temp_max_c:.0f} °C")
        text = ", ".join(parts)
        return f"DEMO FORECAST - {text}" if self.synthetic else text


def _now() -> datetime:
    return datetime.now(timezone.utc)


def is_planted(payload: dict) -> bool:
    """True for a demo forecast written by scripts/seed_demo.py."""
    return bool(payload.get("_streamlens_synthetic"))


def rebase_planted(payload: dict, *, now: datetime | None = None) -> dict:
    """Slide a planted forecast onto the current clock.

    A planted forecast is a shape - so many millimetres an hour, from 48 hours
    ago to 72 hours ahead - not a claim about particular hours. Left alone it
    ages out of its own window within a day and the rules it exists to
    demonstrate fall silent again. Rebasing keeps the shape and moves the
    timestamps, so a demo shows the same thing in a week as it does today.

    It stays labelled synthetic throughout. The point is to demonstrate a rule
    honestly, not to pass planted weather off as real.
    """
    hourly = payload.get("hourly") or {}
    count = len(hourly.get("time") or [])
    if not count:
        return payload

    moment = (now or _now()).replace(minute=0, second=0, microsecond=0, tzinfo=None)
    # The planter writes 48 hours of past before the present hour.
    start = moment - timedelta(hours=48)
    rebased = dict(payload)
    rebased["hourly"] = dict(hourly)
    rebased["hourly"]["time"] = [
        (start + timedelta(hours=index)).strftime("%Y-%m-%dT%H:00")
        for index in range(count)
    ]
    return rebased


def _parse(site_id: str, payload: dict, fetched_at: datetime, stale: bool) -> Forecast:
    hourly = payload.get("hourly") or {}
    times = hourly.get("time") or []
    rain = hourly.get("precipitation") or []
    temps = hourly.get("temperature_2m") or []

    # Open-Meteo returns from the start of today; take the next 48 entries from
    # now, so "the next 48 hours" means what it says.
    now = _now().replace(tzinfo=None)
    start = 0
    for index, stamp in enumerate(times):
        try:
            if datetime.fromisoformat(stamp) >= now:
                start = index
                break
        except ValueError:
            continue
    window = slice(start, start + 48)

    rain_window = [r for r in rain[window] if r is not None]
    temp_window = [t for t in temps[window] if t is not None]

    past = slice(max(0, start - 48), start)
    rain_past = [r for r in rain[past] if r is not None]

    age = int((_now() - fetched_at).total_seconds()) if fetched_at else 0
    synthetic = bool(payload.get("_streamlens_synthetic"))
    return Forecast(
        synthetic=synthetic,
        site_id=site_id,
        rain_mm_48h=round(sum(rain_window), 1),
        rain_mm_past_48h=round(sum(rain_past), 1),
        temp_max_c=max(temp_window) if temp_window else None,
        temp_min_c=min(temp_window) if temp_window else None,
        fetched_at=fetched_at,
        stale=stale,
        age_seconds=max(0, age),
        available=True,
        hourly=[
            {"time": t, "precipitation_mm": r, "temperature_c": c}
            for t, r, c in zip(times[window], rain[window], temps[window])
        ],
    )


def fetch_live(lat: float, lon: float) -> dict:
    """One call to Open-Meteo. Raises on any failure."""
    query = urllib.parse.urlencode({
        "latitude": f"{lat:.4f}",
        "longitude": f"{lon:.4f}",
        "hourly": "precipitation,temperature_2m",
        "forecast_days": 3,
        # Two days of already-observed weather, so one cached response serves
        # both the forecast rules and the after-rain quests.
        "past_days": 2,
        "timezone": "UTC",
    })
    request = urllib.request.Request(
        f"{API_URL}?{query}", headers={"User-Agent": "StreamLens/0.2"}
    )
    with urllib.request.urlopen(request, timeout=TIMEOUT_S) as response:
        return json.loads(response.read().decode("utf-8"))


def get_forecast(
    session: Session,
    site_id: str,
    lat: float | None,
    lon: float | None,
    *,
    cache_seconds: int = 3600,
    allow_network: bool = True,
) -> Forecast:
    """A forecast for one site: cache first, then network, then stale cache."""
    if lat is None or lon is None:
        return Forecast(site_id=site_id, available=False,
                        error="This site has no recorded coordinates.")

    cached = session.get(WeatherCache, site_id)
    if cached:
        payload = json.loads(cached.payload_json)
        if is_planted(payload):
            # Planted demo weather is never refreshed from the network and never
            # expires: it is there to demonstrate a rule, and a demo that only
            # works for an hour after seeding demonstrates nothing. Delete the
            # row (scripts/seed_demo.py --reset) to get the real forecast back.
            return _parse(site_id, rebase_planted(payload), _now(), stale=False)

        age = (_now() - cached.fetched_at.replace(tzinfo=timezone.utc)).total_seconds()
        if age < cache_seconds:
            return _parse(site_id, json.loads(cached.payload_json),
                          cached.fetched_at.replace(tzinfo=timezone.utc), stale=False)

    if allow_network:
        try:
            payload = fetch_live(lat, lon)
        except Exception as exc:  # noqa: BLE001 - any network failure is the same here
            logger.warning("Open-Meteo unavailable for %s: %s", site_id, exc)
        else:
            fetched_at = _now()
            row = session.get(WeatherCache, site_id)
            if row:
                row.payload_json = json.dumps(payload)
                row.fetched_at = fetched_at
            else:
                row = WeatherCache(
                    site_id=site_id,
                    payload_json=json.dumps(payload),
                    fetched_at=fetched_at,
                )
            session.add(row)
            session.commit()
            return _parse(site_id, payload, fetched_at, stale=False)

    # Network gone. A stale forecast beats none, as long as we say it is stale.
    if cached:
        forecast = _parse(site_id, json.loads(cached.payload_json),
                          cached.fetched_at.replace(tzinfo=timezone.utc), stale=True)
        forecast.error = "Showing the last forecast we were able to fetch."
        return forecast

    return Forecast(
        site_id=site_id,
        available=False,
        error="No forecast could be fetched and nothing is cached for this site.",
    )


def purge_older_than(session: Session, days: int = 30) -> int:
    """Housekeeping: a forecast nobody looked at in a month is not worth keeping."""
    cutoff = _now().replace(tzinfo=None) - timedelta(days=days)
    rows = session.exec(select(WeatherCache).where(WeatherCache.fetched_at < cutoff)).all()
    for row in rows:
        session.delete(row)
    session.commit()
    return len(rows)
