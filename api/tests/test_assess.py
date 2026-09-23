"""POST /assess/suggest, with the AI provider mocked.

The provider is replaced in every test here, so nothing reaches a network and
the assertions are about our behaviour, not a model's.
"""

from __future__ import annotations

import pytest

from app.ai.base import ProviderResult, RawSuggestion
from app.routers import assess as assess_router
from tests.conftest import blurry_image, dark_image, green_image, sharp_image


class FakeProvider:
    """A provider that returns exactly what a test tells it to."""

    name = "fake"
    model = "fake-1"
    is_mock = False

    def __init__(self, suggestions, note="") -> None:
        self._result = ProviderResult(suggestions=suggestions, note=note)
        self.calls: list[tuple] = []

    def suggest(self, images, context):
        self.calls.append((images, context))
        return self._result


class ExplodingProvider:
    name = "boom"
    model = "boom-1"
    is_mock = False

    def suggest(self, images, context):
        raise RuntimeError("provider is down")


@pytest.fixture
def use_provider(monkeypatch):
    def _install(provider):
        monkeypatch.setattr(assess_router, "get_provider", lambda settings: provider)
        return provider

    return _install


def _post(client, site_id, files=None, **form):
    payload = {"site_id": site_id, **{k: str(v) for k, v in form.items()}}
    return client.post(
        "/assess/suggest",
        data=payload,
        files=files or {"upstream": ("up.jpg", sharp_image(), "image/jpeg")},
    )


# --------------------------------------------------------------------------

def test_suggest_returns_validated_chips(client, site_id, use_provider):
    use_provider(FakeProvider([
        RawSuggestion("channelType", ["ART"], 0.91, "The bed is flat grey concrete."),
        RawSuggestion("habitats", ["SB", "RF"], 0.7, "Sand and broken water are visible."),
    ]))

    response = _post(client, site_id)
    assert response.status_code == 200
    body = response.json()

    assert [c["question_id"] for c in body["suggestions"]] == ["channelType", "habitats"]
    assert body["suggestions"][0]["suggested_code"] == "ART"
    assert body["suggestions"][1]["additional_codes"] == ["RF"]
    assert body["dropped"] == []
    assert body["provider"] == "fake"
    assert body["is_mock"] is False
    assert body["prompt_version"] == "assess_v1"
    assert "suggestions only" in body["notice"]


def test_invalid_codes_are_dropped_not_shown(client, site_id, use_provider):
    use_provider(FakeProvider([
        RawSuggestion("channelType", ["CONCRETE"], 0.99, "invented code"),
        RawSuggestion("notAQuestion", ["Y"], 0.99, "invented question"),
        RawSuggestion("bankType", ["NAT"], 0.8, "Earth banks with roots."),
    ]))

    body = _post(client, site_id).json()
    assert [c["question_id"] for c in body["suggestions"]] == ["bankType"]
    assert {d["question_id"] for d in body["dropped"]} == {"channelType", "notAQuestion"}


def test_ai_suggesting_the_overall_rating_is_refused(client, site_id, use_provider):
    use_provider(FakeProvider([
        RawSuggestion("overall", ["POOR"], 1.0, "the model tried to rate the stream"),
    ]))

    body = _post(client, site_id).json()
    assert body["suggestions"] == []
    assert body["dropped"][0]["question_id"] == "overall"


def test_photo_quality_is_reported(client, site_id, use_provider):
    use_provider(FakeProvider([]))
    body = _post(client, site_id).json()

    quality = body["photo_quality"][0]
    assert quality["role"] == "upstream"
    assert quality["exif_stripped"] is True
    assert quality["blur_score"] > 0
    assert quality["ok"] is True


def test_blurry_photo_is_flagged(client, site_id, use_provider):
    use_provider(FakeProvider([]))
    body = _post(
        client, site_id, files={"upstream": ("up.jpg", blurry_image(), "image/jpeg")}
    ).json()

    codes = [i["code"] for i in body["photo_quality"][0]["issues"]]
    assert "blurry" in codes
    assert body["photo_quality"][0]["ok"] is False


def test_dark_photo_is_flagged(client, site_id, use_provider):
    use_provider(FakeProvider([]))
    body = _post(
        client, site_id, files={"upstream": ("up.jpg", dark_image(), "image/jpeg")}
    ).json()

    codes = [i["code"] for i in body["photo_quality"][0]["issues"]]
    assert "dark" in codes


def test_bad_photo_marks_suggestions_for_review(client, site_id, use_provider):
    use_provider(FakeProvider([
        RawSuggestion("channelType", ["ART"], 0.97, "very confident"),
    ]))
    body = _post(
        client, site_id, files={"upstream": ("up.jpg", blurry_image(), "image/jpeg")}
    ).json()

    assert body["suggestions"][0]["needs_review"] is True


def test_both_photos_are_accepted(client, site_id, use_provider):
    provider = use_provider(FakeProvider([]))
    body = _post(
        client,
        site_id,
        files={
            "upstream": ("up.jpg", sharp_image(), "image/jpeg"),
            "downstream": ("down.jpg", green_image(), "image/jpeg"),
        },
    ).json()

    assert [p["role"] for p in body["photo_quality"]] == ["upstream", "downstream"]
    images, _ = provider.calls[0]
    assert [i.role for i in images] == ["upstream", "downstream"]


def test_gps_far_from_the_site_is_flagged(client, site_id, sites, use_provider):
    use_provider(FakeProvider([]))
    site = sites.get(site_id)
    body = _post(client, site_id, lat=site["lat"] + 0.5, lon=site["lon"]).json()

    assert body["location"]["provided"] is True
    assert body["location"]["far_from_site"] is True
    assert body["location"]["distance_m"] > 250


def test_gps_at_the_site_is_not_flagged(client, site_id, sites, use_provider):
    use_provider(FakeProvider([]))
    site = sites.get(site_id)
    body = _post(client, site_id, lat=site["lat"], lon=site["lon"]).json()

    assert body["location"]["far_from_site"] is False
    assert body["location"]["distance_m"] < 1


def test_missing_gps_is_stated_not_guessed(client, site_id, use_provider):
    use_provider(FakeProvider([]))
    body = _post(client, site_id).json()
    assert body["location"]["provided"] is False
    assert body["location"]["distance_m"] is None


def test_unknown_site_is_404(client, use_provider):
    use_provider(FakeProvider([]))
    assert _post(client, "NOT-A-SITE").status_code == 404


def test_photo_is_required(client, site_id, use_provider):
    use_provider(FakeProvider([]))
    response = client.post("/assess/suggest", data={"site_id": site_id})
    assert response.status_code == 422


def test_a_file_that_is_not_an_image_is_rejected(client, site_id, use_provider):
    use_provider(FakeProvider([]))
    response = _post(
        client, site_id, files={"upstream": ("notes.txt", b"hello there", "image/jpeg")}
    )
    assert response.status_code == 422


def test_provider_failure_does_not_lose_the_visit(client, site_id, use_provider):
    use_provider(ExplodingProvider())
    response = _post(client, site_id)
    assert response.status_code == 502
    assert "yourself" in response.json()["detail"]


def test_the_prompt_carries_the_question_catalogue(client, site_id, use_provider):
    provider = use_provider(FakeProvider([]))
    _post(client, site_id)

    _, context = provider.calls[0]
    assert "channelType" in context.catalogue
    assert "overall" not in context.catalogue  # never offered to the model
    assert context.site_name


# --------------------------------------------------------------------------
# The mock provider, which the demo runs on
# --------------------------------------------------------------------------

def test_mock_provider_is_labelled_as_a_mock(client, site_id):
    body = _post(client, site_id).json()
    assert body["is_mock"] is True
    assert body["provider"] == "mock"
    assert "not a vision model" in body["provider_note"]


def test_mock_provider_output_is_valid_and_deterministic(client, site_id):
    first = _post(client, site_id, files={"upstream": ("u.jpg", green_image(), "image/jpeg")})
    second = _post(client, site_id, files={"upstream": ("u.jpg", green_image(), "image/jpeg")})

    a = [(c["question_id"], c["suggested_code"], c["confidence"]) for c in first.json()["suggestions"]]
    b = [(c["question_id"], c["suggested_code"], c["confidence"]) for c in second.json()["suggestions"]]
    assert a == b
    assert first.json()["dropped"] == []
    assert a, "the mock provider should suggest something"


def test_mock_provider_never_suggests_a_rating(client, site_id):
    body = _post(client, site_id).json()
    assert "overall" not in [c["question_id"] for c in body["suggestions"]]
