"""Quests: real gaps in the stored data, turned into something worth doing.

The rule this file exists to enforce is that a quest must point at a gap that
actually exists. It is easy to generate endless errands; the value is in only
asking for the visit that would actually improve the dataset, and in saying
plainly why.

Every quest carries the fact behind it - the date of the last visit, the
millimetres that fell, the season that is missing - so a volunteer can judge for
themselves whether it is worth the walk.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any

from .config import DATA_DIR
from .weather import Forecast

RULES_PATH = DATA_DIR / "quest_rules.json"

SEASONS = {12: "winter", 1: "winter", 2: "winter",
           3: "spring", 4: "spring", 5: "spring",
           6: "summer", 7: "summer", 8: "summer",
           9: "autumn", 10: "autumn", 11: "autumn"}

SEWAGE_EVIDENCE = {"sewage": {"Y"}, "pollutedPipes": {"Y"}}


def season_of(moment: datetime) -> str:
    """Meteorological season. All five research cities are northern hemisphere."""
    return SEASONS[moment.month]


@dataclass
class Quest:
    rule_id: str
    name: str
    site_id: str
    site_name: str
    city: str
    priority: int
    why: str
    facts: dict[str, Any] = field(default_factory=dict)
    lat: float | None = None
    lon: float | None = None
    # True when the weather behind this quest was planted for the demo.
    weather_synthetic: bool = False


class QuestRules:
    def __init__(self, doc: dict[str, Any]) -> None:
        self.doc = doc
        self.rules = {r["id"]: r for r in doc.get("rules", [])}

    def threshold(self, rule_id: str, key: str, default: float) -> float:
        for entry in self.rules.get(rule_id, {}).get("thresholds", []):
            if entry["key"] == key:
                return float(entry["value"])
        return default


def load_rules(path: Path | None = None) -> QuestRules:
    with (path or RULES_PATH).open(encoding="utf-8") as fh:
        return QuestRules(json.load(fh))


@lru_cache
def get_quest_rules() -> QuestRules:
    return load_rules()


@dataclass
class SiteHistory:
    """Everything the quest engine needs to know about one site."""

    site: dict[str, Any]
    visit_dates: list[datetime] = field(default_factory=list)
    observers_by_date: list[tuple[datetime, str]] = field(default_factory=list)
    sewage_reports: list[datetime] = field(default_factory=list)

    @property
    def last_visit(self) -> datetime | None:
        return max(self.visit_dates) if self.visit_dates else None

    @property
    def visits(self) -> int:
        return len(self.visit_dates)


def _quest(rule: dict, history: SiteHistory, why: str, facts: dict,
           forecast: Forecast | None = None) -> Quest:
    site = history.site
    return Quest(
        rule_id=rule["id"],
        name=rule["name"],
        site_id=site.get("id", ""),
        site_name=site.get("name", ""),
        city=site.get("city", ""),
        priority=int(rule.get("priority", 5)),
        why=why,
        facts=facts,
        lat=site.get("lat"),
        lon=site.get("lon"),
        weather_synthetic=bool(forecast.synthetic) if forecast else False,
    )


def for_site(
    history: SiteHistory,
    forecast: Forecast | None = None,
    rules: QuestRules | None = None,
    now: datetime | None = None,
) -> list[Quest]:
    """Every quest this one site currently justifies, most urgent first."""
    rules = rules or get_quest_rules()
    now = now or datetime.now(timezone.utc)
    site = history.site
    found: list[Quest] = []

    # --- (a) nobody has been here for a while -----------------------------
    rule = rules.rules.get("stale_site")
    if rule and history.last_visit:
        days = (now - history.last_visit).days
        if days >= rules.threshold("stale_site", "days_since_last_visit", 30):
            found.append(_quest(rule, history,
                rule["why_template"].format(
                    days=days, last_date=history.last_visit.strftime("%d %B %Y")),
                {"days_since_last_visit": days,
                 "last_visit": history.last_visit.isoformat()}))

    # --- (b) check after the rain -----------------------------------------
    rule = rules.rules.get("after_rain")
    if rule and forecast and forecast.available:
        within = rules.threshold("after_rain", "reports_within_days", 90)
        cutoff = now - timedelta(days=within)
        recent_reports = [d for d in history.sewage_reports if d >= cutoff]
        rain = forecast.rain_mm_past_48h
        if (rain >= rules.threshold("after_rain", "rain_mm_past_48h", 15)
                and len(recent_reports) >= rules.threshold(
                    "after_rain", "sewage_reports", 1)):
            found.append(_quest(rule, history,
                rule["why_template"].format(rain=f"{rain:.0f}",
                                            reports=len(recent_reports)),
                {"rain_mm_past_48h": rain,
                 "sewage_reports": len(recent_reports),
                 "reports_within_days": int(within)},
                forecast))

    # --- (c) this season has no record ------------------------------------
    rule = rules.rules.get("missing_season")
    if rule and history.visits:
        season = season_of(now)
        this_season = [d for d in history.visit_dates
                       if season_of(d) == season and (now - d).days < 365]
        if not this_season:
            found.append(_quest(rule, history,
                rule["why_template"].format(
                    site=site.get("name", "this site"), season=season),
                {"season": season, "visits_this_season": 0}))

    # --- (d) a second opinion would help ----------------------------------
    rule = rules.rules.get("second_opinion")
    if rule and history.observers_by_date:
        within = rules.threshold("second_opinion", "within_days", 14)
        cutoff = now - timedelta(days=within)
        recent = [(d, who) for d, who in history.observers_by_date if d >= cutoff]
        observers = {who for _, who in recent if who}
        if recent and len(observers) == 1:
            latest = max(d for d, _ in recent)
            found.append(_quest(rule, history,
                rule["why_template"].format(
                    site=site.get("name", "this site"),
                    last_date=latest.strftime("%d %B %Y")),
                {"distinct_observers": 1,
                 "within_days": int(within),
                 "last_visit": latest.isoformat()}))

    found.sort(key=lambda q: q.priority)
    return found


def rank(quests: list[Quest], limit: int | None = None) -> list[Quest]:
    """Most urgent first, and never more than one quest per site.

    A volunteer standing at a stream wants one clear reason to be there, not
    four competing ones.
    """
    best: dict[str, Quest] = {}
    for quest in sorted(quests, key=lambda q: q.priority):
        best.setdefault(quest.site_id, quest)
    ordered = sorted(best.values(), key=lambda q: (q.priority, q.site_name))
    return ordered[:limit] if limit else ordered
