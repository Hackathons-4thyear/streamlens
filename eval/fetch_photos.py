"""Download a spread of freely-licensed stream photographs into eval/photos/.

Sources are Wikimedia Commons categories listed in docs/photo-sources.md. Only
images under CC0, CC BY, CC BY-SA or a public-domain mark are kept; anything
else, or anything whose licence cannot be read, is skipped.

Every kept image is recorded in eval/photos_manifest.csv with its source URL,
author and licence, so the attribution obligations can actually be met. The
images themselves stay gitignored; the manifest is committed.

Usage:
    python eval/fetch_photos.py
    python eval/fetch_photos.py --dry-run     # list what would be fetched
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path

from PIL import Image

EVAL_DIR = Path(__file__).resolve().parent
PHOTOS_DIR = EVAL_DIR / "photos"
MANIFEST_PATH = EVAL_DIR / "photos_manifest.csv"

API = "https://commons.wikimedia.org/w/api.php"
USER_AGENT = (
    "StreamLens-eval/0.1 (IEEE OneAquaHealth Hackathon 2026; "
    "educational evaluation of a vision prompt)"
)
MAX_PX = 1600
ALLOW_PORTRAIT = False

# Licences we will accept. Matched case-insensitively as substrings.
ALLOWED_LICENCES = (
    "cc0", "public domain", "pd-", "cc by", "cc-by",
)
# ...but never these, even if they also match above.
FORBIDDEN_LICENCES = ("nc", "nd", "non-commercial", "noderiv", "fair use")

# (slug, category, how many to take, what it is meant to show)
TOPUP: list[tuple[str, str, int, str]] = [
    ("litter", "Category:Litter", 2, "Litter in or beside a watercourse"),
    ("litter", "Category:Plastic pollution", 2, "Plastic waste in water"),
    ("litter", "Category:Illegal dumping", 2, "Dumped waste beside water"),
    ("litter", "Category:Marine debris", 1, "Debris washed up at the water's edge"),
]


TARGETS: list[tuple[str, str, int, str]] = [
    # --- the five OneAquaHealth research cities ---------------------------
    ("coimbra", "Category:Mondego River", 2, "River in Coimbra, Portugal (OAH city)"),
    ("benevento", "Category:Calore Irpino", 2, "River at Benevento, Italy (OAH city)"),
    ("toulouse", "Category:Garonne", 2, "River at Toulouse, France (OAH city)"),
    ("ghent", "Category:Leie", 2, "River at Ghent, Belgium (OAH city)"),
    ("oslo", "Category:Akerselva", 2, "River in Oslo, Norway (OAH city)"),
    # --- condition and pressures ------------------------------------------
    ("pollution", "Category:Water pollution", 3, "Visibly polluted water"),
    ("outfall", "Category:Outfalls", 2, "Pipe discharging into a watercourse"),
    ("sewage", "Category:Sewage", 1, "Sewage-related water"),
    ("weir", "Category:Weirs", 2, "Weir: a barrier across the channel"),
    ("culvert", "Category:Culverts", 1, "Culverted / enclosed channel"),
    ("gabion", "Category:Gabions", 2, "Bank hardened with laid stone in cages"),
    ("drybed", "Category:Dry riverbeds", 2, "Dry channel, no water"),
    ("algae", "Category:Algal blooms", 1, "Algal bloom, unusual water colour"),
    # --- vegetation --------------------------------------------------------
    ("knotweed", "Category:Fallopia japonica", 2, "Japanese knotweed, an invasive plant"),
    ("giantreed", "Category:Arundo donax", 2, "Giant reed, an invasive plant"),
    ("riparian", "Category:Riparian zones", 2, "Vegetated bank strip beside water"),
    # --- channel form and habitat -----------------------------------------
    ("rapids", "Category:Rapids", 2, "Fast broken water over stones (riffle)"),
    ("streambed", "Category:Stream beds", 2, "The bed of a stream"),
    ("woodydebris", "Category:Woody debris", 1, "Fallen wood in a channel"),
    ("canal", "Category:Canal du Midi", 1, "Hard-engineered channel"),
    ("erosion", "Category:Erosion", 1, "Eroded bank"),
]


def api_get(params: dict) -> dict:
    params = {**params, "format": "json", "formatversion": "2"}
    url = f"{API}?{urllib.parse.urlencode(params)}"
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=45) as response:
        return json.loads(response.read().decode("utf-8"))


def strip_html(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text or "")
    text = text.replace("&amp;", "&").replace("&nbsp;", " ").replace("&#160;", " ")
    text = text.replace("&quot;", '"').replace("&#39;", "'").replace("&lt;", "<")
    return re.sub(r"\s+", " ", text).strip()


def licence_ok(licence: str) -> bool:
    low = (licence or "").lower()
    if not low:
        return False
    if any(bad in low.split() or bad in low for bad in FORBIDDEN_LICENCES):
        return False
    return any(good in low for good in ALLOWED_LICENCES)


def category_files(category: str, want: int) -> list[dict]:
    """Candidate files from one category, newest-quality-first-ish."""
    try:
        data = api_get({
            "action": "query",
            "generator": "categorymembers",
            "gcmtitle": category,
            "gcmtype": "file",
            "gcmlimit": str(min(60, max(20, want * 12))),
            "prop": "imageinfo",
            "iiprop": "url|extmetadata|size|mime",
            "iiurlwidth": str(MAX_PX),
        })
    except Exception as exc:  # noqa: BLE001 - a missing category is not fatal
        print(f"    ! could not read {category}: {exc}")
        return []

    pages = (data.get("query") or {}).get("pages") or []
    out = []
    for page in pages:
        info = (page.get("imageinfo") or [{}])[0]
        if not info:
            continue
        if not str(info.get("mime", "")).startswith("image/"):
            continue
        if str(info.get("mime", "")).endswith("svg+xml"):
            continue
        meta = info.get("extmetadata") or {}
        licence = strip_html((meta.get("LicenseShortName") or {}).get("value", ""))
        if not licence_ok(licence):
            continue
        width, height = info.get("width", 0), info.get("height", 0)
        if width < 800 or height < 500:
            continue
        # Prefer landscape: a stream assessment photo looks along a channel.
        # Plant close-ups are usually portrait, so allow those through.
        if height > width and not ALLOW_PORTRAIT:
            continue
        out.append({
            "title": page.get("title", ""),
            "thumb": info.get("thumburl") or info.get("url"),
            "descriptionurl": info.get("descriptionurl", ""),
            "licence": licence,
            "licence_url": strip_html((meta.get("LicenseUrl") or {}).get("value", "")),
            "author": strip_html((meta.get("Artist") or {}).get("value", "")) or "unknown",
            "description": strip_html(
                (meta.get("ImageDescription") or {}).get("value", "")
            )[:200],
        })
    return out


def download(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read()


def save_resized(raw: bytes, path: Path) -> tuple[int, int]:
    image = Image.open(io.BytesIO(raw))
    image = image.convert("RGB")
    if max(image.size) > MAX_PX:
        image.thumbnail((MAX_PX, MAX_PX), Image.LANCZOS)
    image.save(path, format="JPEG", quality=88, optimize=True)
    return image.size


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--topup", action="store_true",
                        help="fetch only the categories the first pass missed")
    parser.add_argument("--pace", type=float, default=0.4)
    parser.add_argument("--allow-portrait", action="store_true")
    args = parser.parse_args()

    global ALLOW_PORTRAIT
    ALLOW_PORTRAIT = args.allow_portrait

    PHOTOS_DIR.mkdir(parents=True, exist_ok=True)
    rows: list[dict] = []
    seen_hashes: set[str] = set()
    seen_titles: set[str] = set()

    targets = TOPUP if args.topup else TARGETS
    if args.topup and MANIFEST_PATH.exists():
        import csv as _csv
        with MANIFEST_PATH.open(encoding="utf-8", newline="") as fh:
            rows = list(_csv.DictReader(fh))
        seen_titles.update(r["commons_title"] for r in rows)

    for slug, category, want, shows in targets:
        print(f"  {category} (want {want})")
        candidates = category_files(category, want)
        taken = 0
        for candidate in candidates:
            if taken >= want:
                break
            if candidate["title"] in seen_titles:
                continue

            name = f"{slug}_{taken + 1:02d}.jpg"
            if args.dry_run:
                print(f"    would take {candidate['title']} [{candidate['licence']}]")
                seen_titles.add(candidate["title"])
                taken += 1
                continue

            try:
                raw = download(candidate["thumb"])
            except Exception as exc:  # noqa: BLE001
                print(f"    ! download failed: {exc}")
                continue

            digest = hashlib.sha256(raw).hexdigest()
            if digest in seen_hashes:
                continue

            try:
                width, height = save_resized(raw, PHOTOS_DIR / name)
            except Exception as exc:  # noqa: BLE001
                print(f"    ! could not convert: {exc}")
                continue

            seen_hashes.add(digest)
            seen_titles.add(candidate["title"])
            taken += 1
            rows.append({
                "filename": name,
                "shows": shows,
                "source_url": candidate["descriptionurl"],
                "author": candidate["author"][:120],
                "licence": candidate["licence"],
                "licence_url": candidate["licence_url"],
                "commons_title": candidate["title"],
                "width": width,
                "height": height,
                "description": candidate["description"],
            })
            print(f"    + {name}  [{candidate['licence']}]  {width}x{height}")
            time.sleep(args.pace)  # be polite to Commons

        if taken < want:
            print(f"    (only {taken} of {want} usable)")

    if args.dry_run:
        return 0

    if args.topup and MANIFEST_PATH.exists():
        with MANIFEST_PATH.open(encoding="utf-8", newline="") as fh:
            rows = list(csv.DictReader(fh)) + rows
    if not rows:
        print("nothing fetched")
        return 1

    # One row per file, newest entry winning, and only for files that exist.
    # Without this a second --topup run re-appends every existing row.
    on_disk = {p.name for p in PHOTOS_DIR.glob("*.jpg")}
    deduped: dict[str, dict] = {}
    for row in rows:
        if row["filename"] in on_disk:
            deduped[row["filename"]] = row
    rows = sorted(deduped.values(), key=lambda r: r["filename"])
    with MANIFEST_PATH.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    print(f"\n{len(rows)} photos in {PHOTOS_DIR}")
    print(f"Manifest: {MANIFEST_PATH}")
    licences: dict[str, int] = {}
    for row in rows:
        licences[row["licence"]] = licences.get(row["licence"], 0) + 1
    for licence, count in sorted(licences.items(), key=lambda kv: -kv[1]):
        print(f"  {count:3d}  {licence}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
