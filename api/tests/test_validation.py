"""Answer validation: the gate that stops an invented code reaching a citizen."""

from __future__ import annotations

import pytest

from app.ai.base import RawSuggestion
from app.routers.assess import validate_suggestions


# --------------------------------------------------------------------------
# The catalogue itself
# --------------------------------------------------------------------------

def test_catalogue_loads(questions):
    assert len(questions.questions) == 23
    assert questions.get("channelType") is not None


def test_every_question_has_options_and_provenance(questions):
    for question in questions.questions.values():
        assert question.codes, f"{question.id} has no options"
        assert question.raw["source"], f"{question.id} has no source"
        for option in question.raw["options"]:
            assert option["source"], f"{question.id}/{option['code']} has no source"


def test_unknown_answer_available_on_single_choice_questions(questions):
    for question in questions.questions.values():
        if question.is_multi or question.id == "overall":
            continue
        assert "NS" in question.codes, f"{question.id} offers no 'not sure' answer"


def test_overall_is_never_ai_suggestable(questions):
    overall = questions.get("overall")
    assert overall is not None
    assert overall.ai_suggestable is False
    assert set(overall.codes) == {"GOOD", "MODERATE", "POOR"}


# --------------------------------------------------------------------------
# validate / validate_answer
# --------------------------------------------------------------------------

@pytest.mark.parametrize(
    ("question_id", "code", "expected"),
    [
        ("channelType", "NAT", True),
        ("channelType", "ART", True),
        ("channelType", "NS", True),
        ("channelType", "CONCRETE", False),  # a plausible-looking invention
        ("channelType", "nat", False),  # codes are case-sensitive
        ("nosuchquestion", "NAT", False),
        ("overall", "GOOD", True),
        ("overall", "EXCELLENT", False),
    ],
)
def test_validate_single_codes(questions, question_id, code, expected):
    ok, reason = questions.validate(question_id, code)
    assert ok is expected
    if not ok:
        assert reason


def test_single_answer_question_rejects_two_codes(questions):
    ok, reason = questions.validate_answer("channelType", ["NAT", "ART"])
    assert ok is False
    assert "single answer" in reason


def test_multi_answer_question_accepts_several_codes(questions):
    ok, _ = questions.validate_answer("habitats", ["SB", "RF"])
    assert ok is True


def test_empty_answer_is_rejected(questions):
    ok, reason = questions.validate_answer("channelType", [])
    assert ok is False
    assert "no answer" in reason


# --------------------------------------------------------------------------
# validate_suggestions: what a provider is allowed to put on screen
# --------------------------------------------------------------------------

def _raw(question_id: str, codes: list[str], confidence: float = 0.9) -> RawSuggestion:
    return RawSuggestion(question_id, codes, confidence, "because the photo shows it")


def test_valid_suggestion_becomes_a_chip(questions):
    chips, dropped = validate_suggestions(
        [_raw("channelType", ["ART"])], questions, 0.55, True
    )
    assert dropped == []
    assert len(chips) == 1
    assert chips[0].suggested_code == "ART"
    assert chips[0].needs_review is False


def test_invented_code_is_dropped(questions):
    chips, dropped = validate_suggestions(
        [_raw("channelType", ["CONCRETE"])], questions, 0.55, True
    )
    assert chips == []
    assert len(dropped) == 1
    assert "not an option" in dropped[0].why


def test_unknown_question_is_dropped(questions):
    chips, dropped = validate_suggestions(
        [_raw("waterSmellsBad", ["Y"])], questions, 0.55, True
    )
    assert chips == []
    assert dropped[0].why == "no such question"


def test_ai_cannot_suggest_the_overall_rating(questions):
    """The central rule of the product, enforced in code and not only in the prompt."""
    chips, dropped = validate_suggestions(
        [_raw("overall", ["POOR"], 0.99)], questions, 0.55, True
    )
    assert chips == []
    assert len(dropped) == 1
    assert "never suggested" in dropped[0].why


def test_duplicate_suggestions_are_dropped(questions):
    chips, dropped = validate_suggestions(
        [_raw("channelType", ["NAT"]), _raw("channelType", ["ART"])], questions, 0.55, True
    )
    assert len(chips) == 1
    assert chips[0].suggested_code == "NAT"
    assert dropped[0].why == "duplicate suggestion"


def test_extra_codes_on_a_single_choice_question_are_dropped(questions):
    chips, dropped = validate_suggestions(
        [_raw("channelType", ["NAT", "ART"])], questions, 0.55, True
    )
    assert chips == []
    assert "single-answer" in dropped[0].why


def test_multi_choice_codes_are_split_into_primary_and_additional(questions):
    chips, dropped = validate_suggestions(
        [_raw("habitats", ["SB", "RF", "SD"])], questions, 0.55, True
    )
    assert dropped == []
    assert chips[0].suggested_code == "SB"
    assert chips[0].additional_codes == ["RF", "SD"]


def test_low_confidence_is_flagged_for_review(questions):
    chips, _ = validate_suggestions(
        [_raw("channelType", ["ART"], 0.2)], questions, 0.55, True
    )
    assert chips[0].needs_review is True
    assert "not confident" in chips[0].review_reason


def test_not_sure_is_flagged_for_review(questions):
    chips, _ = validate_suggestions(
        [_raw("channelType", ["NS"], 0.9)], questions, 0.55, True
    )
    assert chips[0].needs_review is True


def test_bad_photos_flag_every_chip_for_review(questions):
    chips, _ = validate_suggestions(
        [_raw("channelType", ["ART"], 0.99)], questions, 0.55, photos_ok=False
    )
    assert chips[0].needs_review is True
    assert "photo quality" in chips[0].review_reason


def test_confidence_is_clamped_into_range(questions):
    chips, _ = validate_suggestions(
        [_raw("channelType", ["ART"], 4.2)], questions, 0.55, True
    )
    assert chips[0].confidence == 1.0


def test_chips_come_back_in_catalogue_order(questions):
    chips, _ = validate_suggestions(
        [_raw("sewage", ["N"]), _raw("channelForm", ["FLAT"]), _raw("bankType", ["NAT"])],
        questions, 0.55, True,
    )
    order = [questions.get(c.question_id).raw["order"] for c in chips]
    assert order == sorted(order)
