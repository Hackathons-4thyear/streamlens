"""Fetch the OneAquaHealth research sites once into data/sites.json.

The live endpoint is public and needs no key, but the app must work offline and
must not depend on it at runtime -- so this script is run by hand when the site
list needs refreshing, and the API only ever reads the local file.

Usage:  python scripts/fetch_sites.py
"""

from __future__ import annotations

import json
import ssl
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

SITES_URL = "https://api.enora-oah.eu/api/sites/all"
OUT_PATH = Path(__file__).resolve().parents[1] / "data" / "sites.json"
ATTRIBUTION = "Site data: OneAquaHealth / ENORA API"

# The five OneAquaHealth research cities, keyed by the API's own city id.
CITY_COUNTRY = {
    "CO": ("Portugal", "pt"),
    "BE": ("Italy", "it"),
    "TO": ("France", "fr"),
    "GH": ("Belgium", "nl"),
    "OS": ("Norway", "no"),
}


def fetch(url: str) -> list[dict]:
    ctx = ssl.create_default_context()
    req = urllib.request.Request(url, headers={"User-Agent": "StreamLens/0.1 (hackathon)"})
    with urllib.request.urlopen(req, timeout=30, context=ctx) as resp:
        if resp.status != 200:
            raise RuntimeError(f"{url} returned HTTP {resp.status}")
        return json.loads(resp.read().decode("utf-8"))


def normalise(raw: list[dict]) -> list[dict]:
    sites: list[dict] = []
    for item in raw:
        city = item.get("city") or {}
        city_id = city.get("id") or ""
        country, lang = CITY_COUNTRY.get(city_id, ("", "en"))
        sites.append(
            {
                "id": item["code"],
                "name": item["name"],
                "city_id": city_id,
                "city": city.get("name", ""),
                "country": country,
                "lang": lang,
                "lat": _f(item.get("latitude")),
                "lon": _f(item.get("longitude")),
                "altitude_m": _f(item.get("altitude")),
                "city_lat": _f(city.get("latitude")),
                "city_lon": _f(city.get("longitude")),
            }
        )
    sites.sort(key=lambda s: (s["city"], s["id"]))
    return sites


def _f(value: object) -> float | None:
    return None if value is None else float(value)


def main() -> int:
    try:
        raw = fetch(SITES_URL)
    except Exception as exc:  # noqa: BLE001 - this is a CLI, report and stop
        print(f"Could not reach {SITES_URL}: {exc}", file=sys.stderr)
        print("data/sites.json was left unchanged.", file=sys.stderr)
        return 1

    sites = normalise(raw)
    doc = {
        "source": "https://api.enora-oah.eu/api/sites/all",
        "source_kind": "live-api",
        "attribution": ATTRIBUTION,
        "fetched_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "synthetic": False,
        "note": (
            "Fetched once and served from this file at runtime so the app works "
            "offline. Re-run scripts/fetch_sites.py to refresh."
        ),
        "count": len(sites),
        "cities": sorted({s["city"] for s in sites}),
        "sites": sites,
    }
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(sites)} sites to {OUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
