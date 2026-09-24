"""Scoring, the leaderboard and the wellbeing mirror.

Three deliberate constraints run through this file:

1. **Nothing is scored by volume.** No points for how many questions were
   answered or how many records were submitted. See the `why_not_volume` block
   in data/points_rules.json: paying per submission pays for rubbish.
2. **The leaderboard is teams only.** Ranking individuals on a scientific
   dataset rewards whoever submits most, and the fastest way to submit most is
   to stop looking properly. Teams also make a coverage map meaningful.
3. **Group statistics have a minimum count.** A "community" figure computed from
   three people is not a community figure, and with a small enough group it
   identifies them. `MIN_GROUP` is enforced here, not only in the interface.
"""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any

from .config import DATA_DIR

POINTS_PATH = DATA_DIR / "points_rules.json"

# No community statistic is published for a group smaller than this. Stated in
# the payload as well, so the interface cannot quietly drop the caveat.
MIN_GROUP = 10

# A "team" of one person is an individual ranking by the back door, which is the
# thing the team-only rule exists to prevent. Such teams are computed but held
# back from the published ranking, and the response says how many were held.
MIN_TEAM_MEMBERS = 2

POSITIVE_EMOTIONS = ("joy", "serenity")


class PointsRules:
    def __init__(self, doc: dict[str, Any]) -> None:
        self.doc = doc
        self.rules = {r["id"]: r for r in doc.get("rules", [])}

    @property
    def daily_cap(self) -> int:
        return int(self.doc.get("daily_cap", {}).get("points", 60))

    def points_for(self, rule_id: str) -> int:
        return int(self.rules.get(rule_id, {}).get("points", 0))

    def threshold(self, rule_id: str, key: str, default: float) -> float:
        for entry in self.rules.get(rule_id, {}).get("thresholds", []):
            if entry["key"] == key:
                return float(entry["value"])
        return default


def load_points_rules(path: Path | None = None) -> PointsRules:
    with (path or POINTS_PATH).open(encoding="utf-8") as fh:
        return PointsRules(json.load(fh))


@lru_cache
def get_points_rules() -> PointsRules:
    return load_points_rules()


@dataclass
class ScoredObservation:
    """What one assessment earned, and exactly why."""

    observation_id: str
    site_id: str
    client_id: str
    recorded_at: datetime
    points: int = 0
    awards: list[dict] = field(default_factory=list)
    capped_from: int | None = None


@dataclass
class ObservationInput:
    """The facts about one stored assessment that scoring depends on."""

    id: str
    site_id: str
    client_id: str
    recorded_at: datetime
    photos_ok: list[bool] = field(default_factory=list)
    answers: dict[str, list[str]] = field(default_factory=dict)
    completed_quest: str | None = None
    synthetic: bool = False
    team: str = ""


def agreement_between(a: dict[str, list[str]], b: dict[str, list[str]]) -> tuple[int, float]:
    """Shared questions, and the share of them where the two answers match."""
    shared = set(a) & set(b)
    if not shared:
        return 0, 0.0
    matches = sum(1 for q in shared if set(a[q]) == set(b[q]))
    return len(shared), matches / len(shared)


def score_observations(
    observations: list[ObservationInput],
    rules: PointsRules | None = None,
) -> list[ScoredObservation]:
    """Score every assessment, then apply the per-person daily cap."""
    rules = rules or get_points_rules()
    by_site: dict[str, list[ObservationInput]] = defaultdict(list)
    for observation in observations:
        by_site[observation.site_id].append(observation)

    within_days = rules.threshold("observer_agreement", "within_days", 14)
    min_shared = rules.threshold("observer_agreement", "min_shared_questions", 3)
    min_agree = rules.threshold("observer_agreement", "min_agreement", 0.6)

    scored: list[ScoredObservation] = []
    for observation in observations:
        entry = ScoredObservation(
            observation_id=observation.id,
            site_id=observation.site_id,
            client_id=observation.client_id,
            recorded_at=observation.recorded_at,
        )

        if len(observation.photos_ok) >= 2:
            points = rules.points_for("both_photos")
            entry.points += points
            entry.awards.append({"rule_id": "both_photos", "points": points,
                                 "detail": "Upstream and downstream both present."})

        good_photos = sum(1 for ok in observation.photos_ok if ok)
        if good_photos:
            points = rules.points_for("photo_quality") * good_photos
            entry.points += points
            entry.awards.append({
                "rule_id": "photo_quality", "points": points,
                "detail": f"{good_photos} photo(s) passed the blur and brightness checks.",
            })

        if observation.completed_quest:
            points = rules.points_for("quest_completed")
            entry.points += points
            entry.awards.append({
                "rule_id": "quest_completed", "points": points,
                "detail": f"Filled the '{observation.completed_quest}' gap.",
            })

        # Agreement with an independent visitor to the same site.
        best: tuple[int, float, str] | None = None
        for other in by_site[observation.site_id]:
            if other.id == observation.id or other.client_id == observation.client_id:
                continue
            gap = abs((other.recorded_at - observation.recorded_at).days)
            if gap > within_days:
                continue
            shared, share = agreement_between(observation.answers, other.answers)
            if shared >= min_shared and share >= min_agree:
                if best is None or share > best[1]:
                    best = (shared, share, other.id)
        if best:
            points = rules.points_for("observer_agreement")
            entry.points += points
            entry.awards.append({
                "rule_id": "observer_agreement", "points": points,
                "detail": f"Agreed with another visitor on {best[1] * 100:.0f}% of "
                          f"{best[0]} shared questions.",
            })

        scored.append(entry)

    # --- the daily cap, per person per day --------------------------------
    cap = rules.daily_cap
    running: dict[tuple[str, str], int] = defaultdict(int)
    for entry in sorted(scored, key=lambda e: e.recorded_at):
        key = (entry.client_id, entry.recorded_at.date().isoformat())
        remaining = cap - running[key]
        if entry.points > remaining:
            entry.capped_from = entry.points
            entry.points = max(0, remaining)
        running[key] += entry.points
    return scored


# --------------------------------------------------------------------------
# Teams
# --------------------------------------------------------------------------

@dataclass
class TeamStanding:
    team: str
    points: int
    sites_covered: int
    observations: int
    members: int
    cities: list[str] = field(default_factory=list)


def leaderboard(
    observations: list[ObservationInput],
    scored: list[ScoredObservation],
    city: str | None = None,
    site_city: dict[str, str] | None = None,
) -> list[TeamStanding]:
    """Teams only. Individuals are never ranked.

    An individual ranking on a scientific dataset rewards whoever submits most,
    and the fastest way to submit most is to stop looking properly.
    """
    site_city = site_city or {}
    points_by_id = {s.observation_id: s.points for s in scored}

    teams: dict[str, dict] = defaultdict(
        lambda: {"points": 0, "sites": set(), "members": set(),
                 "observations": 0, "cities": set()}
    )
    for observation in observations:
        team = (observation.team or "").strip()
        if not team:
            continue
        where = site_city.get(observation.site_id, "")
        if city and where.lower() != city.lower():
            continue
        entry = teams[team]
        entry["points"] += points_by_id.get(observation.id, 0)
        entry["sites"].add(observation.site_id)
        entry["members"].add(observation.client_id)
        entry["observations"] += 1
        if where:
            entry["cities"].add(where)

    standings = [
        TeamStanding(
            team=name,
            points=data["points"],
            sites_covered=len(data["sites"]),
            observations=data["observations"],
            members=len(data["members"]),
            cities=sorted(data["cities"]),
        )
        for name, data in teams.items()
    ]
    ranked = [t for t in standings if t.members >= MIN_TEAM_MEMBERS]
    ranked.sort(key=lambda t: (-t.points, -t.sites_covered, t.team))
    return ranked


def withheld_teams(
    observations: list[ObservationInput],
    scored: list[ScoredObservation],
    city: str | None = None,
    site_city: dict[str, str] | None = None,
) -> int:
    """How many teams were too small to publish. Shown, never silently dropped."""
    site_city = site_city or {}
    members: dict[str, set[str]] = defaultdict(set)
    for observation in observations:
        team = (observation.team or "").strip()
        if not team:
            continue
        where = site_city.get(observation.site_id, "")
        if city and where.lower() != city.lower():
            continue
        members[team].add(observation.client_id)
    return sum(1 for people in members.values() if len(people) < MIN_TEAM_MEMBERS)


def coverage(
    observations: list[ObservationInput],
    all_sites: list[dict],
    since: datetime,
    city: str | None = None,
) -> dict:
    """Which sites got a visit since `since`. The opening shot of the video."""
    visited = {
        o.site_id for o in observations if o.recorded_at >= since
    }
    sites = [s for s in all_sites
             if not city or s.get("city", "").lower() == city.lower()]
    rows = [
        {
            "site_id": s["id"],
            "site_name": s.get("name", ""),
            "city": s.get("city", ""),
            "lat": s.get("lat"),
            "lon": s.get("lon"),
            "visited": s["id"] in visited,
        }
        for s in sites
    ]
    covered = sum(1 for r in rows if r["visited"])
    return {
        "since": since.isoformat(),
        "city": city,
        "total_sites": len(rows),
        "covered": covered,
        "share": round(covered / len(rows), 3) if rows else 0.0,
        "sites": rows,
    }


# --------------------------------------------------------------------------
# Wellbeing mirror
# --------------------------------------------------------------------------

@dataclass
class WellbeingMirror:
    available: bool
    scope: str  # "personal" | "community"
    people: int
    visits: int
    by_rating: dict[str, dict] = field(default_factory=dict)
    headline: str = ""
    caveat: str = ""
    min_group: int = MIN_GROUP


def wellbeing(
    records: list[tuple[str, str, dict[str, int]]],
    scope: str = "personal",
) -> WellbeingMirror:
    """How people felt, split by the rating they themselves gave.

    `records` is (client_id, overall_rating, emotions).

    This is descriptive and nothing more. It reports what people recorded
    feeling at streams they judged differently. It is not a health measure, it
    is not evidence that a stream caused a feeling, and the wording must never
    suggest either.
    """
    people = {client for client, _, _ in records if client}
    if scope == "community" and len(people) < MIN_GROUP:
        return WellbeingMirror(
            available=False,
            scope=scope,
            people=len(people),
            visits=len(records),
            caveat=(
                f"A community view needs at least {MIN_GROUP} people. This group has "
                f"{len(people)}. Publishing a figure from fewer would say more about "
                "the individuals than about the community."
            ),
        )

    buckets: dict[str, list[dict[str, int]]] = defaultdict(list)
    for _, rating, emotions in records:
        if rating and emotions:
            buckets[rating].append(emotions)

    by_rating: dict[str, dict] = {}
    for rating, entries in buckets.items():
        positive = sum(
            1 for e in entries
            if max((e.get(k, 0) for k in POSITIVE_EMOTIONS), default=0) >= 3
        )
        by_rating[rating] = {
            "visits": len(entries),
            "positive_share": round(positive / len(entries), 3) if entries else 0.0,
            "averages": {
                name: round(sum(e.get(name, 0) for e in entries) / len(entries), 2)
                for name in ("joy", "serenity", "anger", "fear")
            },
        }

    headline = ""
    good = by_rating.get("GOOD")
    poor = by_rating.get("POOR")
    if good and poor and good["visits"] and poor["visits"]:
        headline = (
            f"Calm or joy was recorded on {good['positive_share'] * 100:.0f}% of "
            f"visits to streams rated Good, and {poor['positive_share'] * 100:.0f}% "
            "of visits to streams rated Poor."
        )

    return WellbeingMirror(
        available=bool(by_rating),
        scope=scope,
        people=len(people),
        visits=len(records),
        by_rating=by_rating,
        headline=headline,
        caveat=(
            "This describes what people recorded feeling, beside streams they "
            "themselves rated. It is not a health measurement, and it does not show "
            "that a stream caused a feeling - people who dislike a place may rate it "
            "lower for the same reasons they enjoy it less."
        ),
    )
