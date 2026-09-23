"""The research sites, loaded from data/sites.json.

Deliberately a local file and never a live call: the app has to work in a field
with no signal, and a hackathon demo should not depend on somebody else's uptime.
Refresh the file with scripts/fetch_sites.py.
"""

from __future__ import annotations

import json
import math
from functools import lru_cache
from pathlib import Path
from typing import Any

from .config import DATA_DIR

SITES_PATH = DATA_DIR / "sites.json"

EARTH_RADIUS_M = 6_371_000.0


class SiteSet:
    def __init__(self, doc: dict[str, Any]) -> None:
        self.doc = doc
        self.sites: dict[str, dict[str, Any]] = {s["id"]: s for s in doc.get("sites", [])}

    def get(self, site_id: str) -> dict[str, Any] | None:
        return self.sites.get(site_id)

    def all(self) -> list[dict[str, Any]]:
        return list(self.sites.values())

    @property
    def attribution(self) -> str:
        return self.doc.get("attribution", "")

    @property
    def meta(self) -> dict[str, Any]:
        return {
            "source": self.doc.get("source"),
            "attribution": self.attribution,
            "fetched_at": self.doc.get("fetched_at"),
            "count": len(self.sites),
            "cities": self.doc.get("cities", []),
            "synthetic": self.doc.get("synthetic", False),
        }


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in metres."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(a))


def load_sites(path: Path | None = None) -> SiteSet:
    target = path or SITES_PATH
    with target.open(encoding="utf-8") as fh:
        return SiteSet(json.load(fh))


@lru_cache
def get_sites() -> SiteSet:
    return load_sites()
