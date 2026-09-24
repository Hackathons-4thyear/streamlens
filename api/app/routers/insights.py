"""Understand & Act: health cards, alerts, measures and the city overview.

Everything here reads from citizen-confirmed observations. The `synthetic`
parameter is explicit on every endpoint and echoed in every response, so demo
data and real data are never silently mixed.
"""

from __future__ import annotations

import csv
import io
from collections import defaultdict
from dataclasses import asdict
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlmodel import Session, select

from ..alerts import ObservationEvidence, evaluate, get_rules
from ..config import Settings, get_settings
from ..health_card import build as build_card
from ..measures import MeasureSet, get_measures
from ..models import Observation, ObservationAnswer, get_session
from ..questions import QuestionSet, get_questions
from ..sites import SiteSet, get_sites, haversine_m
from ..weather import get_forecast

router = APIRouter(tags=["insights"])

DataScope = Query(
    default="all",
    description="Which records to use: 'all', 'real' (synthetic excluded) or "
    "'demo' (synthetic only). Always echoed back in the response.",
)


def _scope_filter(statement, scope: str):
    if scope == "real":
        return statement.where(Observation.synthetic == False)  # noqa: E712
    if scope == "demo":
        return statement.where(Observation.synthetic == True)  # noqa: E712
    return statement


def _load_observations(session: Session, site_id: str, scope: str) -> list[dict]:
    statement = _scope_filter(
        select(Observation).where(Observation.site_id == site_id), scope
    )
    observations = session.exec(statement).all()
    if not observations:
        return []

    ids = [o.id for o in observations]
    answers = session.exec(
        select(ObservationAnswer).where(ObservationAnswer.observation_id.in_(ids))
    ).all()
    by_observation: dict[str, list] = defaultdict(list)
    for answer in answers:
        by_observation[answer.observation_id].append(answer)

    return [
        {
            "id": o.id,
            "overall": o.overall,
            "recorded_at": o.recorded_at.replace(tzinfo=timezone.utc)
            if o.recorded_at.tzinfo is None else o.recorded_at,
            "synthetic": o.synthetic,
            "emotions": o.emotions,
            "answers": [
                {"question_id": a.question_id, "codes": a.codes}
                for a in by_observation.get(o.id, [])
            ],
        }
        for o in observations
    ]


def _evidence(observations: list[dict]) -> list[ObservationEvidence]:
    out: list[ObservationEvidence] = []
    for observation in observations:
        for answer in observation["answers"]:
            out.append(ObservationEvidence(
                observation_id=observation["id"],
                question_id=answer["question_id"],
                codes=list(answer["codes"]),
                recorded_at=observation["recorded_at"],
                synthetic=observation["synthetic"],
            ))
    return out


# --------------------------------------------------------------------------
# Health card
# --------------------------------------------------------------------------

@router.get("/sites/{site_id}/health-card")
def health_card(
    site_id: str,
    scope: str = DataScope,
    site_set: SiteSet = Depends(get_sites),
    questions: QuestionSet = Depends(get_questions),
    measures: MeasureSet = Depends(get_measures),
    session: Session = Depends(get_session),
) -> dict:
    site = site_set.get(site_id)
    if site is None:
        raise HTTPException(status_code=404, detail=f"unknown site '{site_id}'")

    observations = _load_observations(session, site_id, scope)
    card = build_card(site, observations, questions, measures)
    payload = asdict(card)
    payload["scope"] = scope
    payload["site"] = site
    payload["built_from"] = (
        "Citizen-confirmed answers only. AI suggestions that nobody accepted are "
        "not included."
    )
    return payload


# --------------------------------------------------------------------------
# Alerts
# --------------------------------------------------------------------------

def _alerts_for_site(
    site: dict, scope: str, session: Session, settings: Settings, allow_network: bool
) -> dict:
    observations = _load_observations(session, site["id"], scope)
    forecast = get_forecast(
        session, site["id"], site.get("lat"), site.get("lon"),
        cache_seconds=settings.weather_cache_seconds,
        allow_network=allow_network,
    )
    alerts = evaluate(forecast, _evidence(observations))
    rules = get_rules()

    return {
        "site_id": site["id"],
        "site_name": site.get("name", ""),
        "city": site.get("city", ""),
        "scope": scope,
        "forecast": {
            "available": forecast.available,
            "rain_mm_48h": forecast.rain_mm_48h,
            "temp_max_c": forecast.temp_max_c,
            "temp_min_c": forecast.temp_min_c,
            "fetched_at": forecast.fetched_at.isoformat() if forecast.fetched_at else None,
            "stale": forecast.stale,
            "age_seconds": forecast.age_seconds,
            "summary": forecast.summary,
            "error": forecast.error,
            "source": forecast.source,
            "synthetic": forecast.synthetic,
        },
        "alerts": [asdict(a) for a in alerts],
        "always_include": rules.always_include,
        "never_a_diagnosis": (
            "These are advisory notes about conditions, not statements about anyone's "
            "health and not a water quality measurement."
        ),
    }


@router.get("/sites/{site_id}/alerts")
def site_alerts(
    site_id: str,
    scope: str = DataScope,
    offline: bool = Query(default=False, description="Skip the network, use the cache."),
    site_set: SiteSet = Depends(get_sites),
    settings: Settings = Depends(get_settings),
    session: Session = Depends(get_session),
) -> dict:
    site = site_set.get(site_id)
    if site is None:
        raise HTTPException(status_code=404, detail=f"unknown site '{site_id}'")
    return _alerts_for_site(site, scope, session, settings, allow_network=not offline)


@router.get("/alerts/near")
def alerts_near(
    lat: float = Query(...),
    lon: float = Query(...),
    radius_km: float = Query(default=25.0, ge=0.1, le=500),
    limit: int = Query(default=5, ge=1, le=20),
    scope: str = DataScope,
    site_set: SiteSet = Depends(get_sites),
    settings: Settings = Depends(get_settings),
    session: Session = Depends(get_session),
) -> dict:
    """Alerts for the nearest sites with any observations.

    Only nearby sites that somebody has actually visited are checked: a site
    with no observations can never trigger a rule, and calling the weather API
    for it would be wasted.
    """
    visited = {
        row for row in session.exec(select(Observation.site_id)).all()
    }
    candidates = []
    for site in site_set.all():
        if site["id"] not in visited:
            continue
        if site.get("lat") is None or site.get("lon") is None:
            continue
        distance = haversine_m(lat, lon, site["lat"], site["lon"]) / 1000
        if distance <= radius_km:
            candidates.append((distance, site))
    candidates.sort(key=lambda pair: pair[0])

    results = []
    for distance, site in candidates[:limit]:
        payload = _alerts_for_site(site, scope, session, settings, allow_network=True)
        payload["distance_km"] = round(distance, 1)
        results.append(payload)

    return {
        "scope": scope,
        "radius_km": radius_km,
        "checked": len(results),
        "sites_with_alerts": sum(1 for r in results if r["alerts"]),
        "results": results,
    }


# --------------------------------------------------------------------------
# Measures
# --------------------------------------------------------------------------

@router.get("/measures")
def list_measures(
    problems: str = Query(default="", description="Comma-separated problem ids."),
    measures: MeasureSet = Depends(get_measures),
) -> dict:
    ids = [p.strip() for p in problems.split(",") if p.strip()]
    selected = measures.measures_for(ids) if ids else list(measures.measures.values())
    return {
        "catalogue": measures.catalogue,
        "provenance_note": measures.doc.get("provenance_note", ""),
        "health_note": measures.doc.get("health_note", ""),
        "problems_requested": ids,
        "count": len(selected),
        "measures": selected,
        "all_problems": list(measures.problems.values()),
    }


@router.get("/sites/{site_id}/actions")
def site_actions(
    site_id: str,
    scope: str = DataScope,
    site_set: SiteSet = Depends(get_sites),
    questions: QuestionSet = Depends(get_questions),
    measures: MeasureSet = Depends(get_measures),
    session: Session = Depends(get_session),
) -> dict:
    """The measures that address the problems actually reported at this site."""
    site = site_set.get(site_id)
    if site is None:
        raise HTTPException(status_code=404, detail=f"unknown site '{site_id}'")

    observations = _load_observations(session, site_id, scope)
    card = build_card(site, observations, questions, measures)
    problem_ids = [p["id"] for p in card.problems]

    return {
        "site_id": site_id,
        "site_name": site.get("name", ""),
        "scope": scope,
        "problems": card.problems,
        "measures": measures.measures_for(problem_ids),
        "catalogue": measures.catalogue,
        "health_note": measures.doc.get("health_note", ""),
    }


# --------------------------------------------------------------------------
# City overview
# --------------------------------------------------------------------------

def _city_rows(
    city: str, scope: str, session: Session, settings: Settings,
    site_set: SiteSet, questions: QuestionSet, measures: MeasureSet,
    with_alerts: bool,
) -> list[dict]:
    sites = [s for s in site_set.all() if s.get("city", "").lower() == city.lower()]
    if not sites:
        raise HTTPException(status_code=404, detail=f"unknown city '{city}'")

    rows = []
    for site in sites:
        observations = _load_observations(session, site["id"], scope)
        card = build_card(site, observations, questions, measures)
        alerts = []
        if with_alerts and observations:
            payload = _alerts_for_site(site, scope, session, settings, allow_network=True)
            alerts = payload["alerts"]
        rows.append({
            "site_id": site["id"],
            "site_name": site.get("name", ""),
            "city": site.get("city", ""),
            "lat": site.get("lat"),
            "lon": site.get("lon"),
            "visits": card.visits,
            "last_visit": card.last_visit.isoformat() if card.last_visit else None,
            "latest_overall": card.latest_overall,
            "completeness": card.completeness,
            "completeness_label": card.completeness_label,
            "alert_count": len(alerts),
            "alerts": [{"rule_id": a["rule_id"], "name": a["name"],
                        "severity": a["severity"]} for a in alerts],
            "top_problems": [p["name"] for p in card.problems[:3]],
            "synthetic_count": card.synthetic_count,
            "real_count": card.real_count,
        })
    rows.sort(key=lambda r: (-r["alert_count"], -r["visits"], r["site_name"]))
    return rows


@router.get("/cities/{city}/overview")
def city_overview(
    city: str,
    scope: str = DataScope,
    with_alerts: bool = Query(default=True),
    site_set: SiteSet = Depends(get_sites),
    questions: QuestionSet = Depends(get_questions),
    measures: MeasureSet = Depends(get_measures),
    settings: Settings = Depends(get_settings),
    session: Session = Depends(get_session),
) -> dict:
    rows = _city_rows(city, scope, session, settings, site_set, questions,
                      measures, with_alerts)
    return {
        "city": city,
        "scope": scope,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "site_count": len(rows),
        "visited": sum(1 for r in rows if r["visits"]),
        "with_alerts": sum(1 for r in rows if r["alert_count"]),
        "disclaimer": (
            "Indicator view built from citizen reports, not a validated ecological "
            "index and not a regulatory classification."
        ),
        "rows": rows,
    }


@router.get("/cities/{city}/overview.csv")
def city_overview_csv(
    city: str,
    scope: str = DataScope,
    with_alerts: bool = Query(default=True),
    site_set: SiteSet = Depends(get_sites),
    questions: QuestionSet = Depends(get_questions),
    measures: MeasureSet = Depends(get_measures),
    settings: Settings = Depends(get_settings),
    session: Session = Depends(get_session),
) -> Response:
    rows = _city_rows(city, scope, session, settings, site_set, questions,
                      measures, with_alerts)

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow([
        "site_id", "site_name", "city", "visits", "last_visit", "latest_overall",
        "completeness", "alert_count", "alerts", "top_problems",
        "real_observations", "synthetic_observations",
    ])
    for row in rows:
        writer.writerow([
            row["site_id"], row["site_name"], row["city"], row["visits"],
            row["last_visit"] or "", row["latest_overall"] or "",
            f"{row['completeness']:.2f}", row["alert_count"],
            "; ".join(a["name"] for a in row["alerts"]),
            "; ".join(row["top_problems"]),
            row["real_count"], row["synthetic_count"],
        ])

    filename = f"streamlens-{city.lower()}-{datetime.now(timezone.utc):%Y%m%d}.csv"
    return Response(
        content=buffer.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
