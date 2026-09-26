"""POST /assess/suggest - photos in, validated suggestion chips out.

The validation gate in `validate_suggestions` is the important part of this
file. A provider may return anything; only proposals that name a real question,
that the question is allowed to be suggested for, and whose codes are real
options of that question, ever reach a citizen. Everything else is dropped and
reported in `dropped`, so a failing prompt is visible rather than silent.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from sqlmodel import Session

from .. import limits
from ..ai.base import AssessContext, ImageInput
from ..ai.factory import suggest_with_fallback, use_mock_instead
from ..ai.gemini import prompt_version
from ..config import Settings, get_settings
from ..imaging import PreparedPhoto, prepare
from ..models import get_session
from ..questions import QuestionSet, get_questions
from ..schemas import (
    DroppedSuggestion,
    LocationCheck,
    PhotoQualityOut,
    QualityIssueOut,
    SuggestionChip,
    SuggestResponse,
    UsageOut,
)
from ..sites import SiteSet, get_sites, haversine_m

router = APIRouter(tags=["assess"])

ALLOWED_IMAGE_TYPES = {
    "image/jpeg", "image/jpg", "image/png", "image/webp", "image/heic", "image/heif",
}


def validate_suggestions(
    raw_suggestions,
    questions: QuestionSet,
    low_confidence: float,
    photos_ok: bool,
) -> tuple[list[SuggestionChip], list[DroppedSuggestion]]:
    """Filter provider output down to what a citizen may be shown."""
    chips: list[SuggestionChip] = []
    dropped: list[DroppedSuggestion] = []
    seen: set[str] = set()

    for item in raw_suggestions:
        qid = item.question_id
        codes = [c for c in item.codes if isinstance(c, str) and c]

        question = questions.get(qid)
        if question is None:
            dropped.append(DroppedSuggestion(
                question_id=qid, codes=codes, why="no such question"))
            continue
        if not question.ai_suggestable:
            dropped.append(DroppedSuggestion(
                question_id=qid, codes=codes,
                why="this question is never suggested by the AI"))
            continue
        if qid in seen:
            dropped.append(DroppedSuggestion(
                question_id=qid, codes=codes, why="duplicate suggestion"))
            continue
        if not codes:
            dropped.append(DroppedSuggestion(
                question_id=qid, codes=codes, why="no answer code given"))
            continue

        bad = [c for c in codes if not question.allows(c)]
        if bad:
            dropped.append(DroppedSuggestion(
                question_id=qid, codes=codes,
                why=f"code(s) not an option of this question: {', '.join(bad)}"))
            continue
        if not question.is_multi and len(codes) > 1:
            dropped.append(DroppedSuggestion(
                question_id=qid, codes=codes,
                why="several codes given for a single-answer question"))
            continue

        confidence = min(1.0, max(0.0, float(item.confidence)))

        review_reason = ""
        if not photos_ok:
            review_reason = "The photo quality makes this harder to trust - please check it."
        elif confidence < low_confidence:
            review_reason = "The AI is not confident here. Your judgement decides."
        elif codes[0] == "NS":
            review_reason = "The AI could not tell. Answer it yourself if you can."

        seen.add(qid)
        chips.append(
            SuggestionChip(
                question_id=qid,
                suggested_code=codes[0],
                additional_codes=codes[1:],
                confidence=round(confidence, 2),
                reason=(item.reason or "").strip(),
                needs_review=bool(review_reason),
                review_reason=review_reason,
            )
        )

    chips.sort(key=lambda c: questions.get(c.question_id).raw.get("order", 0))
    return chips, dropped


def _quality_out(photo: PreparedPhoto) -> PhotoQualityOut:
    return PhotoQualityOut(
        role=photo.role,
        width=photo.width,
        height=photo.height,
        blur_score=photo.blur_score,
        brightness=photo.brightness,
        issues=[QualityIssueOut(code=i.code, severity=i.severity, message=i.message)
                for i in photo.issues],
        ok=photo.ok,
        exif_stripped=photo.exif_stripped,
    )


def check_location(
    site: dict, lat: float | None, lon: float | None, warn_m: float
) -> LocationCheck:
    if lat is None or lon is None:
        return LocationCheck(
            provided=False,
            message="No location was shared, so we could not check you are at the site.",
        )
    if site.get("lat") is None or site.get("lon") is None:
        return LocationCheck(provided=True, message="This site has no recorded coordinates.")

    distance = haversine_m(lat, lon, site["lat"], site["lon"])
    far = distance > warn_m
    return LocationCheck(
        provided=True,
        distance_m=round(distance, 1),
        far_from_site=far,
        message=(
            f"You look about {round(distance):,} m from the recorded point for this site. "
            "Check you picked the right one - or carry on if you know you are in the right place."
            if far
            else f"You are about {round(distance):,} m from the recorded point for this site."
        ),
    )


@router.post("/assess/suggest", response_model=SuggestResponse)
async def suggest(
    request: Request,
    site_id: str = Form(...),
    upstream: UploadFile | None = File(default=None),
    downstream: UploadFile | None = File(default=None),
    lat: float | None = Form(default=None),
    lon: float | None = Form(default=None),
    client_id: str = Form(default=""),
    settings: Settings = Depends(get_settings),
    questions: QuestionSet = Depends(get_questions),
    site_set: SiteSet = Depends(get_sites),
    session: Session = Depends(get_session),
) -> SuggestResponse:
    """Draft answers for one or two photographs.

    Only reached when the citizen has chosen AI help: the interface offers a
    manual path that never calls this at all, so opting out means the photos are
    never sent to Google rather than merely not being shown.
    """
    site = site_set.get(site_id)
    if site is None:
        raise HTTPException(status_code=404, detail=f"unknown site '{site_id}'")

    uploads = [(r, f) for r, f in (("upstream", upstream), ("downstream", downstream)) if f]
    if not uploads:
        raise HTTPException(
            status_code=422,
            detail="send at least one photo, as 'upstream' and/or 'downstream'",
        )

    prepared: list[PreparedPhoto] = []
    for role, upload in uploads:
        raw = await upload.read()
        if not raw:
            raise HTTPException(status_code=422, detail=f"the {role} photo was empty")
        if len(raw) > settings.max_upload_mb * 1024 * 1024:
            raise HTTPException(
                status_code=413,
                detail=f"the {role} photo is larger than {settings.max_upload_mb} MB",
            )
        if upload.content_type and upload.content_type.lower() not in ALLOWED_IMAGE_TYPES:
            raise HTTPException(
                status_code=415,
                detail=f"the {role} file is {upload.content_type}, not an image",
            )
        try:
            prepared.append(
                prepare(
                    raw,
                    role,
                    max_px=settings.max_image_px,
                    ai_max_px=settings.ai_max_image_px,
                    blur_threshold=settings.blur_threshold,
                    dark_threshold=settings.dark_threshold,
                    bright_threshold=settings.bright_threshold,
                )
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    context = AssessContext(
        site_name=site.get("name", ""),
        city=site.get("city", ""),
        country=site.get("country", ""),
        catalogue=questions.catalogue_for_prompt(),
    )
    # The SMALLER copy is what leaves this server. Never `p.data`.
    images = [ImageInput(role=p.role, data=p.ai_data or p.data) for p in prepared]

    caller = client_id or (request.client.host if request.client else "anonymous")
    decision = limits.check(
        session, caller,
        per_hour=settings.ai_calls_per_hour_per_client,
        per_day=settings.ai_calls_per_day_total,
    )

    try:
        if not decision.allowed:
            # Not an error: the free allowance is spent, so the labelled mock
            # answers instead and the interface says so.
            outcome = await use_mock_instead(
                images, context, settings.ai_provider.lower(),
                "quota", decision.message,
            )
        else:
            outcome = await suggest_with_fallback(settings, images, context)
            if not outcome.is_mock:
                limits.record(session, caller)
    except Exception as exc:  # noqa: BLE001 - only reachable if the mock itself fails
        raise HTTPException(
            status_code=502,
            detail=f"suggestions could not be produced: {exc}. "
                   "You can still answer every question yourself.",
        ) from exc

    photos_ok = all(p.ok for p in prepared)

    if not outcome.is_watercourse:
        # The model says this is not a stream. Whatever else it returned, none
        # of it is an assessment of a watercourse, so none of it is shown.
        chips, dropped = [], []
    else:
        chips, dropped = validate_suggestions(
            outcome.result.suggestions, questions, settings.low_confidence, photos_ok
        )

    return SuggestResponse(
        site_id=site_id,
        site_name=site.get("name", ""),
        provider=outcome.provider,
        requested_provider=outcome.requested_provider,
        model=outcome.model,
        is_mock=outcome.is_mock,
        degraded=outcome.degraded,
        degraded_reason=outcome.degraded_reason,
        degraded_kind=outcome.degraded_kind,
        is_watercourse=outcome.is_watercourse,
        not_watercourse_reason=outcome.not_watercourse_reason,
        attempts=outcome.attempts,
        latency_ms=outcome.latency_ms,
        usage=UsageOut(**vars(outcome.usage)),
        ai_calls_remaining_today=decision.remaining_today,
        prompt_version=prompt_version(),
        provider_note=outcome.result.note,
        generated_at=datetime.now(timezone.utc),
        photo_quality=[_quality_out(p) for p in prepared],
        location=check_location(site, lat, lon, settings.gps_warn_m),
        suggestions=chips,
        dropped=dropped,
    )
