"""Write eval/labels.csv from labels made by viewing each photograph.

These labels were produced by Claude (the coding agent) opening every image and
answering only what was clearly visible, BEFORE any Gemini output existed for
these photographs. They are an independent second opinion, not ground truth and
not a human expert's judgement.

Two rules were followed throughout:

0. **Litter is labelled only where the view is close and clear enough that
   litter would be obvious if present.** On a wide or distant shot a blank is
   honest: small items are simply not resolvable, and marking such a photo
   "NONE" would punish a model for seeing something real.
1. **Blank when unsure.** A blank cell means "I could not tell from this photo
   either", and the scorer skips it. It is not counted against the model.
2. **Left/right only when both banks agree.** The photographs carry no flow
   direction, so "left" and "right" cannot be assigned reliably. Bank questions
   are answered only where both banks clearly have the SAME answer, which makes
   the assignment irrelevant. Otherwise they are left blank.

Photographs with no visible watercourse - artwork, diagrams, plant close-ups,
dry hillsides - carry no labels at all. They are kept in the run as negative
controls: the prompt tells the model to stay silent on such images, and the
report counts how often it does.

Usage:
    python eval/write_labels.py
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

EVAL_DIR = Path(__file__).resolve().parent
REPO_ROOT = EVAL_DIR.parent
PHOTOS_DIR = EVAL_DIR / "photos"
LABELS_PATH = EVAL_DIR / "labels.csv"

sys.path.insert(0, str(REPO_ROOT / "api"))

from app.questions import get_questions  # noqa: E402

LABELLER = "claude-code"

# Photographs that do not show a watercourse. Kept, deliberately unlabelled.
NEGATIVE_CONTROLS = {
    "pollution_03.jpg": "a BOD/DO line chart, not a photograph",
    "pollution_02.jpg": "aerial of an open-sea slick; no channel or bank",
    "outfall_01.jpg": "coastal outfall on a rocky shore; sea, not a stream",
    "gabion_01.jpg": "gabion wall in a grass field; no water",
    "gabion_02.jpg": "close-up of gabion stone; no water",
    "riparian_01.jpg": "arid canyon landscape; no visible watercourse",
    "riparian_02.jpg": "arid canyon landscape; no visible watercourse",
    "rapids_01.jpg": "a printed postcard, not a photograph",
    "rapids_02.jpg": "a 19th-century engraving, not a photograph",
    "woodydebris_01.jpg": "mossy log in woodland; no channel",
    "erosion_01.jpg": "hillside landslip above houses; no channel",
    "giantreed_01.jpg": "giant reed beside a beach; no channel",
    "giantreed_02.jpg": "giant reed in grassland; no channel",
    "litter_01.jpg": "aerosol can on a sea beach; no channel",
    "litter_02.jpg": "derelict urban courtyard full of dumped waste; no water, and a "
                     "person in frame",
}

# What each labelled photograph shows, and the answers that were clear in it.
LABELS: dict[str, dict[str, str]] = {
    # Wide river, wooded earth banks both sides, gravel bar, green turbid water.
    "benevento_01.jpg": {
        "channelForm": "FLAT", "bankType": "NAT", "habitats": "SB",
        "waterAspect": "MU", "dams": "N", "pollutedPipes": "N", "sewage": "N",
        "construction": "N", "imperviousL": "N", "imperviousR": "N",
        "vegCoverL": "Y", "vegCoverR": "Y", "vegDominantL": "T", "vegDominantR": "T",
    },
    # Shallow clear pool, cobble bed visible through the water, trees both sides.
    "benevento_02.jpg": {
        "litter": "NONE",
        "channelType": "NAT", "habitats": "SD", "waterAspect": "CL",
        "dams": "N", "pollutedPipes": "N", "sewage": "N", "construction": "N",
        "imperviousL": "N", "imperviousR": "N",
        "vegCoverL": "Y", "vegCoverR": "Y", "vegDominantL": "T", "vegDominantR": "T",
    },
    # Hydro intake with sluice gates and a fish pass; tarmac apron.
    "toulouse_01.jpg": {
        "bankType": "ART", "dams": "Y", "fallenBiomass": "NONE",
        "pollutedPipes": "N", "sewage": "N", "construction": "N",
    },
    # Historic black-and-white view: stone quay wall, bridge, moored boats.
    "toulouse_02.jpg": {
        "bankType": "ART", "dams": "N", "pollutedPipes": "N", "sewage": "N",
        "construction": "N",
    },
    # Harbour shore under construction: excavator, rubble, containment boom.
    "oslo_01.jpg": {
        "construction": "Y", "sewage": "N",
    },
    # Fast broken water over a shallow reach, wooded both sides, fallen tree.
    "oslo_02.jpg": {
        "litter": "NONE",
        "waterFlow": "FAS", "channelType": "NAT", "bankType": "NAT",
        "habitats": "RF", "fallenBiomass": "FT",
        "dams": "N", "pollutedPipes": "N", "sewage": "N", "construction": "N",
        "imperviousL": "N", "imperviousR": "N",
        "vegCoverL": "Y", "vegCoverR": "Y", "vegDominantL": "T", "vegDominantR": "T",
    },
    # Newly built drainage swale: concrete walls, erosion matting, dry gravel line.
    "pollution_01.jpg": {
        "waterFlow": "DRY", "bankType": "ART", "construction": "Y",
        "pollutedPipes": "N", "sewage": "N",
    },
    # River sluice/outfall structure, sheet piling, brown turbid water, mud banks.
    "outfall_02.jpg": {
        "bankType": "ART", "dams": "Y", "waterAspect": "MU",
        "pollutedPipes": "N", "sewage": "N", "construction": "N",
    },
    # Concrete weir across a forested river, boulders upstream, brown water.
    "weir_01.jpg": {
        "bankType": "ART", "dams": "Y", "waterAspect": "MU", "habitats": "SD",
        "pollutedPipes": "N", "sewage": "N", "construction": "N",
    },
    # Close crop of water pouring over a weir crest, autumn leaves caught on it.
    "weir_02.jpg": {
        "channelType": "ART", "dams": "Y", "fallenBiomass": "FL", "waterFlow": "FAS",
    },
    # Urban canal: concrete retaining wall, sluice gates, still dark water.
    "culvert_01.jpg": {
        "litter": "NONE",
        "bankType": "ART", "dams": "Y", "waterFlow": "STA",
        "pollutedPipes": "N", "sewage": "N", "construction": "N",
    },
    # Dried-out river channel with stranded boats and rice seedlings.
    "drybed_01.jpg": {
        "litter": "SOME",
        "waterFlow": "DRY", "channelType": "NAT",
        "sewage": "N", "construction": "N",
    },
    # Thick green algal scum over still water among reeds and fallen branches.
    "algae_01.jpg": {
        "waterAspect": "CO", "waterFlow": "STA", "channelType": "NAT",
        "habitats": "AV", "fallenBiomass": "FB",
    },
    # Rocky river bed with shallow pools; a dam visible upstream; wooded banks.
    "streambed_01.jpg": {
        "channelType": "NAT", "habitats": "SD", "waterAspect": "CL", "dams": "Y",
        "pollutedPipes": "N", "sewage": "N", "construction": "N",
        "vegCoverL": "Y", "vegCoverR": "Y", "vegDominantL": "T", "vegDominantR": "T",
    },
    # Dry stony streambed running through woodland.
    "streambed_02.jpg": {
        "litter": "NONE",
        "waterFlow": "DRY", "channelType": "NAT", "bankType": "NAT",
        "pollutedPipes": "N", "sewage": "N", "construction": "N",
        "imperviousL": "N", "imperviousR": "N",
        "vegCoverL": "Y", "vegCoverR": "Y", "vegDominantL": "T", "vegDominantR": "T",
    },
    # Tree-lined navigation canal with grassy earth banks and a gravel towpath.
    "canal_01.jpg": {
        "bankType": "NAT", "waterAspect": "MU",
        "habitats": "NONE", "fallenBiomass": "NONE",
        "dams": "N", "pollutedPipes": "N", "sewage": "N", "construction": "N",
        "imperviousL": "N", "imperviousR": "N",
        "vegCoverL": "Y", "vegCoverR": "Y", "vegDominantL": "T", "vegDominantR": "T",
    },
}

FIELDNAMES = [
    "photo", "question_id", "question", "type", "allowed_codes", "code",
    "labeller", "photo_usable",
]


def main() -> int:
    questions = get_questions()
    suggestable = sorted(questions.suggestable, key=lambda q: q.raw.get("order", 0))
    photos = sorted(p.name for p in PHOTOS_DIR.glob("*.jpg"))
    if not photos:
        print(f"No photos in {PHOTOS_DIR}")
        return 1

    unknown = set(LABELS) | set(NEGATIVE_CONTROLS)
    missing = unknown - set(photos)
    if missing:
        print(f"WARNING: labels reference photos that are not on disk: {sorted(missing)}")

    rows = []
    for photo in photos:
        usable = "no" if photo in NEGATIVE_CONTROLS else "yes"
        answers = LABELS.get(photo, {})
        for question in suggestable:
            code = answers.get(question.id, "")
            if code:
                ok, why = questions.validate_answer(question.id, code.split(";"))
                if not ok:
                    raise SystemExit(f"bad label {photo}/{question.id}={code}: {why}")
            rows.append({
                "photo": photo,
                "question_id": question.id,
                "question": question.raw["label"].get("en", question.id),
                "type": "choose ALL" if question.is_multi else "choose ONE",
                "allowed_codes": " ".join(question.codes),
                "code": code,
                "labeller": LABELLER,
                "photo_usable": usable,
            })

    with LABELS_PATH.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)

    filled = sum(1 for r in rows if r["code"])
    labelled_photos = len(LABELS)
    controls = sum(1 for p in photos if p in NEGATIVE_CONTROLS)
    print(f"Wrote {len(rows)} rows to {LABELS_PATH}")
    print(f"  {len(photos)} photos: {labelled_photos} labelled, {controls} negative controls")
    print(f"  {filled} answers filled, labeller={LABELLER}")
    per_photo = {p: sum(1 for r in rows if r['photo'] == p and r['code']) for p in photos}
    for photo in sorted(per_photo, key=lambda p: -per_photo[p]):
        if per_photo[photo]:
            print(f"    {photo:22s} {per_photo[photo]:2d} labels")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
