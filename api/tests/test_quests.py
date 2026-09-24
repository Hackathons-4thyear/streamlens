"""Quest generation: each type firing, and each type staying quiet.

A quest that fires when there is no real gap is worse than no quest at all - it
sends somebody out for nothing and teaches them to ignore the next one. So each
rule is tested in both directions.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.quests import SiteHistory, for_site, get_quest_rules, rank, season_of
from app.weather import Forecast

# A fixed autumn date, so the season rule is deterministic.
NOW = datetime(2026, 9, 24, 12, 0, tzinfo=timezone.utc)

SITE = {"id": "C1", "name": "Exploratório", "city": "Coimbra",
        "lat": 40.19787, "lon": -8.42865}


def days_ago(n: float) -> datetime:
    return NOW - timedelta(days=n)


def history(visits=(), observers=(), sewage=()) -> SiteHistory:
    return SiteHistory(
        site=SITE,
        visit_dates=list(visits),
        observers_by_date=list(observers),
        sewage_reports=list(sewage),
    )


def forecast(past_rain: float = 0.0, synthetic: bool = False) -> Forecast:
    return Forecast(site_id="C1", rain_mm_past_48h=past_rain, available=True,
                    synthetic=synthetic)


def ids(quests) -> set[str]:
    return {q.rule_id for q in quests}


# --------------------------------------------------------------------------
# (a) stale site
# --------------------------------------------------------------------------

def test_stale_site_fires_after_thirty_days():
    quests = for_site(history(visits=[days_ago(31)]), now=NOW)
    assert "stale_site" in ids(quests)


def test_stale_site_fires_exactly_on_the_threshold():
    quests = for_site(history(visits=[days_ago(30)]), now=NOW)
    assert "stale_site" in ids(quests)


def test_stale_site_stays_quiet_a_day_early():
    quests = for_site(history(visits=[days_ago(29)]), now=NOW)
    assert "stale_site" not in ids(quests)


def test_stale_site_uses_the_most_recent_visit():
    """An old visit does not make a site stale if somebody went last week."""
    quests = for_site(history(visits=[days_ago(200), days_ago(3)]), now=NOW)
    assert "stale_site" not in ids(quests)


def test_a_site_nobody_has_ever_visited_raises_no_stale_quest():
    """Never-visited is a different problem, and this rule would say
    'the last check was 0 days ago', which is nonsense."""
    quests = for_site(history(), now=NOW)
    assert "stale_site" not in ids(quests)


# --------------------------------------------------------------------------
# (b) after the rain
# --------------------------------------------------------------------------

def test_after_rain_fires_on_rain_plus_a_prior_sewage_report():
    quests = for_site(
        history(visits=[days_ago(5)], sewage=[days_ago(10)]),
        forecast(past_rain=20), now=NOW,
    )
    assert "after_rain" in ids(quests)


def test_after_rain_fires_exactly_at_the_threshold():
    quests = for_site(
        history(visits=[days_ago(5)], sewage=[days_ago(10)]),
        forecast(past_rain=15), now=NOW,
    )
    assert "after_rain" in ids(quests)


def test_after_rain_stays_quiet_just_below_the_threshold():
    quests = for_site(
        history(visits=[days_ago(5)], sewage=[days_ago(10)]),
        forecast(past_rain=14.9), now=NOW,
    )
    assert "after_rain" not in ids(quests)


def test_after_rain_never_fires_on_rain_alone():
    """Rain is not a property of a stream. Without a prior report there is
    nothing specific to go and check."""
    quests = for_site(history(visits=[days_ago(5)]), forecast(past_rain=80), now=NOW)
    assert "after_rain" not in ids(quests)


def test_after_rain_ignores_a_sewage_report_from_last_year():
    quests = for_site(
        history(visits=[days_ago(5)], sewage=[days_ago(120)]),
        forecast(past_rain=30), now=NOW,
    )
    assert "after_rain" not in ids(quests)


def test_after_rain_needs_a_forecast_at_all():
    quests = for_site(
        history(visits=[days_ago(5)], sewage=[days_ago(10)]),
        Forecast(site_id="C1", available=False), now=NOW,
    )
    assert "after_rain" not in ids(quests)


def test_a_quest_says_when_its_weather_was_planted_for_the_demo():
    quests = for_site(
        history(visits=[days_ago(5)], sewage=[days_ago(10)]),
        forecast(past_rain=30, synthetic=True), now=NOW,
    )
    quest = next(q for q in quests if q.rule_id == "after_rain")
    assert quest.weather_synthetic is True


def test_the_after_rain_quest_states_the_millimetres_and_the_count():
    quests = for_site(
        history(visits=[days_ago(5)], sewage=[days_ago(3), days_ago(9)]),
        forecast(past_rain=27), now=NOW,
    )
    quest = next(q for q in quests if q.rule_id == "after_rain")
    assert "27" in quest.why
    assert "2 report" in quest.why
    assert quest.facts["rain_mm_past_48h"] == 27


# --------------------------------------------------------------------------
# (c) missing season
# --------------------------------------------------------------------------

def test_season_boundaries_are_meteorological():
    assert season_of(datetime(2026, 12, 1)) == "winter"
    assert season_of(datetime(2026, 3, 1)) == "spring"
    assert season_of(datetime(2026, 6, 30)) == "summer"
    assert season_of(datetime(2026, 9, 24)) == "autumn"


def test_missing_season_fires_when_this_season_has_no_visit():
    # July is summer; NOW is autumn.
    quests = for_site(history(visits=[datetime(2026, 7, 15, tzinfo=timezone.utc)]),
                      now=NOW)
    assert "missing_season" in ids(quests)


def test_missing_season_stays_quiet_when_this_season_is_covered():
    quests = for_site(history(visits=[days_ago(5)]), now=NOW)
    assert "missing_season" not in ids(quests)


def test_missing_season_needs_the_site_to_have_been_visited_at_all():
    assert "missing_season" not in ids(for_site(history(), now=NOW))


def test_a_visit_in_the_same_season_last_year_does_not_count():
    """The point is a gap in the current record, not that the season was ever
    covered at some point in history."""
    quests = for_site(history(visits=[NOW - timedelta(days=366)]), now=NOW)
    assert "missing_season" in ids(quests)


# --------------------------------------------------------------------------
# (d) second opinion
# --------------------------------------------------------------------------

def test_second_opinion_fires_for_a_lone_recent_observer():
    quests = for_site(
        history(visits=[days_ago(3)], observers=[(days_ago(3), "client-a")]),
        now=NOW,
    )
    assert "second_opinion" in ids(quests)


def test_second_opinion_stays_quiet_when_two_people_already_went():
    quests = for_site(
        history(visits=[days_ago(3), days_ago(5)],
                observers=[(days_ago(3), "client-a"), (days_ago(5), "client-b")]),
        now=NOW,
    )
    assert "second_opinion" not in ids(quests)


def test_second_opinion_ignores_an_old_lone_visit():
    quests = for_site(
        history(visits=[days_ago(40)], observers=[(days_ago(40), "client-a")]),
        now=NOW,
    )
    assert "second_opinion" not in ids(quests)


def test_the_same_person_twice_is_still_one_opinion():
    quests = for_site(
        history(visits=[days_ago(2), days_ago(6)],
                observers=[(days_ago(2), "client-a"), (days_ago(6), "client-a")]),
        now=NOW,
    )
    assert "second_opinion" in ids(quests)


# --------------------------------------------------------------------------
# Ranking and presentation
# --------------------------------------------------------------------------

def test_a_site_offers_only_its_most_urgent_quest_in_the_list():
    """A volunteer standing at a stream wants one clear reason to be there."""
    stale_and_seasonless = for_site(
        history(visits=[datetime(2026, 5, 1, tzinfo=timezone.utc)]), now=NOW
    )
    assert len(stale_and_seasonless) >= 2, "this site genuinely has two gaps"
    assert len(rank(stale_and_seasonless)) == 1
    assert rank(stale_and_seasonless)[0].rule_id == "missing_season", "the higher priority"


def test_ranking_orders_by_priority_across_sites():
    a = SiteHistory(site={**SITE, "id": "A", "name": "A"},
                    visit_dates=[days_ago(3)],
                    observers_by_date=[(days_ago(3), "one")])
    b = SiteHistory(site={**SITE, "id": "B", "name": "B"},
                    visit_dates=[days_ago(5)], sewage_reports=[days_ago(5)])
    quests = for_site(a, now=NOW) + for_site(b, forecast(past_rain=30), now=NOW)
    ordered = rank(quests)
    assert ordered[0].rule_id == "after_rain", "rain is the time-critical one"


def test_every_quest_explains_itself_in_one_plain_sentence():
    quests = for_site(
        history(visits=[days_ago(40)], observers=[(days_ago(40), "a")],
                sewage=[days_ago(10)]),
        forecast(past_rain=30), now=NOW,
    )
    assert quests, "this history should raise something"
    for quest in quests:
        assert quest.why, quest.rule_id
        # A sentence may open with a number - "27 mm of rain fell here..."
        assert quest.why[0].isupper() or quest.why[0].isdigit(), quest.why
        assert quest.why.rstrip().endswith("."), quest.why
        assert quest.site_name in quest.why or any(
            ch.isdigit() for ch in quest.why
        ), "a quest names the site or the number behind it"


@pytest.mark.parametrize("rule_id", [
    "stale_site", "after_rain", "missing_season", "second_opinion",
])
def test_the_four_required_rules_exist_and_are_documented(rule_id):
    rule = get_quest_rules().rules[rule_id]
    assert rule["plain_language_condition"]
    assert rule["why_template"]
    for threshold in rule.get("thresholds", []):
        assert threshold.get("source"), f"{rule_id}/{threshold['key']}"
        assert threshold.get("source_note"), f"{rule_id}/{threshold['key']}"
