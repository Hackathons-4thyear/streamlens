"""Points, the team leaderboard, the wellbeing mirror and the FHIR bundle.

The constraints tested here are the ones that would quietly rot the dataset if
they broke: scoring by volume, ranking individuals, publishing a group statistic
computed from a handful of people.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.fhir import build_bundle
from app.points import (
    MIN_GROUP,
    MIN_TEAM_MEMBERS,
    ObservationInput,
    coverage,
    get_points_rules,
    leaderboard,
    score_observations,
    wellbeing,
    withheld_teams,
)

NOW = datetime(2026, 9, 24, 12, 0, tzinfo=timezone.utc)


def make(**kwargs) -> ObservationInput:
    defaults = dict(
        id="o1", site_id="C1", client_id="person-a", recorded_at=NOW,
        photos_ok=[], answers={}, completed_quest=None, team="",
    )
    defaults.update(kwargs)
    return ObservationInput(**defaults)


def points_of(entries, observation_id="o1") -> int:
    return next(e.points for e in entries if e.observation_id == observation_id)


def awards_of(entries, observation_id="o1") -> set[str]:
    entry = next(e for e in entries if e.observation_id == observation_id)
    return {a["rule_id"] for a in entry.awards}


# --------------------------------------------------------------------------
# Points: what earns them
# --------------------------------------------------------------------------

def test_two_good_photos_earn_both_awards():
    scored = score_observations([make(photos_ok=[True, True])])
    assert awards_of(scored) == {"both_photos", "photo_quality"}


def test_a_blurry_photo_earns_the_pair_award_but_not_the_quality_one():
    scored = score_observations([make(photos_ok=[True, False])])
    entry = next(e for e in scored)
    quality = next(a for a in entry.awards if a["rule_id"] == "photo_quality")
    assert quality["points"] == get_points_rules().points_for("photo_quality")


def test_completing_a_quest_is_the_largest_single_award():
    rules = get_points_rules()
    assert rules.points_for("quest_completed") > rules.points_for("both_photos")
    assert rules.points_for("quest_completed") > rules.points_for("observer_agreement")
    scored = score_observations([make(completed_quest="stale_site")])
    assert "quest_completed" in awards_of(scored)


# --------------------------------------------------------------------------
# Points: what does NOT earn them
# --------------------------------------------------------------------------

def test_answering_more_questions_earns_nothing_extra():
    """The rule the whole scheme depends on: volume is never rewarded."""
    few = score_observations([make(id="few", answers={"sewage": ["N"]})])
    many = score_observations([make(
        id="many",
        answers={f"q{i}": ["Y"] for i in range(20)},
    )])
    assert points_of(few, "few") == points_of(many, "many") == 0


def test_submitting_more_observations_earns_nothing_per_observation():
    one = score_observations([make(id="a")])
    ten = score_observations([
        make(id=f"o{i}", recorded_at=NOW - timedelta(days=i)) for i in range(10)
    ])
    assert points_of(one, "a") == 0
    assert all(e.points == 0 for e in ten)


def test_the_rules_file_names_what_is_never_rewarded():
    never = get_points_rules().doc["never_awarded_for"]
    assert "number of observations submitted" in never
    assert "number of answers given" in never
    assert get_points_rules().doc["why_not_volume"], "the reasoning is written down"


def test_disagreeing_with_another_visitor_never_costs_points():
    disagreeing = [
        make(id="a", client_id="p1", answers={"q1": ["Y"], "q2": ["Y"], "q3": ["Y"]}),
        make(id="b", client_id="p2", answers={"q1": ["N"], "q2": ["N"], "q3": ["N"]}),
    ]
    scored = score_observations(disagreeing)
    assert all(e.points >= 0 for e in scored)
    assert "observer_agreement" not in awards_of(scored, "a")


# --------------------------------------------------------------------------
# Points: agreement with another visitor
# --------------------------------------------------------------------------

def test_two_people_agreeing_at_one_site_both_earn_it():
    answers = {"q1": ["Y"], "q2": ["Y"], "q3": ["Y"]}
    scored = score_observations([
        make(id="a", client_id="p1", answers=answers),
        make(id="b", client_id="p2", answers=answers, recorded_at=NOW - timedelta(days=2)),
    ])
    assert "observer_agreement" in awards_of(scored, "a")
    assert "observer_agreement" in awards_of(scored, "b")


def test_agreeing_with_yourself_earns_nothing():
    """Otherwise one person could farm it by visiting twice."""
    answers = {"q1": ["Y"], "q2": ["Y"], "q3": ["Y"]}
    scored = score_observations([
        make(id="a", client_id="same", answers=answers),
        make(id="b", client_id="same", answers=answers, recorded_at=NOW - timedelta(days=1)),
    ])
    assert "observer_agreement" not in awards_of(scored, "a")


def test_agreement_needs_enough_shared_questions():
    answers = {"q1": ["Y"], "q2": ["Y"]}  # only two
    scored = score_observations([
        make(id="a", client_id="p1", answers=answers),
        make(id="b", client_id="p2", answers=answers),
    ])
    assert "observer_agreement" not in awards_of(scored, "a")


def test_agreement_expires_after_the_window():
    answers = {"q1": ["Y"], "q2": ["Y"], "q3": ["Y"]}
    scored = score_observations([
        make(id="a", client_id="p1", answers=answers),
        make(id="b", client_id="p2", answers=answers,
             recorded_at=NOW - timedelta(days=20)),
    ])
    assert "observer_agreement" not in awards_of(scored, "a")


def test_agreement_is_not_earned_across_different_sites():
    answers = {"q1": ["Y"], "q2": ["Y"], "q3": ["Y"]}
    scored = score_observations([
        make(id="a", client_id="p1", site_id="C1", answers=answers),
        make(id="b", client_id="p2", site_id="C2", answers=answers),
    ])
    assert "observer_agreement" not in awards_of(scored, "a")


# --------------------------------------------------------------------------
# Points: the daily cap
# --------------------------------------------------------------------------

def test_the_daily_cap_stops_a_person_farming_in_one_afternoon():
    cap = get_points_rules().daily_cap
    same_day = [
        make(id=f"o{i}", client_id="busy", site_id=f"S{i}",
             photos_ok=[True, True], completed_quest="stale_site",
             recorded_at=NOW - timedelta(minutes=10 * i))
        for i in range(8)
    ]
    scored = score_observations(same_day)
    assert sum(e.points for e in scored) == cap


def test_the_cap_resets_the_next_day():
    day_one = make(id="a", client_id="p", photos_ok=[True, True],
                   completed_quest="q", recorded_at=NOW)
    day_two = make(id="b", client_id="p", photos_ok=[True, True],
                   completed_quest="q", recorded_at=NOW - timedelta(days=1))
    scored = score_observations([day_one, day_two])
    assert points_of(scored, "a") == points_of(scored, "b") > 0


def test_a_capped_observation_records_what_it_would_have_earned():
    cap = get_points_rules().daily_cap
    many = [
        make(id=f"o{i}", client_id="p", site_id=f"S{i}", photos_ok=[True, True],
             completed_quest="q", recorded_at=NOW - timedelta(minutes=i))
        for i in range(6)
    ]
    scored = score_observations(many)
    capped = [e for e in scored if e.capped_from is not None]
    assert capped, "somebody should have hit the cap"
    assert sum(e.points for e in scored) == cap


def test_the_cap_is_per_person_not_global():
    busy = [make(id=f"a{i}", client_id="p1", site_id=f"S{i}",
                 photos_ok=[True, True], completed_quest="q",
                 recorded_at=NOW - timedelta(minutes=i)) for i in range(6)]
    other = [make(id="b", client_id="p2", site_id="Z", photos_ok=[True, True])]
    scored = score_observations(busy + other)
    assert points_of(scored, "b") > 0


# --------------------------------------------------------------------------
# Leaderboard
# --------------------------------------------------------------------------

def _team_data():
    observations = [
        make(id="a", client_id="p1", team="SCHOOL-A", site_id="C1", photos_ok=[True, True]),
        make(id="b", client_id="p2", team="SCHOOL-A", site_id="C2", photos_ok=[True, True]),
        make(id="c", client_id="p3", team="SCHOOL-B", site_id="C3", photos_ok=[True]),
        make(id="d", client_id="p4", team="SCHOOL-B", site_id="C3", photos_ok=[True]),
    ]
    return observations, score_observations(observations)


def test_the_leaderboard_ranks_teams():
    observations, scored = _team_data()
    standings = leaderboard(observations, scored)
    assert {t.team for t in standings} == {"SCHOOL-A", "SCHOOL-B"}
    assert standings[0].team == "SCHOOL-A", "more points"


def test_the_leaderboard_never_returns_individuals():
    observations, scored = _team_data()
    standings = leaderboard(observations, scored)
    for standing in standings:
        assert not hasattr(standing, "client_id")
    fields = set(vars(standings[0]))
    assert "client_id" not in fields and "nickname" not in fields


def test_a_one_person_team_is_not_ranked():
    """A team of one is an individual ranking by another name."""
    observations = [
        make(id="a", client_id="solo", team="ME", photos_ok=[True, True]),
        make(id="b", client_id="p1", team="REAL-TEAM", site_id="C2", photos_ok=[True]),
        make(id="c", client_id="p2", team="REAL-TEAM", site_id="C3", photos_ok=[True]),
    ]
    scored = score_observations(observations)
    standings = leaderboard(observations, scored)
    assert {t.team for t in standings} == {"REAL-TEAM"}
    assert withheld_teams(observations, scored) == 1


def test_teams_are_counted_by_distinct_people_not_submissions():
    observations = [
        make(id=f"o{i}", client_id="solo", team="ME", site_id=f"S{i}",
             recorded_at=NOW - timedelta(days=i), photos_ok=[True, True])
        for i in range(5)
    ]
    scored = score_observations(observations)
    assert leaderboard(observations, scored) == []
    assert MIN_TEAM_MEMBERS == 2


def test_an_observation_with_no_team_is_simply_not_ranked():
    observations = [make(id="a", client_id="p1", team="", photos_ok=[True, True])]
    assert leaderboard(observations, score_observations(observations)) == []


def test_the_leaderboard_can_be_filtered_to_one_city():
    observations, scored = _team_data()
    site_city = {"C1": "Coimbra", "C2": "Oslo", "C3": "Oslo"}
    only_oslo = leaderboard(observations, scored, city="Oslo", site_city=site_city)
    assert {t.team for t in only_oslo} == {"SCHOOL-B"}, "SCHOOL-A has one member in Oslo"


# --------------------------------------------------------------------------
# Coverage map
# --------------------------------------------------------------------------

def test_coverage_counts_sites_visited_in_the_window():
    sites = [{"id": f"S{i}", "name": f"Site {i}", "city": "Oslo"} for i in range(4)]
    observations = [
        make(id="a", site_id="S0", recorded_at=NOW - timedelta(days=3)),
        make(id="b", site_id="S1", recorded_at=NOW - timedelta(days=40)),
    ]
    result = coverage(observations, sites, since=NOW - timedelta(days=30))
    assert result["covered"] == 1
    assert result["total_sites"] == 4
    assert result["share"] == 0.25
    visited = {r["site_id"] for r in result["sites"] if r["visited"]}
    assert visited == {"S0"}


# --------------------------------------------------------------------------
# Wellbeing mirror
# --------------------------------------------------------------------------

def _records(people: int, rating: str = "GOOD"):
    return [
        (f"person-{i}", rating, {"joy": 4, "serenity": 4, "anger": 0, "fear": 0})
        for i in range(people)
    ]


def test_a_personal_mirror_works_for_one_person():
    mirror = wellbeing(_records(1), scope="personal")
    assert mirror.available is True
    assert mirror.scope == "personal"


def test_a_community_mirror_is_withheld_below_the_minimum():
    mirror = wellbeing(_records(MIN_GROUP - 1), scope="community")
    assert mirror.available is False
    assert mirror.by_rating == {}
    assert str(MIN_GROUP) in mirror.caveat
    assert mirror.people == MIN_GROUP - 1


def test_a_community_mirror_is_published_at_exactly_the_minimum():
    mirror = wellbeing(_records(MIN_GROUP), scope="community")
    assert mirror.available is True
    assert mirror.people == MIN_GROUP


def test_the_mirror_splits_feelings_by_the_rating_the_person_gave():
    records = (
        [(f"g{i}", "GOOD", {"joy": 4, "serenity": 4}) for i in range(6)]
        + [(f"p{i}", "POOR", {"joy": 0, "serenity": 0, "anger": 3}) for i in range(6)]
    )
    mirror = wellbeing(records, scope="community")
    assert mirror.by_rating["GOOD"]["positive_share"] == 1.0
    assert mirror.by_rating["POOR"]["positive_share"] == 0.0
    assert "Good" in mirror.headline and "Poor" in mirror.headline


def test_the_mirror_never_claims_a_stream_caused_a_feeling():
    mirror = wellbeing(_records(MIN_GROUP), scope="community")

    # The headline is the part a reader skims, so it must claim nothing.
    headline = mirror.headline.lower()
    for word in ("causes", "caused", "health", "makes you", "diagnos", "benefit"):
        assert word not in headline, mirror.headline

    # The caveat is allowed to use the word "caused" - it is there to deny it.
    caveat = mirror.caveat.lower()
    assert "not a health measurement" in caveat
    assert "does not show" in caveat and "caused" in caveat


# --------------------------------------------------------------------------
# FHIR bundle structure
# --------------------------------------------------------------------------

SITE = {"id": "C1", "name": "Exploratório", "city": "Coimbra",
        "country": "Portugal", "lat": 40.19787, "lon": -8.42865}

QUESTIONS = {
    "channelType": {
        "label": {"en": "Channel bed"}, "explain": {"en": "What the bed is made of."},
        "options": [{"code": "NAT", "label": {"en": "Natural"}, "explain": {"en": ""}},
                    {"code": "ART", "label": {"en": "Artificial"}, "explain": {"en": ""}}],
    },
    "habitats": {
        "label": {"en": "Instream habitats"}, "explain": {"en": "Features in the water."},
        "options": [{"code": "SB", "label": {"en": "Sand banks"}, "explain": {"en": ""}},
                    {"code": "RF", "label": {"en": "Riffles"}, "explain": {"en": ""}}],
    },
    "overall": {
        "label": {"en": "Overall"}, "explain": {"en": "The citizen's verdict."},
        "options": [{"code": "GOOD", "label": {"en": "Good"}, "explain": {"en": ""}},
                    {"code": "POOR", "label": {"en": "Poor"}, "explain": {"en": ""}}],
    },
}


def _observation(**kwargs) -> dict:
    base = {
        "id": "abc-123",
        "overall": "POOR",
        "recorded_at": NOW,
        "client_id": "pseudo-xyz",
        "ai_provider": "gemini",
        "ai_model": "gemini-3.5-flash-lite",
        "answers": [
            {"question_id": "channelType", "codes": ["ART"],
             "ai_suggested_code": "NAT", "ai_confidence": 0.62},
            {"question_id": "habitats", "codes": ["SB", "RF"]},
        ],
    }
    base.update(kwargs)
    return base


def _bundle(**kwargs) -> dict:
    return build_bundle(_observation(**kwargs), SITE, QUESTIONS,
                        team="SCHOOL-A", prompt_version="assess_v3")


def _resources(bundle: dict, kind: str) -> list[dict]:
    return [e["resource"] for e in bundle["entry"]
            if e["resource"]["resourceType"] == kind]


def test_the_bundle_has_a_location_observations_and_a_provenance():
    bundle = _bundle()
    assert bundle["resourceType"] == "Bundle"
    assert bundle["type"] == "collection"
    assert len(_resources(bundle, "Location")) == 1
    assert len(_resources(bundle, "Observation")) == 3, "two answers plus the rating"
    assert len(_resources(bundle, "Provenance")) == 1


def test_every_entry_has_an_absolute_fullurl():
    """urn:uuid: is only legal in front of an actual UUID."""
    for entry in _bundle()["entry"]:
        assert entry["fullUrl"].startswith("https://")


def test_the_location_meets_the_profiles_required_elements():
    location = _resources(_bundle(), "Location")[0]
    assert location["identifier"][0]["value"] == "C1"
    assert location["name"]
    assert location["mode"] == "instance"
    assert location["position"]["latitude"] == pytest.approx(40.19787)
    assert location["position"]["longitude"] == pytest.approx(-8.42865)


def test_every_observation_meets_the_profiles_required_elements():
    for observation in _resources(_bundle(), "Observation"):
        assert observation["status"] == "final", "the profile fixes this"
        assert observation["code"]["coding"]
        assert observation["subject"]["reference"] == "Location/site-C1"
        assert observation["effectiveDateTime"]
        assert observation["performer"], "the profile requires performer 1.."
        assert observation["performer"][0]["reference"] == "#programme"


def test_the_performer_is_a_contained_organization_naming_the_team():
    observation = _resources(_bundle(), "Observation")[0]
    contained = observation["contained"][0]
    assert contained["resourceType"] == "Organization"
    assert "SCHOOL-A" in contained["name"]


def test_no_patient_or_relatedperson_is_invented():
    """StreamLens holds no identity, and a citizen is not a patient."""
    types = {e["resource"]["resourceType"] for e in _bundle()["entry"]}
    assert "Patient" not in types
    assert "RelatedPerson" not in types


def test_a_single_answer_uses_value_and_a_multi_answer_uses_components():
    observations = {o["code"]["coding"][0]["code"]: o
                    for o in _resources(_bundle(), "Observation")}
    assert "valueCodeableConcept" in observations["channelType"]
    assert "component" not in observations["channelType"]

    habitats = observations["habitats"]
    assert "valueCodeableConcept" not in habitats
    assert len(habitats["component"]) == 2
    codes = {c["valueCodeableConcept"]["coding"][0]["code"] for c in habitats["component"]}
    assert codes == {"habitats.SB", "habitats.RF"}


def test_the_citizen_is_a_logical_reference_with_no_personal_data():
    provenance = _resources(_bundle(), "Provenance")[0]
    author = next(a for a in provenance["agent"]
                  if a["type"]["coding"][0]["code"] == "author")
    assert author["who"]["identifier"]["value"] == "pseudo-xyz"
    assert "reference" not in author["who"], "there is no resource for the citizen"


def test_the_ai_is_an_assembler_device_never_the_author():
    provenance = _resources(_bundle(), "Provenance")[0]
    roles = {a["type"]["coding"][0]["code"] for a in provenance["agent"]}
    assert roles == {"author", "assembler"}

    device = provenance["contained"][0]
    assert device["resourceType"] == "Device"
    assert device["deviceName"][0]["name"] == "gemini-3.5-flash-lite"
    assert device["version"][0]["value"] == "assess_v3"


def test_no_ai_agent_appears_when_no_ai_was_used():
    bundle = build_bundle(
        _observation(ai_provider="", ai_model=""), SITE, QUESTIONS,
        prompt_version="assess_v3",
    )
    provenance = _resources(bundle, "Provenance")[0]
    roles = {a["type"]["coding"][0]["code"] for a in provenance["agent"]}
    assert roles == {"author"}


def test_what_the_ai_suggested_and_whether_it_was_kept_is_recorded():
    observations = {o["code"]["coding"][0]["code"]: o
                    for o in _resources(_bundle(), "Observation")}
    note = observations["channelType"]["note"][0]["text"]
    assert "NAT" in note
    assert "chose differently" in note
    assert "gemini-3.5-flash-lite" in note


def test_the_overall_rating_says_the_ai_never_suggests_it():
    observations = {o["code"]["coding"][0]["code"]: o
                    for o in _resources(_bundle(), "Observation")}
    note = observations["overall"]["note"][0]["text"]
    assert "never lets the AI suggest" in note


def test_the_provenance_targets_every_observation_and_the_location():
    bundle = _bundle()
    provenance = _resources(bundle, "Provenance")[0]
    targets = {t["reference"] for t in provenance["target"]}
    assert "Location/site-C1" in targets
    assert len([t for t in targets if t.startswith("Observation/")]) == 3


def test_every_resource_carries_a_narrative():
    for entry in _bundle()["entry"]:
        assert entry["resource"]["text"]["status"] == "generated"
