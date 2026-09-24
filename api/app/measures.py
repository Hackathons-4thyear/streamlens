"""The measures catalogue: observable problems -> what can be done about them.

Loaded from data/measures.json, which carries its own provenance. This module
does the lookup and nothing else; it invents no measures and makes no claims
the file does not already carry.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from .config import DATA_DIR

MEASURES_PATH = DATA_DIR / "measures.json"


class MeasureSet:
    def __init__(self, doc: dict[str, Any]) -> None:
        self.doc = doc
        self.measures: dict[str, dict] = {m["id"]: m for m in doc.get("measures", [])}
        self.problems: dict[str, dict] = {p["id"]: p for p in doc.get("problems", [])}

    @property
    def catalogue(self) -> dict:
        return self.doc.get("catalogue", {})

    def problems_for_answers(self, answers: dict[str, set[str]]) -> list[dict]:
        """Which known problems the citizen answers at a site point to.

        `answers` maps question_id -> the set of codes citizens have confirmed.
        A problem is present when any of its detectors matches.
        """
        found = []
        for problem in self.doc.get("problems", []):
            hits = []
            for detector in problem.get("detected_by", []):
                seen = answers.get(detector["question_id"], set())
                matched = sorted(seen & set(detector["codes"]))
                if matched:
                    hits.append({
                        "question_id": detector["question_id"],
                        "codes": matched,
                    })
            if hits:
                found.append({**problem, "matched": hits})
        return found

    def measures_for(self, problem_ids: list[str]) -> list[dict]:
        """Measures addressing the given problems, each carrying why it is listed.

        Ordered by how many of the site's problems a measure addresses, so a
        single action that fixes several things is proposed first.
        """
        scores: dict[str, dict] = {}
        for problem_id in problem_ids:
            problem = self.problems.get(problem_id)
            if not problem:
                continue
            for rank, measure_id in enumerate(problem.get("measures", [])):
                measure = self.measures.get(measure_id)
                if not measure:
                    continue
                entry = scores.setdefault(measure_id, {
                    **measure,
                    "addresses": [],
                    "_best_rank": rank,
                })
                entry["addresses"].append({
                    "problem_id": problem_id,
                    "problem_name": problem["name"],
                })
                entry["_best_rank"] = min(entry["_best_rank"], rank)

        ordered = sorted(
            scores.values(),
            key=lambda m: (-len(m["addresses"]), m["_best_rank"], m["name"]),
        )
        for entry in ordered:
            entry.pop("_best_rank", None)
        return ordered


def load_measures(path: Path | None = None) -> MeasureSet:
    target = path or MEASURES_PATH
    with target.open(encoding="utf-8") as fh:
        return MeasureSet(json.load(fh))


@lru_cache
def get_measures() -> MeasureSet:
    return load_measures()
