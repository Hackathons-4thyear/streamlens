"""Keeping a free-tier key inside its free tier.

There is no billing account behind this key. If these limits fail, the demo
stops working for everybody until the quota resets - so they are tested at the
boundary in both directions, and the behaviour when they bite is tested too:
the request must still succeed, on the labelled mock, never as an error.
"""

from __future__ import annotations

import pytest
from sqlmodel import Session

from app import limits
from app.models import AiUsage, get_engine
from tests.conftest import sharp_image


@pytest.fixture
def session(client):
    with Session(get_engine()) as session:
        yield session


@pytest.fixture(autouse=True)
def _clean():
    limits.reset_for_tests()
    yield
    limits.reset_for_tests()


# --------------------------------------------------------------------------
# The hourly, per-caller limit
# --------------------------------------------------------------------------

def test_a_caller_is_allowed_up_to_the_hourly_limit(session):
    for _ in range(10):
        decision = limits.check(session, "person-a", per_hour=10, per_day=1000)
        assert decision.allowed
        limits.record(session, "person-a")

    assert limits.check(session, "person-a", per_hour=10, per_day=1000).allowed is False


def test_the_eleventh_call_in_an_hour_is_refused_with_a_plain_reason(session):
    for _ in range(10):
        limits.record(session, "person-a")

    decision = limits.check(session, "person-a", per_hour=10, per_day=1000)
    assert decision.reason == "hourly_cap"
    assert "limit" in decision.message.lower()
    assert "your own answers are unaffected" in decision.message.lower()


def test_one_caller_hitting_the_limit_does_not_block_another(session):
    for _ in range(10):
        limits.record(session, "person-a")

    assert limits.check(session, "person-a", per_hour=10, per_day=1000).allowed is False
    assert limits.check(session, "person-b", per_hour=10, per_day=1000).allowed is True


def test_the_window_slides(session):
    """Calls from more than an hour ago should not count against you."""
    import time

    now = time.time()
    for _ in range(10):
        limits.record(session, "person-a", now=now - 3700)

    assert limits.check(session, "person-a", per_hour=10, per_day=1000, now=now).allowed


# --------------------------------------------------------------------------
# The daily, whole-service cap
# --------------------------------------------------------------------------

def test_the_daily_cap_applies_across_all_callers(session):
    """This is the one that actually protects the key: one enthusiastic user
    must not be able to spend the whole day's allowance either, but neither
    should a crowd of them."""
    for index in range(20):
        limits.record(session, f"person-{index}")

    decision = limits.check(session, "someone-new", per_hour=10, per_day=20)
    assert decision.allowed is False
    assert decision.reason == "daily_cap"
    assert decision.used_today == 20


def test_the_daily_cap_is_exact_at_the_boundary(session):
    for index in range(19):
        limits.record(session, f"person-{index}")

    assert limits.check(session, "x", per_hour=100, per_day=20).allowed is True
    limits.record(session, "x")
    assert limits.check(session, "y", per_hour=100, per_day=20).allowed is False


def test_the_daily_count_survives_a_restart(session):
    """It lives in the database, not in memory, precisely for this."""
    for _ in range(5):
        limits.record(session, "person-a")

    limits.reset_for_tests()  # as if the process had restarted
    assert limits.usage_today(session) == 5
    assert limits.check(session, "person-a", per_hour=10, per_day=5).allowed is False


def test_the_daily_message_says_it_comes_back_tomorrow(session):
    limits.record(session, "a")
    decision = limits.check(session, "a", per_hour=10, per_day=1)
    assert "tomorrow" in decision.message.lower()
    assert "answer them yourself" in decision.message.lower()


def test_remaining_today_is_reported(session):
    for _ in range(3):
        limits.record(session, "a")
    decision = limits.check(session, "a", per_hour=100, per_day=10)
    assert decision.remaining_today == 7


def test_checking_does_not_consume_an_allowance(session):
    """A request that fails before reaching the provider must not cost anybody
    their quota."""
    for _ in range(5):
        limits.check(session, "a", per_hour=10, per_day=100)
    assert limits.usage_today(session) == 0


def test_a_zero_limit_means_no_limit(session):
    for _ in range(50):
        limits.record(session, "a")
    assert limits.check(session, "a", per_hour=0, per_day=0).allowed is True


# --------------------------------------------------------------------------
# What a citizen sees when a limit bites
# --------------------------------------------------------------------------

def _post(client, site_id, client_id="judge-1"):
    return client.post(
        "/assess/suggest",
        data={"site_id": site_id, "client_id": client_id},
        files={"upstream": ("up.jpg", sharp_image(), "image/jpeg")},
    )


def test_hitting_the_cap_still_returns_suggestions_never_an_error(
    client, site_id, settings, session
):
    settings.ai_calls_per_day_total = 1
    settings.ai_provider = "gemini"
    limits.record(session, "someone-else")

    response = _post(client, site_id)
    assert response.status_code == 200, "a spent quota is not an error"

    body = response.json()
    assert body["degraded"] is True
    assert body["degraded_kind"] == "quota"
    assert body["is_mock"] is True
    assert body["suggestions"], "the citizen still has something to work from"
    assert "used up" in body["degraded_reason"].lower()


def test_the_quota_notice_is_distinct_from_a_failure(client, site_id, settings, session):
    """'Unavailable' reads as broken; a spent free allowance is not broken."""
    settings.ai_calls_per_day_total = 1
    limits.record(session, "x")

    reason = _post(client, site_id).json()["degraded_reason"]
    assert "used up" in reason.lower()
    assert "could not be reached" not in reason.lower()


def test_a_successful_mock_run_does_not_consume_the_ai_allowance(
    client, site_id, settings, session
):
    """With no key configured every call is already the mock, and those must
    not count against a quota they never touched."""
    settings.ai_provider = "mock"
    _post(client, site_id)
    assert limits.usage_today(session) == 0


# --------------------------------------------------------------------------
# Upload guards
# --------------------------------------------------------------------------

def test_an_oversized_upload_is_refused(client, site_id, settings):
    settings.max_upload_mb = 1
    big = b"\xff\xd8\xff" + b"0" * (2 * 1024 * 1024)
    response = client.post(
        "/assess/suggest",
        data={"site_id": site_id},
        files={"upstream": ("big.jpg", big, "image/jpeg")},
    )
    assert response.status_code == 413
    assert "larger than 1 MB" in response.json()["detail"]


def test_a_non_image_content_type_is_refused(client, site_id):
    response = client.post(
        "/assess/suggest",
        data={"site_id": site_id},
        files={"doc": ("notes.pdf", b"%PDF-1.4", "application/pdf"),
               "upstream": ("notes.pdf", b"%PDF-1.4", "application/pdf")},
    )
    assert response.status_code == 415
    assert "not an image" in response.json()["detail"]


# --------------------------------------------------------------------------
# What actually leaves the server
# --------------------------------------------------------------------------

def test_only_the_smaller_copy_is_sent_to_the_ai(client, site_id, settings, monkeypatch):
    """The stored image may be 1600px; what goes to Google must be <= 1024px.

    Kept as a test because the two sizes are easy to conflate, and conflating
    them would silently send citizens' photographs at full size to a third
    party under terms that allow human review.
    """
    from io import BytesIO

    from PIL import Image

    from app.ai import factory

    seen: dict[str, int] = {}

    class Capturing:
        name, model, is_mock, retries = "capture", "c1", False, 0

        async def suggest(self, images, context):
            from app.ai.base import ProviderResult

            widest = max(
                Image.open(BytesIO(image.data)).size[0] for image in images
            )
            seen["width"] = widest
            return ProviderResult(suggestions=[])

    monkeypatch.setattr(factory, "get_provider", lambda s: Capturing())
    settings.ai_max_image_px = 512

    big = Image.new("RGB", (2400, 1600), (70, 110, 90))
    buffer = BytesIO()
    big.save(buffer, format="JPEG")

    client.post(
        "/assess/suggest",
        data={"site_id": site_id},
        files={"upstream": ("up.jpg", buffer.getvalue(), "image/jpeg")},
    )
    assert seen["width"] <= 512, f"sent {seen['width']}px to the provider"
