"""Build data/measures.json: observable problems -> restoration measures.

Measures, their names and their page numbers come from the OneAquaHealth
**Catalogue of measures for urban aquatic ecosystems rehabilitation** (D2.4),
DOI 10.5281/zenodo.20040211, CC-BY-4.0. Page numbers are the printed document
pages as listed in the PDF's own table of contents.

What is OURS and marked as such:

- the mapping from an observable problem (a citizen answer code) to a measure;
- the short plain-language descriptions written for citizens;
- the human-health co-benefit tags;
- the rough effort estimate.

The catalogue links rehabilitation to health in general terms (section 6,
p.132), not measure by measure, so the per-measure co-benefit tags are our
reading and are labelled `project judgement`. Nothing here invents a citation.

If the PDF is present the script VERIFIES that each cited page still carries the
measure's name, and refuses to write a citation it could not confirm. If the PDF
is absent it writes the file anyway and marks every citation `verified: false`.

Usage:
    python scripts/build_measures.py
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
OUT_PATH = REPO_ROOT / "data" / "measures.json"
PDF_PATH = REPO_ROOT / "data" / "sources" / "OAH_Catalogue_of_measures.pdf"

CATALOGUE = {
    "title": "D2.4 Catalogue of measures for urban aquatic ecosystems rehabilitation",
    "authors": "Dias, M., Serra, S.R.Q., Feio, M.J. (University of Coimbra)",
    "project": "OneAquaHealth, Horizon Europe, Grant Agreement 101086521",
    "date": "2025-12-22",
    "doi": "10.5281/zenodo.20040211",
    "url": "https://doi.org/10.5281/zenodo.20040211",
    "licence": "CC-BY-4.0",
    "page_note": (
        "Page numbers are the printed document pages from the catalogue's own "
        "table of contents. In this PDF, printed page N is sheet N+2."
    ),
}

# Printed page N is PDF sheet index N+1 (0-based) -> N+2 as a 1-based sheet.
PAGE_OFFSET = 1

OURS = "project judgement (StreamLens)"

# (id, name, section, page, type, keywords to confirm on the page)
MEASURES: list[dict] = [
    # --- riparian vegetation ---------------------------------------------
    {
        "id": "passive_riparian",
        "name": "Let the bank vegetation grow back on its own",
        "catalogue_name": "Passive riparian vegetation: allowing natural regeneration",
        "section": "4.1.1", "page": 32, "type": "nature-based", "effort": "low",
        "plain": "Stop mowing and clearing a strip along the bank and let whatever "
                 "grows there come back by itself. The cheapest measure in the catalogue.",
        "ecosystem_benefit": "Shade, bank stability, leaf litter as food, cover for animals.",
        "health_cobenefits": ["cooling", "wellbeing"],
        "confirm": ["passive", "regeneration"],
    },
    {
        "id": "active_riparian",
        "name": "Replant the bank with native trees and shrubs",
        "catalogue_name": "Active riparian vegetation restoration",
        "section": "4.1.2", "page": 33, "type": "nature-based", "effort": "medium",
        "plain": "Plant native trees and shrubs along the bank where nothing is "
                 "regenerating on its own.",
        "ecosystem_benefit": "Shade that cools the water, roots that hold the bank, "
                             "habitat and a corridor for wildlife.",
        "health_cobenefits": ["cooling", "wellbeing", "recreation"],
        "confirm": ["active", "riparian"],
    },
    {
        "id": "riparian_buffer",
        "name": "Keep a planted buffer strip between the town and the water",
        "catalogue_name": "Constrained riparian vegetation corridors (buffers)",
        "section": "4.1.3", "page": 37, "type": "nature-based", "effort": "medium",
        "plain": "A planted strip between the built-up area and the water, even a "
                 "narrow one, to filter what runs off the land.",
        "ecosystem_benefit": "Filters runoff before it reaches the water; buffers the "
                             "channel from what happens on the land beside it.",
        "health_cobenefits": ["cooling", "wellbeing"],
        "confirm": ["buffer"],
    },
    # --- water quality -----------------------------------------------------
    {
        "id": "sewer_improvements",
        "name": "Fix the sewer connections and point discharges",
        "catalogue_name": "Sewer system and point-source improvements",
        "section": "4.2.2", "page": 42, "type": "structural", "effort": "high",
        "plain": "Find and fix misconnected or leaking pipes, and reduce discharges "
                 "from the sewer network into the stream.",
        "ecosystem_benefit": "Removes the pollution at source rather than treating it "
                             "downstream; the first-line measure for foul water.",
        "health_cobenefits": ["vector control", "recreation"],
        "confirm": ["sewer"],
    },
    {
        "id": "self_purification",
        "name": "Help the stream clean itself",
        "catalogue_name": "In-stream self-purification enhancement",
        "section": "4.2.1", "page": 41, "type": "nature-based", "effort": "medium",
        "plain": "Restore the riffles, gravels and plants that let a stream break "
                 "down pollutants through its own biology.",
        "ecosystem_benefit": "Higher oxygen and more biological processing of nutrients.",
        "health_cobenefits": ["recreation"],
        "confirm": ["purification"],
    },
    {
        "id": "litter_control",
        "name": "Litter, plastic and oil control",
        "catalogue_name": "Litter, plastic, and hydrocarbon control",
        "section": "4.2.3", "page": 43, "type": "structural", "effort": "low",
        "plain": "Traps, screens and regular clean-ups, together with stopping litter "
                 "entering from the street drains in the first place.",
        "ecosystem_benefit": "Less physical harm to animals; fewer pollutants leaching "
                             "into the water.",
        "health_cobenefits": ["wellbeing", "recreation"],
        "confirm": ["litter"],
    },
    {
        "id": "natural_wwtp",
        "name": "Treat waste water with a constructed wetland",
        "catalogue_name": "Natural wastewater treatment plants",
        "section": "4.7.1", "page": 105, "type": "nature-based", "effort": "high",
        "plain": "A reed bed or constructed wetland that treats waste water using "
                 "plants and soil instead of a chemical plant.",
        "ecosystem_benefit": "Removes nutrients and pathogens while itself being habitat.",
        "health_cobenefits": ["vector control", "wellbeing"],
        "confirm": ["wastewater"],
    },
    {
        "id": "floating_wetland",
        "name": "Floating treatment wetlands",
        "catalogue_name": "Floating treatment wetlands",
        "section": "4.7.2", "page": 107, "type": "nature-based", "effort": "medium",
        "plain": "Rafts of plants floating on the water whose roots strip out nutrients. "
                 "Useful where there is no room on the bank.",
        "ecosystem_benefit": "Nutrient uptake and shade in slow or standing reaches.",
        "health_cobenefits": ["wellbeing"],
        "confirm": ["floating"],
    },
    # --- barriers ----------------------------------------------------------
    {
        "id": "remove_barriers",
        "name": "Remove the barrier",
        "catalogue_name": "Removing barriers",
        "section": "4.3.1", "page": 47, "type": "structural", "effort": "high",
        "plain": "Take out a weir, dam or culvert that no longer serves a purpose, so "
                 "animals and sediment can move along the stream again.",
        "ecosystem_benefit": "Restores movement up and down the stream for fish and "
                             "invertebrates, and lets sediment through.",
        "health_cobenefits": ["recreation", "wellbeing"],
        "confirm": ["barrier"],
    },
    {
        "id": "pass_barriers",
        "name": "Make the barrier passable",
        "catalogue_name": "Passing barriers",
        "section": "4.3.2", "page": 49, "type": "structural", "effort": "high",
        "plain": "Where a barrier has to stay, add a fish pass or rock ramp so animals "
                 "can still get past it.",
        "ecosystem_benefit": "Partial restoration of movement where removal is not possible.",
        "health_cobenefits": ["recreation"],
        "confirm": ["passing", "barrier"],
    },
    # --- channel form ------------------------------------------------------
    {
        "id": "remeandering",
        "name": "Let the stream bend again",
        "catalogue_name": "Stream re-meandering",
        "section": "4.3.3", "page": 52, "type": "structural", "effort": "high",
        "plain": "Give a straightened channel its bends back, so it has fast and slow "
                 "stretches instead of one uniform chute.",
        "ecosystem_benefit": "Varied flow and depth, which is what creates varied habitat.",
        "health_cobenefits": ["recreation", "wellbeing"],
        "confirm": ["meander"],
    },
    {
        "id": "bed_renaturalization",
        "name": "Put a natural bed back",
        "catalogue_name": "Stream bed re-naturalization",
        "section": "4.3.4", "page": 53, "type": "structural", "effort": "high",
        "plain": "Replace a concrete bed with gravel, stone and sediment the stream "
                 "can move and sort by itself.",
        "ecosystem_benefit": "Restores the spaces between stones where stream animals live.",
        "health_cobenefits": ["recreation"],
        "confirm": ["bed"],
    },
    {
        "id": "constructed_riffles",
        "name": "Build riffles",
        "catalogue_name": "Constructed riffles",
        "section": "4.3.5", "page": 54, "type": "structural", "effort": "medium",
        "plain": "Add shallow stony stretches where water breaks over stones and "
                 "picks up oxygen.",
        "ecosystem_benefit": "Oxygenation and the habitat most invertebrates depend on.",
        "health_cobenefits": [],
        "confirm": ["riffle"],
    },
    # --- hardened banks ----------------------------------------------------
    {
        "id": "remove_bank_protection",
        "name": "Take the hard bank facing out",
        "catalogue_name": "Elimination of riverbank protection",
        "section": "4.3.8", "page": 66, "type": "structural", "effort": "high",
        "plain": "Remove concrete or stone facing from the bank where it is no longer "
                 "needed, and let the bank become soil and roots again.",
        "ecosystem_benefit": "Reconnects the water with the bank and its wildlife.",
        "health_cobenefits": ["cooling", "wellbeing"],
        "confirm": ["bank"],
    },
    {
        "id": "bank_regrading",
        "name": "Reshape a steep bank to a gentle slope",
        "catalogue_name": "Riverbank regrading",
        "section": "4.3.10", "page": 69, "type": "structural", "effort": "medium",
        "plain": "Slope a steep or undercut bank back so plants can root and people "
                 "can reach the water safely.",
        "ecosystem_benefit": "Stable bank with a planted margin instead of a bare face.",
        "health_cobenefits": ["recreation", "wellbeing"],
        "confirm": ["regrading"],
    },
    {
        "id": "live_fascines",
        "name": "Live fascines (bundles of living branches)",
        "catalogue_name": "Live fascines",
        "section": "4.3.13", "page": 73, "type": "nature-based", "effort": "medium",
        "plain": "Bundles of living willow branches laid along the bank; they root and "
                 "hold the soil, replacing stone or concrete.",
        "ecosystem_benefit": "Bank stability that is alive and gets stronger over time.",
        "health_cobenefits": ["cooling"],
        "confirm": ["fascine"],
    },
    {
        "id": "erosion_blanket",
        "name": "Erosion control blanket",
        "catalogue_name": "Erosion control blanket",
        "section": "4.3.20", "page": 85, "type": "nature-based", "effort": "low",
        "plain": "A biodegradable mat pinned over bare soil so it holds until planting "
                 "takes root.",
        "ecosystem_benefit": "Stops soil washing into the stream while vegetation establishes.",
        "health_cobenefits": [],
        "confirm": ["erosion"],
    },
    # --- runoff and impervious surfaces ------------------------------------
    {
        "id": "rain_gardens",
        "name": "Rain gardens",
        "catalogue_name": "Rain gardens",
        "section": "4.6.1", "page": 97, "type": "nature-based", "effort": "low",
        "plain": "Planted hollows that catch road and roof runoff and let it soak "
                 "away instead of rushing into the stream.",
        "ecosystem_benefit": "Cuts the flashy peak after rain and filters what is in it.",
        "health_cobenefits": ["cooling", "wellbeing"],
        "confirm": ["rain garden"],
    },
    {
        "id": "permeable_pavement",
        "name": "Permeable paving",
        "catalogue_name": "Permeable pavements",
        "section": "4.6.3", "page": 99, "type": "structural", "effort": "medium",
        "plain": "Surfaces rain can soak through, instead of tarmac that sends it "
                 "straight to the stream.",
        "ecosystem_benefit": "Less runoff volume and less of the pollution it carries.",
        "health_cobenefits": ["cooling"],
        "confirm": ["permeable"],
    },
    {
        "id": "disconnect_impervious",
        "name": "Disconnect the hard surfaces from the drain",
        "catalogue_name": "Disconnection of impervious areas",
        "section": "4.6.5", "page": 101, "type": "structural", "effort": "medium",
        "plain": "Route water from roofs and paving onto soil and planting rather than "
                 "into the storm drain.",
        "ecosystem_benefit": "Directly reduces the storm peak reaching the channel.",
        "health_cobenefits": ["cooling"],
        "confirm": ["impervious"],
    },
    {
        "id": "vegetated_swales",
        "name": "Vegetated swales",
        "catalogue_name": "Vegetated swales",
        "section": "4.6.6", "page": 102, "type": "nature-based", "effort": "medium",
        "plain": "Shallow planted channels that carry runoff slowly and clean it on "
                 "the way.",
        "ecosystem_benefit": "Slows and filters runoff before it reaches the stream.",
        "health_cobenefits": ["cooling", "wellbeing"],
        "confirm": ["swale"],
    },
    {
        "id": "retention_ponds",
        "name": "Retention ponds and floodable parks",
        "catalogue_name": "Retention ponds and floodable parks",
        "section": "4.6.7", "page": 103, "type": "nature-based", "effort": "high",
        "plain": "Places designed to hold water when it rains hard - often a park that "
                 "is allowed to flood.",
        "ecosystem_benefit": "Storm storage, plus wetland habitat the rest of the year.",
        "health_cobenefits": ["cooling", "recreation", "wellbeing"],
        "confirm": ["retention", "flood"],
    },
    {
        "id": "floodplain_reconnection",
        "name": "Reconnect the floodplain",
        "catalogue_name": "Floodplain reconnection and storage basins",
        "section": "4.3.21", "page": 86, "type": "nature-based", "effort": "high",
        "plain": "Let the stream spill onto its floodplain again instead of being held "
                 "inside walls.",
        "ecosystem_benefit": "Flood storage, sediment deposition and wet habitat.",
        "health_cobenefits": ["cooling", "recreation"],
        "confirm": ["floodplain"],
    },
    # --- invasives ---------------------------------------------------------
    {
        "id": "invasive_control",
        "name": "Control or remove invasive species",
        "catalogue_name": "Control / Removal of invasive species",
        "section": "4.5.1", "page": 93, "type": "nature-based", "effort": "high",
        "plain": "Remove invasive plants and replant with native species. Usually needs "
                 "repeating for several years to work.",
        "ecosystem_benefit": "Lets native bank vegetation and the animals that depend on "
                             "it re-establish.",
        "health_cobenefits": ["wellbeing"],
        "confirm": ["invasive"],
    },
    # --- people ------------------------------------------------------------
    {
        "id": "citizen_science",
        "name": "Citizen science and school partnerships",
        "catalogue_name": "Citizen Science and educational partnerships",
        "section": "4.4.2", "page": 90, "type": "nature-based", "effort": "low",
        "plain": "Keep people watching the stream - which is what StreamLens itself is "
                 "for. Sustained local attention is what keeps other measures maintained.",
        "ecosystem_benefit": "Continuous monitoring and earlier detection of problems.",
        "health_cobenefits": ["wellbeing", "recreation"],
        "confirm": ["citizen science"],
    },
]

# Observable problem -> the measures that address it, best first.
# The problem codes are citizen answers from data/questions.json.
PROBLEMS: list[dict] = [
    {
        "id": "hardened_banks",
        "name": "Paved or hardened banks",
        "detected_by": [{"question_id": "bankType", "codes": ["ART", "LAS"]}],
        "why_it_matters": "A concrete or stone bank has no roots, no burrows and no "
                          "plants, so the edge of the stream stops being habitat.",
        "measures": ["remove_bank_protection", "bank_regrading", "live_fascines",
                     "active_riparian"],
    },
    {
        "id": "channelised",
        "name": "Concrete or artificial bed",
        "detected_by": [{"question_id": "channelType", "codes": ["ART"]}],
        "why_it_matters": "A hard flat bed has none of the gaps between stones where "
                          "stream insects live, and water runs over it too fast.",
        "measures": ["bed_renaturalization", "constructed_riffles", "remeandering"],
    },
    {
        "id": "no_riparian_vegetation",
        "name": "Bare or unvegetated banks",
        "detected_by": [{"question_id": "vegCoverL", "codes": ["N"]},
                        {"question_id": "vegCoverR", "codes": ["N"]}],
        "why_it_matters": "Without plants the water is unshaded and warmer, the bank "
                          "erodes, and nothing filters what runs off the land.",
        "measures": ["passive_riparian", "active_riparian", "riparian_buffer",
                     "erosion_blanket"],
    },
    {
        "id": "sewage",
        "name": "Sewage or a polluted outfall",
        "detected_by": [{"question_id": "sewage", "codes": ["Y"]},
                        {"question_id": "pollutedPipes", "codes": ["Y"]}],
        "why_it_matters": "Foul water strips oxygen from the stream and is the pressure "
                          "most likely to matter to people living nearby.",
        "measures": ["sewer_improvements", "natural_wwtp", "floating_wetland",
                     "self_purification"],
    },
    {
        "id": "barriers",
        "name": "Barriers blocking the stream",
        "detected_by": [{"question_id": "dams", "codes": ["Y"]}],
        "why_it_matters": "A weir or culvert stops fish and invertebrates moving up and "
                          "down, cutting populations off from each other.",
        "measures": ["remove_barriers", "pass_barriers"],
    },
    {
        "id": "litter",
        "name": "Litter in or beside the channel",
        "detected_by": [{"question_id": "waterAspect", "codes": ["CO"]}],
        "detection_note": "StreamLens has no dedicated litter question yet; this is "
                          "currently inferred and should get its own question.",
        "why_it_matters": "Litter harms animals directly and is the strongest visible "
                          "signal to residents that a stream is neglected.",
        "measures": ["litter_control", "citizen_science"],
    },
    {
        "id": "impervious_surroundings",
        "name": "Sealed surfaces right up to the bank",
        "detected_by": [{"question_id": "imperviousL", "codes": ["Y"]},
                        {"question_id": "imperviousR", "codes": ["Y"]}],
        "why_it_matters": "Rain runs straight off tarmac into the stream, carrying "
                          "whatever was on the surface and causing a flashy surge.",
        "measures": ["rain_gardens", "disconnect_impervious", "permeable_pavement",
                     "vegetated_swales"],
    },
    {
        "id": "invasive_plants",
        "name": "Invasive plants on the banks",
        "detected_by": [{"question_id": "invasiveL", "codes": ["Y"]},
                        {"question_id": "invasiveR", "codes": ["Y"]}],
        "why_it_matters": "Species such as giant reed or knotweed crowd out native "
                          "plants and leave banks bare when they die back.",
        "measures": ["invasive_control", "active_riparian"],
    },
    {
        "id": "low_or_no_flow",
        "name": "Standing or dry channel",
        "detected_by": [{"question_id": "waterFlow", "codes": ["STA", "DRY"]}],
        "why_it_matters": "Water that does not move warms up, loses oxygen and can "
                          "become mosquito habitat.",
        "measures": ["floodplain_reconnection", "retention_ponds", "rain_gardens",
                     "riparian_buffer"],
    },
    {
        "id": "no_instream_habitat",
        "name": "No habitat features in the water",
        "detected_by": [{"question_id": "habitats", "codes": ["NONE"]}],
        "why_it_matters": "A uniform channel with no stones, bars or plants supports "
                          "very few species however clean the water is.",
        "measures": ["constructed_riffles", "bed_renaturalization", "remeandering"],
    },
]


def verify_pages() -> tuple[dict[str, bool], str]:
    """Confirm each cited page really names its measure. Best effort."""
    if not PDF_PATH.exists():
        return {}, "not-verified (PDF absent; see data/README.md to fetch it)"
    try:
        from pypdf import PdfReader
    except ImportError:
        return {}, "not-verified (pypdf not installed)"

    reader = PdfReader(str(PDF_PATH))
    results: dict[str, bool] = {}
    for measure in MEASURES:
        sheet = measure["page"] + PAGE_OFFSET
        text = ""
        # Look on the cited sheet and the one after: headings can sit at a break.
        for index in (sheet, sheet + 1):
            if 0 <= index < len(reader.pages):
                text += (reader.pages[index].extract_text() or "").lower()
        text = re.sub(r"\s+", " ", text)
        results[measure["id"]] = all(k.lower() in text for k in measure["confirm"])
    return results, f"verified against the PDF on {datetime.now(timezone.utc):%Y-%m-%d}"


def main() -> int:
    verified, how = verify_pages()

    measures = []
    for m in MEASURES:
        ok = verified.get(m["id"])
        measures.append({
            "id": m["id"],
            "name": m["name"],
            "type": m["type"],
            "plain_language": m["plain"],
            "ecosystem_benefit": m["ecosystem_benefit"],
            "health_cobenefits": m["health_cobenefits"],
            "effort": m["effort"],
            "source": {
                "catalogue_name": m["catalogue_name"],
                "section": m["section"],
                "page": m["page"],
                "doi": CATALOGUE["doi"],
                "licence": CATALOGUE["licence"],
                "verified": bool(ok) if ok is not None else None,
            },
            "authored_by_us": {
                "plain_language": OURS,
                "health_cobenefits": OURS,
                "effort": OURS,
            },
        })

    known = {m["id"] for m in MEASURES}
    for problem in PROBLEMS:
        missing = [m for m in problem["measures"] if m not in known]
        if missing:
            raise SystemExit(f"{problem['id']} references unknown measures: {missing}")

    doc = {
        "version": "1.0.0",
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "generated_by": "scripts/build_measures.py",
        "synthetic": False,
        "catalogue": CATALOGUE,
        "verification": how,
        "provenance_note": (
            "Measure names, sections and page numbers are from the catalogue. The "
            "mapping from observable problems to measures, the plain-language "
            "descriptions, the health co-benefit tags and the effort estimates are "
            "ours and are marked 'project judgement (StreamLens)'. The catalogue "
            "links rehabilitation to health in general terms at p.132 rather than "
            "measure by measure."
        ),
        "health_note": (
            "Co-benefit tags describe why a measure may be good for people in general "
            "terms - shade, fewer mosquito breeding sites, a place worth walking to. "
            "They are not medical claims and must never be presented as any."
        ),
        "measures": measures,
        "problems": PROBLEMS,
    }
    OUT_PATH.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8")

    confirmed = sum(1 for v in verified.values() if v)
    print(f"Wrote {len(measures)} measures and {len(PROBLEMS)} problems to {OUT_PATH}")
    print(f"  {how}")
    if verified:
        print(f"  {confirmed}/{len(verified)} page citations confirmed")
        unconfirmed = [k for k, v in verified.items() if not v]
        if unconfirmed:
            print(f"  could not confirm: {', '.join(unconfirmed)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
