"""Health-card aggregation, the weather cache's offline fallback, and measures."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest
from sqlmodel import Session

from app.health_card import build as build_card
from app.measures import get_measures
from app.models import WeatherCache, get_engine
from app.questions import get_questions
from app.weather import get_forecast

NOW = datetime(2026, 9, 24, 12, 0, tzinfo=timezone.utc)


def observation(overall: str, answers: dict[str, list[str]], days_ago: float = 1.0,
                synthetic: bool = True, obs_id: str = "o1", emotions=None) -> dict:
    return {
        "id": obs_id,
        "overall": overall,
        "recorded_at": NOW - timedelta(days=days_ago),
        "synthetic": synthetic,
        "emotions": emotions or {},
        "answers": [{"question_id": q, "codes": c} for q, c in answers.items()],
    }


@pytest.fixture
def card_parts():
    return get_questions(), get_measures()


SITE = {"id": "C1", "name": "Exploratório", "city": "Coimbra"}


# --------------------------------------------------------------------------
# Health card
# --------------------------------------------------------------------------

def test_a_site_with_no_visits_says_so_rather_than_guessing(card_parts):
    questions, measures = card_parts
    card = build_card(SITE, [], questions, measures)

    assert card.visits == 0
    assert card.latest_overall is None
    assert card.completeness == 0.0
    assert card.completeness_label == "No data yet"
    assert all(s.status == "UNKNOWN" for s in card.sections)


def test_a_clean_site_reads_as_good(card_parts):
    questions, measures = card_parts
    card = build_card(SITE, [observation("GOOD", {
        "channelType": ["NAT"], "bankType": ["NAT"],
    })], questions, measures)

    channel = next(s for s in card.sections if s.section_id == "channel")
    assert channel.status == "GOOD"
    assert channel.answered == 2
    assert card.problems == []


def test_a_concrete_site_reads_as_poor_and_names_the_problems(card_parts):
    questions, measures = card_parts
    card = build_card(SITE, [observation("POOR", {
        "channelType": ["ART"], "bankType": ["ART"], "channelForm": ["U"],
    })], questions, measures)

    channel = next(s for s in card.sections if s.section_id == "channel")
    assert channel.status == "POOR"
    names = {p["name"] for p in card.problems}
    assert "Paved or hardened banks" in names
    assert "Concrete or artificial bed" in names


def test_the_latest_visit_wins_when_answers_change(card_parts):
    """A stream that was concreted last year and restored this year reads as
    restored, not as an average of the two."""
    questions, measures = card_parts
    card = build_card(SITE, [
        observation("POOR", {"channelType": ["ART"]}, days_ago=60, obs_id="old"),
        observation("GOOD", {"channelType": ["NAT"]}, days_ago=1, obs_id="new"),
    ], questions, measures)

    assert card.latest_overall == "GOOD"
    assert "Concrete or artificial bed" not in {p["name"] for p in card.problems}


def test_the_card_counts_visits_and_dates_them(card_parts):
    questions, measures = card_parts
    card = build_card(SITE, [
        observation("GOOD", {"channelType": ["NAT"]}, days_ago=30, obs_id="a"),
        observation("GOOD", {"channelType": ["NAT"]}, days_ago=2, obs_id="b"),
    ], questions, measures)

    assert card.visits == 2
    assert card.last_visit == NOW - timedelta(days=2)
    assert card.first_visit == NOW - timedelta(days=30)
    assert [h["observation_id"] for h in card.overall_history] == ["a", "b"]


def test_completeness_reflects_how_much_has_been_answered(card_parts):
    questions, measures = card_parts
    thin = build_card(SITE, [observation("GOOD", {"channelType": ["NAT"]})],
                      questions, measures)
    assert 0 < thin.completeness < 0.1
    assert thin.completeness_label == "Thin - more visits needed"


def test_emotions_are_averaged_across_visits(card_parts):
    questions, measures = card_parts
    card = build_card(SITE, [
        observation("GOOD", {}, obs_id="a", emotions={"joy": 4, "anger": 0}),
        observation("POOR", {}, obs_id="b", emotions={"joy": 2, "anger": 2}),
    ], questions, measures)

    assert card.emotions["joy"] == 3.0
    assert card.emotions["anger"] == 1.0


def test_real_and_synthetic_visits_are_counted_separately(card_parts):
    questions, measures = card_parts
    card = build_card(SITE, [
        observation("GOOD", {}, obs_id="a", synthetic=True),
        observation("GOOD", {}, obs_id="b", synthetic=False),
    ], questions, measures)

    assert card.synthetic_count == 1
    assert card.real_count == 1


def test_the_card_always_carries_the_indicator_disclaimer(card_parts):
    questions, measures = card_parts
    card = build_card(SITE, [observation("GOOD", {"channelType": ["NAT"]})],
                      questions, measures)
    assert "not a validated ecological index" in card.disclaimer


# --------------------------------------------------------------------------
# Weather cache
# --------------------------------------------------------------------------

def _payload(rain_per_hour: float = 0.5, temp: float = 18.0) -> dict:
    # Anchored to the real clock, not the fixed NOW above: the parser slices the
    # window from the actual current time, so a payload pinned to a past date
    # yields fewer than 48 future hours and the test drifts as days pass.
    start = datetime.now(timezone.utc)
    hours = [(start + timedelta(hours=h)).strftime("%Y-%m-%dT%H:00") for h in range(72)]
    return {
        "hourly": {
            "time": hours,
            "precipitation": [rain_per_hour] * 72,
            "temperature_2m": [temp] * 72,
        }
    }


@pytest.fixture
def session(client):
    """A session on the test database. `client` sets the engine up."""
    with Session(get_engine()) as session:
        yield session


def test_a_fresh_cache_entry_is_used_without_touching_the_network(session):
    session.add(WeatherCache(site_id="C1", payload_json=json.dumps(_payload()),
                             fetched_at=datetime.now(timezone.utc)))
    session.commit()

    forecast = get_forecast(session, "C1", 40.2, -8.4, allow_network=False)
    assert forecast.available is True
    assert forecast.stale is False
    assert forecast.rain_mm_48h == pytest.approx(24.0, abs=0.5)


def test_offline_falls_back_to_a_stale_entry_and_says_it_is_stale(session):
    old = datetime.now(timezone.utc) - timedelta(hours=9)
    session.add(WeatherCache(site_id="C1", payload_json=json.dumps(_payload()),
                             fetched_at=old))
    session.commit()

    forecast = get_forecast(session, "C1", 40.2, -8.4,
                            cache_seconds=3600, allow_network=False)
    assert forecast.available is True
    assert forecast.stale is True
    assert forecast.age_seconds > 3600
    assert forecast.fetched_at is not None, "the UI needs the timestamp to show"
    assert "last forecast" in forecast.error


def test_offline_with_nothing_cached_reports_unavailable_rather_than_zero(session):
    forecast = get_forecast(session, "NEVER-SEEN", 40.2, -8.4, allow_network=False)
    assert forecast.available is False
    assert forecast.rain_mm_48h == 0.0
    assert "nothing is cached" in forecast.error


def test_a_site_without_coordinates_is_handled(session):
    forecast = get_forecast(session, "C1", None, None, allow_network=False)
    assert forecast.available is False
    assert "coordinates" in forecast.error


def test_a_planted_demo_forecast_is_reported_as_synthetic(session):
    payload = {**_payload(), "_streamlens_synthetic": True}
    session.add(WeatherCache(site_id="C1", payload_json=json.dumps(payload),
                             fetched_at=datetime.now(timezone.utc)))
    session.commit()

    forecast = get_forecast(session, "C1", 40.2, -8.4, allow_network=False)
    assert forecast.synthetic is True
    assert "DEMO FORECAST" in forecast.summary


# --------------------------------------------------------------------------
# Measures lookup
# --------------------------------------------------------------------------

def test_answers_map_to_the_problems_they_indicate():
    measures = get_measures()
    found = measures.problems_for_answers({"bankType": {"ART"}, "sewage": {"Y"}})
    assert {p["id"] for p in found} == {"hardened_banks", "sewage"}


def test_a_clean_answer_set_reports_no_problems():
    measures = get_measures()
    assert measures.problems_for_answers({"bankType": {"NAT"}, "sewage": {"N"}}) == []


def test_measures_are_returned_for_a_problem():
    measures = get_measures()
    found = measures.measures_for(["barriers"])
    assert {m["id"] for m in found} == {"remove_barriers", "pass_barriers"}


def test_a_measure_addressing_several_problems_is_offered_first():
    measures = get_measures()
    found = measures.measures_for(["channelised", "no_instream_habitat"])
    assert len(found[0]["addresses"]) >= 2


def test_every_measure_cites_a_page_and_a_licence():
    measures = get_measures()
    for measure in measures.measures.values():
        assert measure["source"]["page"] > 0
        assert measure["source"]["doi"]
        assert measure["source"]["licence"] == "CC-BY-4.0"


def test_what_is_ours_is_marked_as_ours():
    """The catalogue does not tag measures with health co-benefits, so ours
    must not be presented as though it did."""
    measures = get_measures()
    for measure in measures.measures.values():
        assert "project judgement" in measure["authored_by_us"]["health_cobenefits"]


def test_every_problem_points_only_at_measures_that_exist():
    measures = get_measures()
    for problem in measures.problems.values():
        for measure_id in problem["measures"]:
            assert measure_id in measures.measures, measure_id
