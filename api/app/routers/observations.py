"""POST /observations - store what the citizen decided.

Sent as multipart so a queued offline submission can carry its photos with it:
a `payload` field holding the JSON below, plus optional `upstream` /
`downstream` files. Photos are stripped and downscaled again here, because the
client is not trusted to have done it.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from pydantic import ValidationError
from sqlmodel import Session, select

from ..config import Settings, get_settings
from ..imaging import prepare
from ..models import Observation, ObservationAnswer, ObservationPhoto, get_session
from ..questions import QuestionSet, get_questions
from ..retention import sweep_if_due
from ..schemas import (
    ObservationAnswerOut,
    ObservationIn,
    ObservationOut,
    ObservationSummary,
    PhotoQualityOut,
)
from ..sites import SiteSet, get_sites

router = APIRouter(tags=["observations"])

OVERALL_QUESTION = "overall"


def _to_out(
    observation: Observation,
    answers: list[ObservationAnswer],
    photos: list[ObservationPhoto],
    site_name: str,
) -> ObservationOut:
    judged = [a for a in answers if a.agreed_with_ai is not None]
    agreement = (
        round(sum(1 for a in judged if a.agreed_with_ai) / len(judged), 3) if judged else None
    )
    return ObservationOut(
        id=observation.id,
        site_id=observation.site_id,
        site_name=site_name,
        overall=observation.overall,
        emotions=observation.emotions,
        answers=[
            ObservationAnswerOut(
                question_id=a.question_id,
                codes=a.codes,
                ai_suggested_code=a.ai_suggested_code,
                ai_confidence=a.ai_confidence,
                agreed_with_ai=a.agreed_with_ai,
            )
            for a in answers
        ],
        lang=observation.lang,
        lat=observation.lat,
        lon=observation.lon,
        note=observation.note,
        synthetic=observation.synthetic,
        ai_provider=observation.ai_provider,
        ai_model=observation.ai_model,
        photos=[
            PhotoQualityOut(
                role=p.role,
                width=p.width,
                height=p.height,
                blur_score=p.blur_score,
                brightness=p.brightness,
                issues=[],
                ok=True,
                exif_stripped=p.exif_stripped,
            )
            for p in photos
        ],
        recorded_at=observation.recorded_at,
        created_at=observation.created_at,
        ai_agreement=agreement,
    )


@router.post("/observations", response_model=ObservationOut, status_code=201)
async def create_observation(
    payload: str = Form(..., description="The observation as a JSON object."),
    upstream: UploadFile | None = File(default=None),
    downstream: UploadFile | None = File(default=None),
    settings: Settings = Depends(get_settings),
    questions: QuestionSet = Depends(get_questions),
    site_set: SiteSet = Depends(get_sites),
    session: Session = Depends(get_session),
) -> ObservationOut:
    try:
        data = ObservationIn.model_validate_json(payload)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=json.loads(exc.json())) from exc

    site = site_set.get(data.site_id)
    if site is None:
        raise HTTPException(status_code=404, detail=f"unknown site '{data.site_id}'")

    # The overall rating is a citizen answer like any other, and validated the same way.
    ok, why = questions.validate_answer(OVERALL_QUESTION, [data.overall])
    if not ok:
        raise HTTPException(status_code=422, detail=f"overall rating rejected: {why}")

    problems: list[str] = []
    seen: set[str] = set()
    for answer in data.answers:
        if answer.question_id == OVERALL_QUESTION:
            problems.append("send the overall rating in 'overall', not in 'answers'")
            continue
        if answer.question_id in seen:
            problems.append(f"'{answer.question_id}' answered more than once")
            continue
        seen.add(answer.question_id)
        valid, reason = questions.validate_answer(answer.question_id, answer.codes)
        if not valid:
            problems.append(reason)
    if problems:
        raise HTTPException(status_code=422, detail={"invalid_answers": problems})

    observation = Observation(
        site_id=data.site_id,
        overall=data.overall,
        lang=data.lang,
        lat=data.lat,
        lon=data.lon,
        accuracy_m=data.accuracy_m,
        emotions_json=json.dumps(data.emotions),
        note=data.note,
        consent_given=data.consent_given,
        synthetic=data.synthetic,
        client_id=data.client_id,
        team=data.team,
        completed_quest=data.completed_quest,
        ai_provider=data.ai_provider,
        ai_model=data.ai_model,
        recorded_at=data.recorded_at or datetime.now(timezone.utc),
    )
    session.add(observation)
    session.flush()  # assigns the id

    rows = [
        ObservationAnswer(
            observation_id=observation.id,
            question_id=a.question_id,
            codes_json=json.dumps(a.codes),
            ai_suggested_code=a.ai_suggested_code,
            ai_confidence=a.ai_confidence,
            agreed_with_ai=a.agreed_with_ai,
        )
        for a in data.answers
        if a.question_id != OVERALL_QUESTION
    ]
    for row in rows:
        session.add(row)

    photo_rows: list[ObservationPhoto] = []
    uploads = [(r, f) for r, f in (("upstream", upstream), ("downstream", downstream)) if f]
    if uploads and settings.store_photos:
        settings.upload_path.mkdir(parents=True, exist_ok=True)
    for role, upload in uploads:
        raw = await upload.read()
        if not raw:
            continue
        try:
            photo = prepare(
                raw,
                role,
                max_px=settings.max_image_px,
                blur_threshold=settings.blur_threshold,
                dark_threshold=settings.dark_threshold,
                bright_threshold=settings.bright_threshold,
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        # On the hosted demo nothing is written to disk: the measurements are
        # kept and the image is dropped. An empty filename is what every other
        # part of the app reads as "there is no file for this photo".
        if settings.store_photos:
            filename = f"{observation.id}_{role}.jpg"
            (settings.upload_path / filename).write_bytes(photo.data)
        else:
            filename = ""
        row = ObservationPhoto(
            observation_id=observation.id,
            role=role,
            filename=filename,
            width=photo.width,
            height=photo.height,
            blur_score=photo.blur_score,
            brightness=photo.brightness,
            exif_stripped=True,
            bytes_stored=len(photo.data) if settings.store_photos else 0,
        )
        session.add(row)
        photo_rows.append(row)

    session.commit()
    session.refresh(observation)

    # Housekeeping while a session is already open: any stored photograph
    # past its keep-by date goes now, at most once an hour per process.
    sweep_if_due(session, settings)

    return _to_out(observation, rows, photo_rows, site.get("name", ""))


@router.get("/observations", response_model=list[ObservationSummary])
def list_observations(
    site_id: str | None = Query(default=None),
    include_synthetic: bool = Query(default=True),
    limit: int = Query(default=50, ge=1, le=200),
    site_set: SiteSet = Depends(get_sites),
    session: Session = Depends(get_session),
) -> list[ObservationSummary]:
    statement = select(Observation).order_by(Observation.created_at.desc()).limit(limit)
    if site_id:
        statement = statement.where(Observation.site_id == site_id)
    if not include_synthetic:
        statement = statement.where(Observation.synthetic == False)  # noqa: E712

    return [
        ObservationSummary(
            id=o.id,
            site_id=o.site_id,
            site_name=(site_set.get(o.site_id) or {}).get("name", ""),
            overall=o.overall,
            synthetic=o.synthetic,
            recorded_at=o.recorded_at,
        )
        for o in session.exec(statement).all()
    ]


@router.get("/observations/{observation_id}", response_model=ObservationOut)
def get_observation(
    observation_id: str,
    site_set: SiteSet = Depends(get_sites),
    session: Session = Depends(get_session),
) -> ObservationOut:
    observation = session.get(Observation, observation_id)
    if observation is None:
        raise HTTPException(status_code=404, detail="no such observation")

    answers = session.exec(
        select(ObservationAnswer).where(ObservationAnswer.observation_id == observation_id)
    ).all()
    photos = session.exec(
        select(ObservationPhoto).where(ObservationPhoto.observation_id == observation_id)
    ).all()
    site = site_set.get(observation.site_id) or {}
    return _to_out(observation, list(answers), list(photos), site.get("name", ""))
