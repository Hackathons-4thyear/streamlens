"""Generate (or refresh) eval/labels.csv: the template for your own answers.

One row per photo per AI-suggestable question, pre-filled with everything except
the answer. You fill in the `code` column only.

Re-running this is safe: codes you have already written are carried across, so
you can drop new photos into eval/photos/ and regenerate without losing work.

Usage:
    python eval/make_labels.py
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

EVAL_DIR = Path(__file__).resolve().parent
REPO_ROOT = EVAL_DIR.parent
PHOTOS_DIR = EVAL_DIR / "photos"
LABELS_PATH = EVAL_DIR / "labels.csv"

sys.path.insert(0, str(REPO_ROOT / "api"))

from app.questions import get_questions  # noqa: E402

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif"}

FIELDNAMES = [
    "photo",
    "question_id",
    "question",
    "type",
    "allowed_codes",
    "code",
]


def find_photos(directory: Path | None = None) -> list[str]:
    folder = directory or PHOTOS_DIR
    if not folder.exists():
        return []
    return sorted(
        p.name
        for p in folder.iterdir()
        if p.is_file() and p.suffix.lower() in IMAGE_SUFFIXES
    )


def read_existing(path: Path | None = None) -> dict[tuple[str, str], str]:
    """Codes already filled in, keyed by (photo, question_id)."""
    target = path or LABELS_PATH
    if not target.exists():
        return {}
    existing: dict[tuple[str, str], str] = {}
    with target.open(encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            code = (row.get("code") or "").strip()
            if code:
                existing[(row["photo"], row["question_id"])] = code
    return existing


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build eval/labels.csv")
    parser.add_argument("--photos-dir", default="",
                        help="read photos from here instead of eval/photos/")
    parser.add_argument("--out", default="",
                        help="write the CSV here instead of eval/labels.csv")
    args = parser.parse_args(argv)

    photos_dir = Path(args.photos_dir) if args.photos_dir else PHOTOS_DIR
    out_path = Path(args.out) if args.out else LABELS_PATH

    photos = find_photos(photos_dir)
    if not photos:
        print(f"No images found in {photos_dir}.")
        print("Put your stream photos there (.jpg/.png/.webp), then run this again.")
        return 1

    questions = get_questions()
    suggestable = sorted(questions.suggestable, key=lambda q: q.raw.get("order", 0))
    existing = read_existing(out_path)

    rows = []
    for photo in photos:
        for question in suggestable:
            rows.append(
                {
                    "photo": photo,
                    "question_id": question.id,
                    "question": question.raw["label"].get("en", question.id),
                    "type": "choose ALL" if question.is_multi else "choose ONE",
                    "allowed_codes": " ".join(question.codes),
                    "code": existing.get((photo, question.id), ""),
                }
            )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)

    kept = sum(1 for row in rows if row["code"])
    print(f"Wrote {len(rows)} rows to {out_path}")
    print(f"  {len(photos)} photos x {len(suggestable)} AI-suggestable questions")
    if kept:
        print(f"  kept {kept} codes you had already filled in")
    print()
    print("Fill in the 'code' column using the codes in 'allowed_codes'.")
    print("For 'choose ALL' questions, separate codes with a semicolon: SB;RF")
    print("Leave a row blank if you cannot tell from the photo either - a blank")
    print("row is skipped, and is not counted against the model.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
