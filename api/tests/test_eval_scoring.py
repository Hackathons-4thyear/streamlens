"""The evaluation harness's scoring maths.

These numbers end up in a committed report that judges may read, so the
arithmetic is tested rather than trusted. No photos and no provider here - the
scorer is fed runs directly.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

EVAL_DIR = Path(__file__).resolve().parents[2] / "eval"
sys.path.insert(0, str(EVAL_DIR))

from run_eval import PhotoRun, read_labels, score  # noqa: E402


def _run(photo: str, chips: list[tuple[str, list[str], float]], dropped=()) -> PhotoRun:
    return PhotoRun(
        photo=photo,
        chips=[
            {
                "question_id": qid,
                "codes": codes,
                "confidence": conf,
                "reason": "",
                "needs_review": False,
            }
            for qid, codes, conf in chips
        ],
        dropped=[
            {"question_id": qid, "codes": codes, "why": "invalid"}
            for qid, codes in dropped
        ],
    )


# --------------------------------------------------------------------------
# Agreement
# --------------------------------------------------------------------------

def test_a_matching_code_counts_as_agreement():
    runs = [_run("a.jpg", [("channelType", ["ART"], 0.9)])]
    labels = {("a.jpg", "channelType"): {"ART"}}

    stats = score(runs, labels)
    assert stats["channelType"].labelled == 1
    assert stats["channelType"].correct == 1
    assert stats["channelType"].agreement == 1.0


def test_a_different_code_counts_against():
    runs = [_run("a.jpg", [("channelType", ["ART"], 0.9)])]
    labels = {("a.jpg", "channelType"): {"NAT"}}

    stats = score(runs, labels)
    assert stats["channelType"].correct == 0
    assert stats["channelType"].agreement == 0.0


def test_multi_answer_agreement_ignores_order():
    runs = [_run("a.jpg", [("habitats", ["RF", "SB"], 0.8)])]
    labels = {("a.jpg", "habitats"): {"SB", "RF"}}

    assert score(runs, labels)["habitats"].correct == 1


def test_a_partial_multi_answer_is_not_agreement():
    """Half the habitats is a different answer, not a better one."""
    runs = [_run("a.jpg", [("habitats", ["SB"], 0.8)])]
    labels = {("a.jpg", "habitats"): {"SB", "RF"}}

    assert score(runs, labels)["habitats"].correct == 0


def test_unlabelled_answers_are_not_counted_either_way():
    runs = [_run("a.jpg", [("channelType", ["ART"], 0.9)])]

    stats = score(runs, {})
    assert stats["channelType"].suggested == 1
    assert stats["channelType"].labelled == 0
    assert stats["channelType"].agreement is None


def test_labels_for_a_different_photo_do_not_leak():
    runs = [_run("a.jpg", [("channelType", ["ART"], 0.9)])]
    labels = {("b.jpg", "channelType"): {"ART"}}

    assert score(runs, labels)["channelType"].labelled == 0


# --------------------------------------------------------------------------
# Unknown and dropped rates
# --------------------------------------------------------------------------

def test_not_sure_answers_are_counted_as_unknown():
    runs = [
        _run("a.jpg", [("channelType", ["NS"], 0.3)]),
        _run("b.jpg", [("channelType", ["ART"], 0.9)]),
    ]
    stats = score(runs, {})
    assert stats["channelType"].suggested == 2
    assert stats["channelType"].unknown == 1
    assert stats["channelType"].unknown_rate == 0.5


def test_dropped_suggestions_are_counted_against_their_question():
    runs = [_run("a.jpg", [], dropped=[("channelType", ["CONCRETE"])])]
    stats = score(runs, {})
    assert stats["channelType"].dropped == 1
    assert stats["channelType"].suggested == 0


def test_a_failed_photo_contributes_nothing():
    failed = PhotoRun(photo="broken.jpg", ok=False, error="not an image")
    assert score([failed], {}) == {}


# --------------------------------------------------------------------------
# Calibration
# --------------------------------------------------------------------------

def test_confidences_are_split_by_whether_the_answer_was_right():
    runs = [
        _run("a.jpg", [("channelType", ["ART"], 0.9)]),
        _run("b.jpg", [("channelType", ["ART"], 0.4)]),
    ]
    labels = {
        ("a.jpg", "channelType"): {"ART"},  # right, confident
        ("b.jpg", "channelType"): {"NAT"},  # wrong, hesitant
    }

    stats = score(runs, labels)["channelType"]
    assert stats.confidences_right == [0.9]
    assert stats.confidences_wrong == [0.4]


# --------------------------------------------------------------------------
# Reading the label file
# --------------------------------------------------------------------------

def test_labels_are_read_and_split_on_semicolons(tmp_path):
    path = tmp_path / "labels.csv"
    path.write_text(
        "photo,question_id,question,type,allowed_codes,code\n"
        "a.jpg,habitats,Instream habitats,choose ALL,SB SI RF,SB;RF\n"
        "a.jpg,channelType,Channel bed,choose ONE,NAT ART NS,NAT\n"
        "a.jpg,bankType,Bank type,choose ONE,NAT ART NS,\n",
        encoding="utf-8",
    )

    labels = read_labels(path)
    assert labels[("a.jpg", "habitats")] == {"SB", "RF"}
    assert labels[("a.jpg", "channelType")] == {"NAT"}
    # A blank row is "I could not tell either" and is skipped entirely.
    assert ("a.jpg", "bankType") not in labels


def test_commas_work_as_a_separator_too(tmp_path):
    """Spreadsheets encourage commas; accept both rather than lose a label."""
    path = tmp_path / "labels.csv"
    path.write_text(
        "photo,question_id,question,type,allowed_codes,code\n"
        'a.jpg,habitats,H,choose ALL,SB RF,"SB, RF"\n',
        encoding="utf-8",
    )
    assert read_labels(path)[("a.jpg", "habitats")] == {"SB", "RF"}


def test_a_missing_label_file_is_not_an_error(tmp_path):
    assert read_labels(tmp_path / "nope.csv") == {}


@pytest.mark.parametrize("raw", ["  NAT  ", "NAT;", ";NAT"])
def test_untidy_cells_are_tolerated(tmp_path, raw):
    path = tmp_path / "labels.csv"
    path.write_text(
        "photo,question_id,question,type,allowed_codes,code\n"
        f'a.jpg,channelType,C,choose ONE,NAT ART,"{raw}"\n',
        encoding="utf-8",
    )
    assert read_labels(path)[("a.jpg", "channelType")] == {"NAT"}


# --------------------------------------------------------------------------
# Set overlap, for choose-ALL questions
# --------------------------------------------------------------------------

def test_a_correct_superset_earns_partial_credit_not_zero():
    """The model spotting a real feature the labeller missed is not the same
    error as naming the wrong thing, and the two should not score alike."""
    runs = [_run("a.jpg", [("habitats", ["SD", "RF"], 0.85)])]
    labels = {("a.jpg", "habitats"): {"SD"}}

    stats = score(runs, labels)["habitats"]
    assert stats.agreement == 0.0, "exact match is unchanged"
    assert stats.overlap == 0.5, "one of two codes shared"


def test_overlap_equals_exact_match_when_the_sets_are_identical():
    runs = [_run("a.jpg", [("habitats", ["SD", "RF"], 0.85)])]
    labels = {("a.jpg", "habitats"): {"RF", "SD"}}

    stats = score(runs, labels)["habitats"]
    assert stats.agreement == 1.0
    assert stats.overlap == 1.0


def test_overlap_is_zero_when_nothing_is_shared():
    runs = [_run("a.jpg", [("habitats", ["SB"], 0.8)])]
    labels = {("a.jpg", "habitats"): {"RF"}}

    stats = score(runs, labels)["habitats"]
    assert stats.overlap == 0.0


def test_single_answer_overlap_is_all_or_nothing():
    runs = [
        _run("a.jpg", [("channelType", ["NAT"], 0.9)]),
        _run("b.jpg", [("channelType", ["ART"], 0.9)]),
    ]
    labels = {
        ("a.jpg", "channelType"): {"NAT"},
        ("b.jpg", "channelType"): {"NAT"},
    }
    stats = score(runs, labels)["channelType"]
    assert stats.overlap == 0.5, "one of two photos matched, no partial credit within one"
