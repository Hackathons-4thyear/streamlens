"""Create realistic demo observations so the Understand & Act screens have data.

**Every record written here carries `synthetic: true`.** The API filters on it,
the UI badges it, and nothing in the product ever mixes these with real citizen
reports without saying so.

Twelve sites across all five research cities, ninety days of visits. Three of
those sites are deliberately shaped so that each alert rule has something to
fire on, so a demo can show all three:

- a sewage site      -> reports of sewage and a discharging pipe
- a stagnant site    -> reports of standing or dry water
- an obstructed site -> reports of a barrier and fallen wood

Whether the rules actually fire also depends on the weather forecast for those
coordinates on the day, which is real. The script says at the end which rules
would fire right now.

Usage:
    python scripts/seed_demo.py            # add demo data
    python scripts/seed_demo.py --if-empty # add it only if there is none yet
    python scripts/seed_demo.py --reset    # delete existing demo data first
    python scripts/seed_demo.py --check    # report which rules would fire now
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "api"))

from sqlmodel import Session, select  # noqa: E402

from app.models import (  # noqa: E402
    Observation,
    ObservationAnswer,
    get_engine,
    init_db,
)
from app.questions import get_questions  # noqa: E402
from app.sites import get_sites  # noqa: E402

CLIENT_PREFIX = "demo-"

# Demo teams, so the team leaderboard and coverage map have something to show.
# A team is a free-text code typed on the phone, not an account.
TEAMS = {
    "Coimbra": ["ESC-COIMBRA-7B", "RIO-MONDEGO"],
    "Benevento": ["LICEO-BN-3A", "AMICI-DEL-CALORE"],
    "Toulouse": ["LYCEE-TLS-2", "GARONNE-VERTE"],
    "Ghent": ["SCHOOL-GENT-4", "LEIE-WACHT"],
    "Oslo": ["OSLO-SKOLE-9", "ELVEVENNER"],
}

# Site "characters": what a visitor would plausibly keep reporting there.
# (key, how many of the city's sites get it, the answers that define it)
CHARACTERS = {
    "healthy": {
        "overall": ["GOOD", "GOOD", "MODERATE"],
        "answers": {
            "channelType": ["NAT"], "bankType": ["NAT"], "waterAspect": ["CL"],
            "waterFlow": ["NOR", "FAS"], "habitats": ["SD", "RF"],
            "fallenBiomass": ["FB"], "vegCoverL": ["Y"], "vegCoverR": ["Y"],
            "vegDominantL": ["T"], "vegDominantR": ["T"],
            "imperviousL": ["N"], "imperviousR": ["N"],
            "sewage": ["N"], "pollutedPipes": ["N"], "dams": ["N"],
            "construction": ["N"],
        },
    },
    "concrete": {
        "overall": ["POOR", "MODERATE", "POOR"],
        "answers": {
            "channelType": ["ART"], "bankType": ["ART"], "waterAspect": ["MU"],
            "waterFlow": ["NOR"], "habitats": ["NONE"], "fallenBiomass": ["NONE"],
            "vegCoverL": ["N"], "vegCoverR": ["N"],
            "imperviousL": ["Y"], "imperviousR": ["Y"],
            "sewage": ["N"], "pollutedPipes": ["N"], "dams": ["N"],
            "construction": ["N"],
        },
    },
    "sewage": {
        "overall": ["POOR", "POOR", "MODERATE"],
        "answers": {
            "channelType": ["ART"], "bankType": ["LAS"], "waterAspect": ["MU", "FO"],
            "waterFlow": ["NOR"], "habitats": ["NONE"],
            "sewage": ["Y"], "pollutedPipes": ["Y"],
            "vegCoverL": ["N"], "vegCoverR": ["Y"], "vegDominantR": ["H"],
            "imperviousL": ["Y"], "imperviousR": ["Y"],
            "dams": ["N"], "construction": ["N"],
        },
    },
    "stagnant": {
        "overall": ["POOR", "MODERATE", "POOR"],
        "answers": {
            "channelType": ["NAT"], "bankType": ["NAT"], "waterAspect": ["CO"],
            "waterFlow": ["STA", "DRY"], "habitats": ["AV"],
            "fallenBiomass": ["FL"],
            "vegCoverL": ["Y"], "vegCoverR": ["Y"],
            "vegDominantL": ["H"], "vegDominantR": ["H"],
            "imperviousL": ["N"], "imperviousR": ["N"],
            "sewage": ["N"], "pollutedPipes": ["N"], "dams": ["N"],
            "construction": ["N"],
        },
    },
    "obstructed": {
        "overall": ["MODERATE", "MODERATE", "POOR"],
        "answers": {
            "channelType": ["NAT"], "bankType": ["LAS"], "waterAspect": ["MU"],
            "waterFlow": ["NOR"], "habitats": ["SD"],
            "fallenBiomass": ["FT", "FB"], "dams": ["Y"],
            "vegCoverL": ["Y"], "vegCoverR": ["Y"],
            "vegDominantL": ["T"], "vegDominantR": ["T"],
            "imperviousL": ["N"], "imperviousR": ["N"],
            "sewage": ["N"], "pollutedPipes": ["N"], "construction": ["N"],
        },
    },
    "recovering": {
        "overall": ["MODERATE", "GOOD", "GOOD"],
        "answers": {
            "channelType": ["NAT"], "bankType": ["NAT"], "waterAspect": ["CL"],
            "waterFlow": ["NOR"], "habitats": ["SD", "SB"],
            "fallenBiomass": ["FB"], "vegCoverL": ["Y"], "vegCoverR": ["Y"],
            "vegDominantL": ["B"], "vegDominantR": ["T"],
            "imperviousL": ["N"], "imperviousR": ["Y"],
            "sewage": ["N"], "pollutedPipes": ["N"], "dams": ["N"],
            "construction": ["Y"],
        },
    },
}

# Emotions that go with each character, as (joy, serenity, anger, fear) ranges.
MOODS = {
    "healthy": ((2, 4), (3, 4), (0, 1), (0, 1)),
    "recovering": ((2, 4), (2, 4), (0, 1), (0, 1)),
    "concrete": ((0, 2), (0, 2), (1, 3), (0, 2)),
    "sewage": ((0, 1), (0, 1), (2, 4), (1, 3)),
    "stagnant": ((0, 2), (1, 2), (1, 3), (1, 3)),
    "obstructed": ((1, 3), (1, 3), (1, 2), (1, 2)),
}

# Which character each chosen site gets. Ordered so every city appears and the
# three alert-triggering characters are all present.
# Shifting some sites' visits back in time so every quest type has something to
# fire on. This shapes WHEN the demo visits happened; it invents no observation
# that the rules would not otherwise see.
#   (city, character) -> extra days to age every visit at that site
QUEST_SHAPING = {
    ("Oslo", "stagnant"): 45,      # -> "nobody has been here for a while"
    ("Ghent", "recovering"): 200,  # -> "this season has no record"
}

PLAN = [
    ("Coimbra", "sewage"), ("Coimbra", "healthy"), ("Coimbra", "concrete"),
    ("Benevento", "stagnant"), ("Benevento", "healthy"),
    ("Toulouse", "obstructed"), ("Toulouse", "concrete"),
    ("Ghent", "sewage"), ("Ghent", "recovering"),
    ("Oslo", "healthy"), ("Oslo", "stagnant"), ("Oslo", "recovering"),
]


def pick_sites(site_set, rng: random.Random) -> list[tuple[dict, str]]:
    by_city: dict[str, list[dict]] = {}
    for site in site_set.all():
        by_city.setdefault(site.get("city", ""), []).append(site)
    for sites in by_city.values():
        sites.sort(key=lambda s: s["id"])

    chosen: list[tuple[dict, str]] = []
    used: set[str] = set()
    for city, character in PLAN:
        pool = [s for s in by_city.get(city, []) if s["id"] not in used]
        if not pool:
            print(f"  ! no spare site in {city}, skipping one {character} site")
            continue
        site = pool[rng.randrange(min(len(pool), 6))]
        used.add(site["id"])
        chosen.append((site, character))
    return chosen


def make_observation(
    site: dict, character: str, when: datetime, rng: random.Random, questions
) -> tuple[Observation, list[ObservationAnswer]]:
    spec = CHARACTERS[character]
    overall = spec["overall"][rng.randrange(len(spec["overall"]))]

    joy, serenity, anger, fear = MOODS[character]
    emotions = {
        "joy": rng.randint(*joy),
        "serenity": rng.randint(*serenity),
        "anger": rng.randint(*anger),
        "fear": rng.randint(*fear),
    }

    observation = Observation(
        site_id=site["id"],
        overall=overall,
        lang=site.get("lang", "en"),
        lat=site.get("lat"),
        lon=site.get("lon"),
        accuracy_m=round(rng.uniform(4, 25), 1),
        emotions_json=json.dumps(emotions),
        note="",
        consent_given=True,
        synthetic=True,
        client_id=f"{CLIENT_PREFIX}{rng.randrange(1, 14)}",
        team=rng.choice(TEAMS.get(site.get("city", ""), ["STREAMLENS-DEMO"])),
        ai_provider="seed",
        ai_model="scripts/seed_demo.py",
        recorded_at=when,
    )

    answers: list[ObservationAnswer] = []
    for question_id, options in spec["answers"].items():
        question = questions.get(question_id)
        if question is None:
            continue
        # A real visitor does not answer everything every time.
        if rng.random() < 0.18:
            continue
        codes = [options[rng.randrange(len(options))]]
        if question.is_multi and len(options) > 1 and rng.random() < 0.4:
            codes = sorted(set(options))
        ok, _ = questions.validate_answer(question_id, codes)
        if not ok:
            continue
        # Half of the answers record what the AI had suggested, some disagreeing,
        # so the demo shows a realistic agreement rate rather than a perfect one.
        suggested = codes[0]
        if rng.random() < 0.25:
            alternatives = [c for c in question.codes if c != codes[0]]
            if alternatives:
                suggested = alternatives[rng.randrange(len(alternatives))]
        answers.append(ObservationAnswer(
            observation_id=observation.id,
            question_id=question_id,
            codes_json=json.dumps(codes),
            ai_suggested_code=suggested if rng.random() < 0.6 else None,
            ai_confidence=round(rng.uniform(0.45, 0.95), 2) if rng.random() < 0.6 else None,
            agreed_with_ai=suggested in codes,
        ))
    return observation, answers


def plant_demo_weather(session: Session, targets: dict[str, dict]) -> None:
    """Write clearly-labelled synthetic forecasts so a demo can show every rule.

    The real forecast for a site is whatever it is; on a dry day the rain rules
    correctly stay silent, which makes them impossible to demonstrate. Rather
    than quietly inventing weather, these rows carry `_streamlens_synthetic`,
    which the API reports and the UI badges as a demo forecast.
    """
    from app.models import WeatherCache

    now = datetime.now(timezone.utc)
    for site_id, shape in targets.items():
        # 48 hours of already-fallen rain, then 72 of forecast, so one planted
        # payload can drive both the alert rules (future) and the after-rain
        # quest (past).
        offsets = list(range(-48, 72))
        hours = [(now + timedelta(hours=h)).strftime("%Y-%m-%dT%H:00")
                 for h in offsets]
        rain = [shape["rain_per_hour"] if -48 <= h < 48 else 0.0 for h in offsets]
        temps = [shape["temp"] for _ in offsets]
        payload = {
            "_streamlens_synthetic": True,
            "_note": "Planted by scripts/seed_demo.py so the demo can show this rule. "
                     "Not a real forecast.",
            "hourly": {"time": hours, "precipitation": rain, "temperature_2m": temps},
        }
        row = session.get(WeatherCache, site_id)
        if row:
            row.payload_json = json.dumps(payload)
            row.fetched_at = now
        else:
            row = WeatherCache(site_id=site_id, payload_json=json.dumps(payload),
                               fetched_at=now)
        session.add(row)
    session.commit()


def reset(session: Session) -> int:
    demo = session.exec(
        select(Observation).where(Observation.synthetic == True)  # noqa: E712
    ).all()
    ids = [o.id for o in demo]
    if ids:
        for answer in session.exec(
            select(ObservationAnswer).where(ObservationAnswer.observation_id.in_(ids))
        ).all():
            session.delete(answer)
        for observation in demo:
            session.delete(observation)
        session.commit()
    return len(ids)


def check(session: Session, site_set) -> None:
    from app.alerts import evaluate
    from app.config import get_settings
    from app.routers.insights import _evidence, _load_observations
    from app.weather import get_forecast

    settings = get_settings()
    print("\nWhich rules would fire right now (real forecast, demo observations):")
    fired_any: set[str] = set()
    for site_id in sorted({o.site_id for o in session.exec(
            select(Observation).where(Observation.synthetic == True)).all()}):  # noqa: E712
        site = site_set.get(site_id)
        if not site:
            continue
        observations = _load_observations(session, site_id, "demo")
        forecast = get_forecast(session, site_id, site.get("lat"), site.get("lon"),
                                cache_seconds=settings.weather_cache_seconds)
        alerts = evaluate(forecast, _evidence(observations))
        if alerts:
            fired_any.update(a.rule_id for a in alerts)
            names = ", ".join(a.rule_id for a in alerts)
            print(f"  {site_id:6s} {site['name'][:28]:30s} {names}")
    missing = {"sewage_overflow_risk", "mosquito_breeding_conditions",
               "debris_blockage_watch"} - fired_any
    if missing:
        print(f"\n  Not firing today: {', '.join(sorted(missing))}")
        print("  The observations for them exist; the weather thresholds are simply")
        print("  not met at those coordinates today. That is the rules working.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reset", action="store_true",
                        help="delete existing synthetic observations first")
    parser.add_argument("--check", action="store_true",
                        help="only report which rules would fire now")
    parser.add_argument("--if-empty", action="store_true",
                        help="do nothing if demo data is already present "
                             "(used by the hosted deploy, which reruns on "
                             "every push)")
    parser.add_argument("--days", type=int, default=90)
    parser.add_argument("--seed", type=int, default=20260924)
    parser.add_argument("--no-demo-weather", action="store_true",
                        help="do not plant synthetic forecasts; use real weather only")
    args = parser.parse_args()

    init_db()
    questions = get_questions()
    site_set = get_sites()
    rng = random.Random(args.seed)

    with Session(get_engine()) as session:
        if args.check:
            check(session, site_set)
            return 0

        if args.if_empty:
            existing = session.exec(
                select(Observation).where(Observation.synthetic == True)  # noqa: E712
            ).first()
            if existing is not None:
                print("Demo data is already present; nothing to do.")
                return 0

        if args.reset:
            removed = reset(session)
            print(f"Removed {removed} existing demo observations")

        chosen = pick_sites(site_set, rng)
        now = datetime.now(timezone.utc)
        total = 0

        for site, character in chosen:
            # Between 4 and 11 visits over the window, most of them recent.
            visits = rng.randint(4, 11)
            offsets = sorted(
                (rng.betavariate(1.6, 2.6) * args.days for _ in range(visits)),
                reverse=True,
            )
            shift = QUEST_SHAPING.get((site.get("city", ""), character), 0)
            for offset in offsets:
                when = now - timedelta(days=offset + shift,
                                       hours=rng.uniform(0, 12))
                observation, answers = make_observation(
                    site, character, when, rng, questions
                )
                session.add(observation)
                for answer in answers:
                    session.add(answer)
                total += 1
            shift = QUEST_SHAPING.get((site.get("city", ""), character), 0)
            aged = f" (+{shift}d older)" if shift else ""
            print(f"  {site['id']:6s} {site['city']:10s} {site['name'][:26]:28s} "
                  f"{character:11s} {visits:2d} visits{aged}")

        session.commit()

        if not args.no_demo_weather:
            # One site per rain-driven rule gets a planted, labelled forecast, so
            # all three rules can be shown on a dry day. The mosquito rule needs
            # no help: warm weather is common enough to trigger it for real.
            targets: dict[str, dict] = {}
            wanted = {"sewage": {"rain_per_hour": 0.6, "temp": 14.0},
                      "obstructed": {"rain_per_hour": 0.8, "temp": 13.0}}
            for site, character in chosen:
                shape = wanted.pop(character, None)
                if shape:
                    targets[site["id"]] = shape
            if targets:
                plant_demo_weather(session, targets)
                print(f"\nPlanted demo forecasts for {', '.join(sorted(targets))} so "
                      "the rain-driven rules can be shown on a dry day.")
                print("They are flagged synthetic; the API reports it and the UI "
                      "badges them as DEMO FORECAST.")

        print(f"\nWrote {total} synthetic observations across {len(chosen)} sites "
              f"in {len({s['city'] for s, _ in chosen})} cities.")
        print("Every one is flagged synthetic=true.")
        check(session, site_set)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
