"""POST /observations - what the citizen decided is what gets stored."""

from __future__ import annotations

import json

from tests.conftest import green_image, sharp_image


def _payload(site_id: str, **overrides) -> dict:
    body = {
        "site_id": site_id,
        "overall": "MODERATE",
        "consent_given": True,
        "lang": "en",
        "emotions": {"joy": 2, "serenity": 3, "anger": 0, "fear": 1},
        "answers": [
            {
                "question_id": "channelType",
                "codes": ["NAT"],
                "ai_suggested_code": "ART",
                "ai_confidence": 0.62,
            },
            {
                "question_id": "bankType",
                "codes": ["NAT"],
                "ai_suggested_code": "NAT",
                "ai_confidence": 0.81,
            },
            {"question_id": "habitats", "codes": ["SB", "RF"]},
        ],
        "ai_provider": "mock",
        "ai_model": "heuristic-colour-v1",
    }
    body.update(overrides)
    return body


def _post(client, payload, files=None):
    return client.post(
        "/observations", data={"payload": json.dumps(payload)}, files=files
    )


# --------------------------------------------------------------------------

def test_observation_is_stored_and_returned(client, site_id):
    response = _post(client, _payload(site_id))
    assert response.status_code == 201
    body = response.json()

    assert body["site_id"] == site_id
    assert body["overall"] == "MODERATE"
    assert body["site_name"]
    assert len(body["answers"]) == 3
    assert body["emotions"]["serenity"] == 3


def test_disagreement_with_the_ai_is_recorded(client, site_id):
    """Both the citizen's answer and the AI's suggestion are kept, so the two
    can be compared later rather than the model's version quietly winning."""
    body = _post(client, _payload(site_id)).json()

    by_id = {a["question_id"]: a for a in body["answers"]}
    assert by_id["channelType"]["codes"] == ["NAT"]
    assert by_id["channelType"]["ai_suggested_code"] == "ART"
    assert by_id["channelType"]["agreed_with_ai"] is False
    assert by_id["bankType"]["agreed_with_ai"] is True
    assert by_id["habitats"]["agreed_with_ai"] is None  # the AI said nothing here

    assert body["ai_agreement"] == 0.5  # one of the two judged answers was kept


def test_observation_can_be_read_back(client, site_id):
    created = _post(client, _payload(site_id)).json()
    fetched = client.get(f"/observations/{created['id']}").json()
    assert fetched["id"] == created["id"]
    assert len(fetched["answers"]) == 3


def test_photos_are_stored_stripped_and_downscaled(client, site_id, settings):
    response = _post(
        client,
        _payload(site_id),
        files={
            "upstream": ("up.jpg", sharp_image(), "image/jpeg"),
            "downstream": ("down.jpg", green_image(), "image/jpeg"),
        },
    )
    body = response.json()
    assert [p["role"] for p in body["photos"]] == ["upstream", "downstream"]
    assert all(p["exif_stripped"] for p in body["photos"])

    stored = list(settings.upload_path.glob("*.jpg"))
    assert len(stored) == 2
    assert all(f.stat().st_size > 0 for f in stored)


def test_consent_is_required(client, site_id):
    response = _post(client, _payload(site_id, consent_given=False))
    assert response.status_code == 422


def test_an_invented_answer_code_is_refused(client, site_id):
    payload = _payload(site_id)
    payload["answers"][0]["codes"] = ["CONCRETE"]
    response = _post(client, payload)
    assert response.status_code == 422
    assert "invalid_answers" in response.json()["detail"]


def test_an_invented_rating_is_refused(client, site_id):
    response = _post(client, _payload(site_id, overall="EXCELLENT"))
    assert response.status_code == 422


def test_the_rating_must_be_sent_as_the_citizens_own_field(client, site_id):
    payload = _payload(site_id)
    payload["answers"].append({"question_id": "overall", "codes": ["GOOD"]})
    response = _post(client, payload)
    assert response.status_code == 422
    assert "overall" in str(response.json()["detail"])


def test_unknown_site_is_refused(client, site_id):
    assert _post(client, _payload("NOT-A-SITE")).status_code == 404


def test_unknown_emotion_is_refused(client, site_id):
    response = _post(client, _payload(site_id, emotions={"rage": 3}))
    assert response.status_code == 422


def test_synthetic_records_keep_their_label(client, site_id):
    body = _post(client, _payload(site_id, synthetic=True)).json()
    assert body["synthetic"] is True

    listed = client.get("/observations").json()
    assert listed[0]["synthetic"] is True

    real_only = client.get("/observations", params={"include_synthetic": False}).json()
    assert real_only == []


def test_observations_can_be_listed_by_site(client, site_id, sites):
    _post(client, _payload(site_id))
    other = sites.all()[1]["id"]
    _post(client, _payload(other))

    listed = client.get("/observations", params={"site_id": site_id}).json()
    assert len(listed) == 1
    assert listed[0]["site_id"] == site_id


def test_a_quest_completion_travels_from_the_form_to_the_points(client, site_id):
    """The whole path the citizen takes: tap a quest, assess, see the award.

    The unit tests cover the scoring rule; this covers the wiring around it,
    which is where a renamed field would otherwise go unnoticed.
    """
    me = "device-quest-1"
    posted = _post(
        client,
        _payload(site_id, client_id=me, completed_quest="stale_site"),
        files=[
            ("upstream", ("upstream.jpg", sharp_image(), "image/jpeg")),
            ("downstream", ("downstream.jpg", sharp_image(), "image/jpeg")),
        ],
    )
    assert posted.status_code == 201

    mine = client.get("/points/me", params={"client_id": me}).json()
    assert mine["observations"] == 1

    awards = mine["awards"][0]["awards"]
    quest_award = [a for a in awards if a["rule_id"] == "quest_completed"]
    assert quest_award, awards
    assert quest_award[0]["points"] > 0
    assert "stale_site" in quest_award[0]["detail"]
    assert mine["total_points"] >= quest_award[0]["points"]


def test_points_are_not_awarded_for_a_quest_that_was_not_taken(client, site_id):
    me = "device-quest-2"
    _post(client, _payload(site_id, client_id=me))

    mine = client.get("/points/me", params={"client_id": me}).json()
    awards = mine["awards"][0]["awards"]
    assert [a for a in awards if a["rule_id"] == "quest_completed"] == []


def test_another_devices_points_are_not_mine(client, site_id):
    _post(client, _payload(site_id, client_id="device-a", completed_quest="stale_site"))

    mine = client.get("/points/me", params={"client_id": "device-b"}).json()
    assert mine["observations"] == 0
    assert mine["total_points"] == 0
