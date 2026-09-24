"""The alert rules: firing and, just as importantly, not firing.

Every rule is tested at its threshold boundary, because an advisory that fires
one millimetre early is a nuisance and one that fires late is useless. Nothing
here touches the network: forecasts are constructed directly.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.alerts import ObservationEvidence, count_evidence, evaluate, get_rules
from app.weather import Forecast

NOW = datetime(2026, 9, 24, 12, 0, tzinfo=timezone.utc)


def forecast(rain: float = 0.0, temp: float | None = 15.0, **kwargs) -> Forecast:
    return Forecast(site_id="C1", rain_mm_48h=rain, temp_max_c=temp, **kwargs)


def evidence(question_id: str, codes: list[str], days_ago: float = 1.0,
             observation_id: str = "obs-1") -> ObservationEvidence:
    return ObservationEvidence(
        observation_id=observation_id,
        question_id=question_id,
        codes=codes,
        recorded_at=NOW - timedelta(days=days_ago),
        synthetic=True,
    )


def fired(alerts, rule_id: str) -> bool:
    return any(a.rule_id == rule_id for a in alerts)


# --------------------------------------------------------------------------
# Rule (a): sewer overflow — rain >= 20 mm AND a sewage report within 14 days
# --------------------------------------------------------------------------

def test_sewage_rule_fires_when_both_conditions_are_met():
    alerts = evaluate(forecast(rain=25), [evidence("sewage", ["Y"])], now=NOW)
    assert fired(alerts, "sewage_overflow_risk")


def test_sewage_rule_fires_exactly_at_the_rain_threshold():
    alerts = evaluate(forecast(rain=20.0), [evidence("sewage", ["Y"])], now=NOW)
    assert fired(alerts, "sewage_overflow_risk"), "the threshold is inclusive"


def test_sewage_rule_stays_silent_just_below_the_threshold():
    alerts = evaluate(forecast(rain=19.9), [evidence("sewage", ["Y"])], now=NOW)
    assert not fired(alerts, "sewage_overflow_risk")


def test_sewage_rule_never_fires_on_weather_alone():
    """Weather is not a property of a stream. Every rule needs an observation."""
    alerts = evaluate(forecast(rain=100), [], now=NOW)
    assert not fired(alerts, "sewage_overflow_risk")


def test_sewage_rule_ignores_reports_older_than_the_window():
    alerts = evaluate(
        forecast(rain=25), [evidence("sewage", ["Y"], days_ago=15)], now=NOW
    )
    assert not fired(alerts, "sewage_overflow_risk")


def test_a_polluted_pipe_report_also_counts():
    alerts = evaluate(forecast(rain=25), [evidence("pollutedPipes", ["Y"])], now=NOW)
    assert fired(alerts, "sewage_overflow_risk")


def test_a_no_answer_is_not_evidence_of_sewage():
    alerts = evaluate(forecast(rain=25), [evidence("sewage", ["N"])], now=NOW)
    assert not fired(alerts, "sewage_overflow_risk")


# --------------------------------------------------------------------------
# Rule (b): mosquito conditions — temp >= 20 AND standing/dry within 21 days
# --------------------------------------------------------------------------

def test_mosquito_rule_fires_on_warmth_plus_standing_water():
    alerts = evaluate(forecast(temp=24), [evidence("waterFlow", ["STA"])], now=NOW)
    assert fired(alerts, "mosquito_breeding_conditions")


def test_mosquito_rule_fires_exactly_at_the_temperature_threshold():
    alerts = evaluate(forecast(temp=20.0), [evidence("waterFlow", ["STA"])], now=NOW)
    assert fired(alerts, "mosquito_breeding_conditions")


def test_mosquito_rule_stays_silent_just_below_the_threshold():
    alerts = evaluate(forecast(temp=19.9), [evidence("waterFlow", ["STA"])], now=NOW)
    assert not fired(alerts, "mosquito_breeding_conditions")


def test_a_dry_channel_also_counts_as_standing():
    alerts = evaluate(forecast(temp=25), [evidence("waterFlow", ["DRY"])], now=NOW)
    assert fired(alerts, "mosquito_breeding_conditions")


def test_flowing_water_does_not_trigger_the_mosquito_rule():
    alerts = evaluate(forecast(temp=30), [evidence("waterFlow", ["NOR"])], now=NOW)
    assert not fired(alerts, "mosquito_breeding_conditions")


def test_mosquito_rule_ignores_reports_older_than_three_weeks():
    alerts = evaluate(
        forecast(temp=25), [evidence("waterFlow", ["STA"], days_ago=22)], now=NOW
    )
    assert not fired(alerts, "mosquito_breeding_conditions")


# --------------------------------------------------------------------------
# Rule (c): debris watch — rain >= 25 mm AND a barrier or fallen wood
# --------------------------------------------------------------------------

def test_debris_rule_fires_on_rain_plus_a_barrier():
    alerts = evaluate(forecast(rain=30), [evidence("dams", ["Y"])], now=NOW)
    assert fired(alerts, "debris_blockage_watch")


def test_debris_rule_fires_exactly_at_its_threshold():
    alerts = evaluate(forecast(rain=25.0), [evidence("dams", ["Y"])], now=NOW)
    assert fired(alerts, "debris_blockage_watch")


def test_debris_rule_stays_silent_just_below_its_threshold():
    alerts = evaluate(forecast(rain=24.9), [evidence("dams", ["Y"])], now=NOW)
    assert not fired(alerts, "debris_blockage_watch")


def test_fallen_wood_also_counts_as_an_obstruction():
    alerts = evaluate(forecast(rain=30), [evidence("fallenBiomass", ["FT"])], now=NOW)
    assert fired(alerts, "debris_blockage_watch")


def test_the_debris_rule_has_a_longer_memory_than_the_sewage_rule():
    """A weir is a lasting feature; a discharge is an event."""
    old = [evidence("dams", ["Y"], days_ago=45)]
    assert fired(evaluate(forecast(rain=30), old, now=NOW), "debris_blockage_watch")
    assert not fired(
        evaluate(forecast(rain=30), [evidence("sewage", ["Y"], days_ago=45)], now=NOW),
        "sewage_overflow_risk",
    )


# --------------------------------------------------------------------------
# Behaviour common to every rule
# --------------------------------------------------------------------------

def test_no_forecast_means_no_alerts_rather_than_a_guess():
    alerts = evaluate(
        Forecast(site_id="C1", available=False),
        [evidence("sewage", ["Y"]), evidence("dams", ["Y"])],
        now=NOW,
    )
    assert alerts == []


def test_every_alert_shows_the_numbers_that_triggered_it():
    alerts = evaluate(forecast(rain=31.4), [evidence("sewage", ["Y"])], now=NOW)
    alert = next(a for a in alerts if a.rule_id == "sewage_overflow_risk")

    rain = next(c for c in alert.conditions if c.key == "rain_mm_48h")
    assert rain.value == 31.4
    assert rain.threshold == 20.0
    assert rain.passed is True
    assert "31" in alert.message, "the measured value appears in the text"
    assert rain.source, "every threshold names its source"


def test_every_alert_points_at_the_observations_behind_it():
    alerts = evaluate(
        forecast(rain=30), [evidence("sewage", ["Y"], observation_id="obs-42")], now=NOW
    )
    alert = next(a for a in alerts if a.rule_id == "sewage_overflow_risk")
    assert alert.evidence[0]["observation_id"] == "obs-42"
    assert alert.evidence[0]["question_id"] == "sewage"


def test_no_alert_ever_calls_water_safe_or_unsafe():
    """The product rule, enforced on the text that actually reaches a citizen."""
    alerts = evaluate(
        forecast(rain=60, temp=30),
        [evidence("sewage", ["Y"]), evidence("waterFlow", ["STA"]),
         evidence("dams", ["Y"])],
        now=NOW,
    )
    assert len(alerts) == 3, "all three rules should fire on this input"

    banned = get_rules().language_rules["never_say"]
    for alert in alerts:
        lowered = alert.message.lower()
        for word in banned:
            assert word not in lowered, f"{alert.rule_id} says '{word}'"


def test_every_alert_points_the_citizen_at_official_advice():
    alerts = evaluate(
        forecast(rain=60, temp=30),
        [evidence("sewage", ["Y"]), evidence("waterFlow", ["STA"]),
         evidence("dams", ["Y"])],
        now=NOW,
    )
    for alert in alerts:
        assert "Check official local advice." in alert.message


def test_alerts_come_back_worst_first():
    alerts = evaluate(
        forecast(rain=60, temp=30),
        [evidence("sewage", ["Y"]), evidence("waterFlow", ["STA"])],
        now=NOW,
    )
    severities = [a.severity for a in alerts]
    assert severities == sorted(severities, key=lambda s: {"high": 0, "medium": 1}[s])


def test_two_reports_in_one_observation_count_once():
    """A visit that reported both sewage and a pipe is one observation, not two."""
    same = [
        evidence("sewage", ["Y"], observation_id="obs-1"),
        evidence("pollutedPipes", ["Y"], observation_id="obs-1"),
    ]
    count, _ = count_evidence("sewage_reports", same, within_days=14, now=NOW)
    assert count == 1


# --------------------------------------------------------------------------
# The rule file itself
# --------------------------------------------------------------------------

def test_every_threshold_declares_a_source():
    for rule in get_rules().rules:
        for threshold in rule["thresholds"]:
            assert threshold.get("source"), f"{rule['id']}/{threshold['key']}"
            assert threshold.get("source_note"), f"{rule['id']}/{threshold['key']}"


def test_every_rule_is_explained_in_plain_language():
    for rule in get_rules().rules:
        assert rule["plain_language_condition"]
        assert rule["why"]
        assert "Check official local advice." in rule["message_template"]


@pytest.mark.parametrize("rule_id", [
    "sewage_overflow_risk", "mosquito_breeding_conditions", "debris_blockage_watch",
])
def test_the_three_required_rules_exist(rule_id):
    assert any(r["id"] == rule_id for r in get_rules().rules)
