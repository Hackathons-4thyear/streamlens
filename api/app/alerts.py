"""The 48-hour alert engine.

A rules engine, deliberately not a model. Every alert is the arithmetic in
data/alert_rules.json applied to a forecast and to recent citizen answers, and
every alert carries the numbers that produced it, so a reader can check it.

Three things this file will not do:

- it never says water is safe or unsafe, and never diagnoses anything;
- it never fires on weather alone, because weather is not a property of a
  stream: every rule also needs a citizen observation;
- it never hides its inputs. `triggered_by` lists each threshold, the value
  measured against it, and whether that condition passed.
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

RULES_PATH = DATA_DIR / "alert_rules.json"

OPERATORS = {
    ">=": lambda a, b: a >= b,
    ">": lambda a, b: a > b,
    "<=": lambda a, b: a <= b,
    "<": lambda a, b: a < b,
    "==": lambda a, b: a == b,
}

# Which citizen answers count as evidence for which rule input. Mirrors the
# "from" descriptions in alert_rules.json; kept here because the engine has to
# execute them, and kept narrow so the mapping stays readable.
EVIDENCE = {
    "sewage_reports": [("sewage", {"Y"}), ("pollutedPipes", {"Y"})],
    "standing_reports": [("waterFlow", {"STA", "DRY"})],
    "obstruction_reports": [("dams", {"Y"}), ("fallenBiomass", {"FT", "FB"})],
}


@dataclass
class Condition:
    key: str
    operator: str
    threshold: float
    value: float | None
    unit: str
    passed: bool
    source: str


@dataclass
class Alert:
    rule_id: str
    name: str
    severity: str
    message: str
    why: str
    conditions: list[Condition] = field(default_factory=list)
    evidence: list[dict] = field(default_factory=list)
    advice_sources: list[dict] = field(default_factory=list)
    forecast_stale: bool = False
    forecast_fetched_at: datetime | None = None


class RuleSet:
    def __init__(self, doc: dict[str, Any]) -> None:
        self.doc = doc
        self.rules = doc.get("rules", [])

    @property
    def language_rules(self) -> dict:
        return self.doc.get("language_rules", {})

    @property
    def always_include(self) -> str:
        return self.language_rules.get("always_include", "")

    def threshold(self, rule: dict, key: str) -> dict | None:
        for entry in rule.get("thresholds", []):
            if entry["key"] == key:
                return entry
        return None


def load_rules(path: Path | None = None) -> RuleSet:
    target = path or RULES_PATH
    with target.open(encoding="utf-8") as fh:
        return RuleSet(json.load(fh))


@lru_cache
def get_rules() -> RuleSet:
    return load_rules()


@dataclass
class ObservationEvidence:
    """One citizen answer that a rule may rely on."""

    observation_id: str
    question_id: str
    codes: list[str]
    recorded_at: datetime
    synthetic: bool


def count_evidence(
    key: str,
    evidence: list[ObservationEvidence],
    within_days: int,
    now: datetime | None = None,
) -> tuple[int, list[dict]]:
    """How many recent observations support this rule input, and which."""
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(days=within_days)
    wanted = EVIDENCE.get(key, [])

    matches: list[dict] = []
    seen_observations: set[str] = set()
    for item in evidence:
        recorded = item.recorded_at
        if recorded.tzinfo is None:
            recorded = recorded.replace(tzinfo=timezone.utc)
        if recorded < cutoff:
            continue
        for question_id, codes in wanted:
            if item.question_id == question_id and set(item.codes) & codes:
                matches.append({
                    "observation_id": item.observation_id,
                    "question_id": item.question_id,
                    "codes": sorted(set(item.codes) & codes),
                    "recorded_at": recorded.isoformat(),
                    "synthetic": item.synthetic,
                })
                seen_observations.add(item.observation_id)
    return len(seen_observations), matches


def evaluate(
    forecast: Forecast,
    evidence: list[ObservationEvidence],
    rules: RuleSet | None = None,
    now: datetime | None = None,
) -> list[Alert]:
    """Apply every rule. Returns only the alerts that fired, worst first."""
    rules = rules or get_rules()
    now = now or datetime.now(timezone.utc)
    fired: list[Alert] = []

    for rule in rules.rules:
        # Weather is a required input for all current rules; with no forecast
        # there is nothing to evaluate and we say nothing rather than guess.
        if not forecast.available:
            continue

        values: dict[str, float | None] = {
            "rain_mm_48h": forecast.rain_mm_48h,
            "temp_max_c": forecast.temp_max_c,
        }
        within = rules.threshold(rule, "reports_within_days")
        within_days = int(within["value"]) if within else 14

        conditions: list[Condition] = []
        matched_evidence: list[dict] = []
        all_passed = True

        for entry in rule.get("thresholds", []):
            key = entry["key"]
            if key == "reports_within_days":
                continue

            if key in EVIDENCE:
                count, matches = count_evidence(key, evidence, within_days, now)
                value: float | None = count
                matched_evidence.extend(matches)
            else:
                value = values.get(key)

            operator = OPERATORS.get(entry["operator"], OPERATORS[">="])
            passed = value is not None and operator(value, entry["value"])
            all_passed = all_passed and passed
            conditions.append(Condition(
                key=key,
                operator=entry["operator"],
                threshold=float(entry["value"]),
                value=None if value is None else float(value),
                unit=entry.get("unit", ""),
                passed=bool(passed),
                source=entry.get("source", ""),
            ))

        if not all_passed:
            continue

        filled = {c.key: c.value for c in conditions}
        message = rule["message_template"]
        for key, value in filled.items():
            shown = f"{value:.0f}" if value is not None else "?"
            message = message.replace("{" + key + "}", shown)
        message = message.replace("{reports_within_days}", str(within_days))

        fired.append(Alert(
            rule_id=rule["id"],
            name=rule["name"],
            severity=rule.get("severity", "medium"),
            message=message,
            why=rule.get("why", ""),
            conditions=conditions,
            evidence=matched_evidence,
            advice_sources=rule.get("advice_sources", []),
            forecast_stale=forecast.stale,
            forecast_fetched_at=forecast.fetched_at,
        ))

    order = {"high": 0, "medium": 1, "low": 2}
    fired.sort(key=lambda a: order.get(a.severity, 9))
    return fired
