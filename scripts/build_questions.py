"""Build data/questions.json for StreamLens.

Why a builder and not a hand-written JSON file: nine of the questions share the
same Yes / No / I'm-not-sure answer set, and every question and option carries a
provenance field. Generating the file keeps those consistent and re-runnable.

PROVENANCE
----------
The OneAquaHealth Citizen Science App's own question endpoints
(api.enora-oah.eu/api/citizens/*) require authentication and return HTTP 401 to
anonymous callers, so the question set could not be fetched directly.

Question ids and answer codes below are taken from a PUBLIC source: the draft
FHIR CodeSystems published by the StreamCheck project
(https://github.com/HyunsikParker/streamcheck/tree/main/docs/fhir --
CodeSystem-citizen-question.json, CodeSystem-citizen-answer.json), which state
that their answer codes reuse the OAH app's own codes. Those carry
source = "streamcheck-fhir-docs".

Everything written by us -- the plain-language explanations, the photo hints,
the section grouping, the glossary and all translations -- carries
source = "manual". Nothing here is presented as an official OneAquaHealth
artefact.

Usage:  python scripts/build_questions.py
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

OUT_PATH = Path(__file__).resolve().parents[1] / "data" / "questions.json"

PUBLIC = "streamcheck-fhir-docs"
MANUAL = "manual"

LANGS = ["en", "pt", "it", "fr", "nl", "no"]

# Languages whose strings, where present, are our own translations rather than
# text supplied by the OneAquaHealth consortium.
MACHINE_TRANSLATED = ["pt", "it", "fr", "nl", "no"]

NOT_SURE_EXPLAIN = (
    "Choose this whenever the photo does not show it clearly. "
    "'Not sure' is a good answer - a guess is not."
)


def t(en: str, pt: str | None = None) -> dict:
    """A translatable string. English is authored; pt is our own translation."""
    out = {"en": en}
    if pt:
        out["pt"] = pt
    return out


def opt(code: str, en: str, pt: str | None, explain_en: str, *, source: str = PUBLIC) -> dict:
    """One answer option. The code is public; the explanation is ours."""
    return {
        "code": code,
        "label": t(en, pt),
        "explain": t(explain_en),
        "source": source,
        "explain_source": MANUAL,
    }


def yes_no_unsure(yes_explain: str, no_explain: str) -> list[dict]:
    return [
        opt("Y", "Yes", "Sim", yes_explain),
        opt("N", "No", "Não", no_explain),
        opt("NS", "I'm not sure", "Não tenho a certeza", NOT_SURE_EXPLAIN),
    ]


def q(
    qid: str,
    section: str,
    label_en: str,
    label_pt: str,
    explain_en: str,
    explain_pt: str,
    options: list[dict],
    *,
    qtype: str = "single",
    ai_suggestable: bool = True,
    photo_hint_en: str = "",
    terms: list[str] | None = None,
    source: str = PUBLIC,
) -> dict:
    return {
        "id": qid,
        "section": section,
        "type": qtype,
        "ai_suggestable": ai_suggestable,
        "source": source,
        "label": t(label_en, label_pt),
        "explain": t(explain_en, explain_pt),
        "photo_hint": t(photo_hint_en) if photo_hint_en else {},
        "terms": terms or [],
        "options": options,
    }


# --------------------------------------------------------------------------
# Questions
# --------------------------------------------------------------------------

QUESTIONS: list[dict] = [
    # --- Channel, bed and banks -------------------------------------------
    q(
        "channelForm", "channel",
        "Channel form", "Forma do canal",
        "The shape of the ditch or valley the water runs through, seen from the side. "
        "A flat wide channel spreads water out; a steep V holds it in a narrow cut.",
        "A forma do canal ou vale por onde a água corre, vista de lado.",
        [
            opt("FLAT", "Flat and wide", "Plano e largo",
                "The ground on both sides is roughly level with the water and the stream is broad."),
            opt("U", "U shape", "Forma em U",
                "Sides rise on both banks but the bottom is flat - like a bathtub."),
            opt("V", "V shape, steep sides", "Forma em V, margens íngremes",
                "The banks slope steeply down to a narrow bottom."),
            opt("NS", "I'm not sure", "Não tenho a certeza",
                "Choose this if the photo does not show the banks clearly."),
        ],
        photo_hint_en="Best judged from a photo taken across the stream, showing both banks.",
        terms=["channel"],
    ),
    q(
        "channelType", "channel",
        "Channel bed", "Leito do canal",
        "What the bottom of the stream is made of. A natural bed is gravel, sand, stones "
        "or mud that the stream itself shaped. An artificial bed is concrete or another "
        "hard surface people laid down.",
        "De que é feito o fundo do ribeiro: natural (areia, pedras, lodo) ou artificial (betão).",
        [
            opt("NAT", "Natural", "Natural",
                "Gravel, sand, stones, silt or mud - material the stream itself moves and sorts."),
            opt("ART", "Artificial", "Artificial",
                "Concrete, brick or another hard engineered surface."),
            opt("NS", "I'm not sure", "Não tenho a certeza",
                "Choose this if the water is too deep, too cloudy or too shaded to see the bottom."),
        ],
        photo_hint_en="Look at the bottom where the water is shallow or clear.",
        terms=["bed"],
    ),
    q(
        "bankType", "channel",
        "Bank type", "Tipo de margem",
        "What the sides of the channel are made of. Natural banks are soil and plant roots; "
        "hardened banks are concrete or stacked stone.",
        "De que são feitas as margens: terra natural, betão ou pedra assente.",
        [
            opt("NAT", "Natural", "Natural",
                "Earth, sediment and plant roots holding the bank together."),
            opt("ART", "Concrete", "Betão",
                "A poured or rendered concrete wall."),
            opt("LAS", "Laid stones", "Pedra assente",
                "Stones or blocks placed by people - rip-rap, gabions or a stone wall."),
            opt("NS", "I'm not sure", "Não tenho a certeza",
                "Choose this if vegetation hides the bank surface."),
        ],
        photo_hint_en="Look at the strip between the water's edge and the top of the bank.",
        terms=["bank"],
    ),

    # --- Habitats and natural debris --------------------------------------
    q(
        "habitats", "habitat",
        "Instream habitats", "Habitats dentro de água",
        "Features inside the water that give small animals places to live, feed and hide. "
        "More variety usually means more life.",
        "Estruturas dentro de água que dão abrigo e alimento a pequenos animais.",
        [
            opt("SB", "Sand banks", "Bancos de areia",
                "A build-up of sand along the edge or inside the channel."),
            opt("SI", "Sand islands", "Ilhas de areia",
                "A patch of sand or sediment standing above the water with flow on both sides."),
            opt("SD", "Stone deposits", "Depósitos de pedras",
                "Loose stones and gravel gathered on the bed."),
            opt("RF", "Riffles, rapids or small falls", "Rápidos ou pequenas quedas",
                "Shallow fast stretches where water breaks over stones and looks broken and "
                "white. These mix air into the water."),
            opt("AV", "Plants growing in the water", "Plantas dentro de água",
                "Rooted or floating plants living in the channel itself."),
            opt("NONE", "None of these", "Nenhum destes",
                "The channel is uniform, with none of these features visible."),
        ],
        qtype="multi",
        photo_hint_en="Scan the whole water surface, edge to edge.",
        terms=["riffle", "instream habitat"],
    ),
    q(
        "fallenBiomass", "habitat",
        "Natural debris", "Detritos naturais",
        "Wood and leaves that fell into the stream naturally. This is not litter - it is "
        "food and shelter for stream life, and it slows the water down.",
        "Madeira e folhas caídas naturalmente no ribeiro. Não é lixo: é alimento e abrigo.",
        [
            opt("FT", "Fallen trees", "Árvores caídas",
                "A whole trunk or large tree lying in or across the channel."),
            opt("FB", "Fallen branches", "Ramos caídos",
                "Branches and smaller woody pieces in the water."),
            opt("FL", "Piles of leaves", "Acumulações de folhas",
                "Collected leaf litter caught in the channel."),
            opt("NONE", "None", "Nenhum",
                "No natural wood or leaf material visible in the water."),
        ],
        qtype="multi",
        photo_hint_en="Look for wood caught against stones, bends or bridge supports.",
        terms=["natural debris"],
    ),

    # --- Flow and water appearance ----------------------------------------
    q(
        "waterFlow", "water",
        "Flow type", "Tipo de escoamento",
        "How fast the water is moving. Standing or dry channels behave very differently "
        "from flowing ones - they warm up faster and hold less oxygen.",
        "A velocidade a que a água se move.",
        [
            opt("FAS", "Fast, with waves", "Rápido, com ondulação",
                "The surface is broken, rippled or white where it passes obstacles."),
            opt("NOR", "Slow", "Lento",
                "Water is clearly moving but the surface is smooth."),
            opt("STA", "Standing", "Parada",
                "Water is present but not moving at all - a pool or a stagnant reach."),
            opt("DRY", "Dry", "Seco",
                "No water in the channel at the time of the visit."),
            opt("NS", "I'm not sure", "Não tenho a certeza",
                "Choose this if a still photo cannot show movement."),
        ],
        photo_hint_en="Movement is hard to see in a still photo - answer 'not sure' if unclear.",
        terms=["flow"],
    ),
    q(
        "waterAspect", "water",
        "Water aspect", "Aspeto da água",
        "How the water looks. Colour, cloudiness and foam can point to pollution, erosion "
        "or perfectly natural conditions after rain.",
        "O aspeto da água: cor, turvação e espuma.",
        [
            opt("CL", "Clear", "Limpa",
                "You can see through the water to the bed."),
            opt("MU", "Muddy or cloudy", "Turva ou lamacenta",
                "Brown or milky water carrying suspended sediment. Common and often natural "
                "after heavy rain."),
            opt("FO", "Foam on the surface", "Espuma à superfície",
                "White or off-white froth. Natural foam is tan and breaks up easily; "
                "persistent bright white foam can point to detergents."),
            opt("CO", "An unusual colour", "Cor invulgar",
                "Green, orange, grey, black or any colour that stands out."),
            opt("NS", "I'm not sure", "Não tenho a certeza",
                "Choose this if glare, shade or reflections hide the water."),
        ],
        qtype="multi",
        photo_hint_en="Photograph the water at an angle to cut reflections off the surface.",
        terms=["turbidity"],
    ),

    # --- Pressures ---------------------------------------------------------
    q(
        "withdrawal", "pressures",
        "Water abstraction", "Captação de água",
        "Signs that water is being taken out of the stream - a pump, a hose, a pipe running "
        "from the channel, or a small diversion channel.",
        "Sinais de que está a ser retirada água do ribeiro (bombas, mangueiras, desvios).",
        yes_no_unsure(
            "A pump, hose, intake or diversion taking water out is visible.",
            "No abstraction structure is visible.",
        ),
        terms=["abstraction"],
    ),
    q(
        "dams", "pressures",
        "Longitudinal connectivity", "Conectividade longitudinal",
        "Whether anything blocks the way along the stream. Weirs, dams, culverts and drops "
        "stop fish and other animals moving up and down.",
        "Se existe algo que bloqueie o percurso ao longo do ribeiro (açudes, barragens, quedas).",
        yes_no_unsure(
            "A weir, dam, sluice, culvert or step blocks movement along the channel.",
            "The water runs uninterrupted through the whole stretch you can see.",
        ),
        terms=["longitudinal connectivity", "weir"],
    ),
    q(
        "pollutedPipes", "pressures",
        "Polluted outfalls", "Descargas poluídas",
        "A pipe discharging into the stream where the water coming out looks or smells "
        "wrong - discoloured, foamy, greasy, or stained around the mouth.",
        "Tubos que descarregam no ribeiro com aspeto ou cheiro suspeito.",
        yes_no_unsure(
            "A pipe is discharging something that looks polluted, or the outfall is stained.",
            "No pipe is discharging, or a pipe is present but the water looks clean.",
        ),
        terms=["outfall"],
    ),
    q(
        "sewage", "pressures",
        "Sewage discharge", "Descarga de esgoto",
        "Signs of waste water: toilet paper, sanitary items, grey scum, sewage fungus "
        "(a white or grey slimy growth), or a strong smell.",
        "Sinais de águas residuais: papel, espuma acinzentada, cheiro forte.",
        yes_no_unsure(
            "Sewage-related material or staining is visible.",
            "No sign of waste water.",
        ),
        terms=["sewage fungus"],
    ),
    q(
        "construction", "pressures",
        "Channel works", "Obras no canal",
        "Building or engineering work in or right beside the channel - machinery, fresh "
        "concrete, dredging, bare disturbed earth or site fencing.",
        "Obras dentro ou junto ao canal: máquinas, betão fresco, dragagens.",
        yes_no_unsure(
            "Active or very recent works are visible in or beside the channel.",
            "No works visible.",
        ),
    ),
]

# --------------------------------------------------------------------------
# Margins: the same five questions asked of each bank
# --------------------------------------------------------------------------

MARGIN_TEMPLATE = [
    (
        "impervious", "Impervious surface", "Superfície impermeável",
        "Sealed ground next to the stream - tarmac, concrete, paving or buildings - that "
        "rain cannot soak into. It sends rain straight into the stream, carrying whatever "
        "was lying on the surface.",
        "Solo selado junto ao ribeiro (alcatrão, betão, pavimento) onde a chuva não se infiltra.",
        lambda: yes_no_unsure(
            "Paving, tarmac, concrete or buildings run up close to the bank.",
            "The ground beside the stream is soil, grass or another surface rain can soak into.",
        ),
        ["impervious surface", "riparian zone"],
    ),
    (
        "vegCover", "Riparian vegetation cover", "Cobertura vegetal ripária",
        "Whether plants cover the strip of land along the bank. That strip shades the water, "
        "holds the bank together and filters what runs off the land.",
        "Se existem plantas na faixa de terreno ao longo da margem.",
        lambda: yes_no_unsure(
            "Plants cover most of the bank strip.",
            "The bank strip is mostly bare, paved, or mown to nothing.",
        ),
        ["riparian zone"],
    ),
    (
        "vegDominant", "Dominant vegetation", "Vegetação dominante",
        "Which kind of plant takes up the most space along the bank. Trees shade and cool "
        "the water; grass alone gives much less shelter.",
        "Que tipo de planta ocupa mais espaço ao longo da margem.",
        lambda: [
            opt("H", "Grass and herbs", "Ervas e herbáceas",
                "Low, soft, non-woody plants."),
            opt("B", "Shrubs", "Arbustos",
                "Woody plants below roughly head height."),
            opt("T", "Trees", "Árvores",
                "Woody plants with a trunk, taller than a person."),
            opt("NS", "I'm not sure", "Não tenho a certeza",
                "Choose this if no plant type clearly dominates, or the bank is out of frame."),
        ],
        ["riparian zone"],
    ),
    (
        "invasive", "Invasive species", "Espécies invasoras",
        "Plants brought from elsewhere that spread fast and crowd out local ones - for "
        "example giant reed, Japanese knotweed, acacia or pampas grass. Only answer yes if "
        "you actually recognise one.",
        "Plantas exóticas que se espalham e substituem as nativas (cana, acácia, erva-das-pampas).",
        lambda: yes_no_unsure(
            "You recognise an invasive species on this bank.",
            "You looked and recognised none.",
        ),
        ["invasive species"],
    ),
    (
        "cuts", "Vegetation management", "Gestão da vegetação",
        "Signs that plants have been cut, mown or cleared recently - stumps, cut stems, "
        "mown strips or piles of cuttings.",
        "Sinais de corte recente da vegetação: cepos, faixas cortadas, restos amontoados.",
        lambda: yes_no_unsure(
            "Recent cutting, mowing or clearing is visible.",
            "The vegetation looks unmanaged.",
        ),
        [],
    ),
]

BANKS = [
    ("L", "margin_left", "left bank", "margem esquerda"),
    ("R", "margin_right", "right bank", "margem direita"),
]

for suffix, section, bank_en, bank_pt in BANKS:
    for base, label_en, label_pt, explain_en, explain_pt, make_opts, terms in MARGIN_TEMPLATE:
        QUESTIONS.append(
            q(
                f"{base}{suffix}", section,
                f"{label_en}, {bank_en}", f"{label_pt}, {bank_pt}",
                explain_en, explain_pt,
                make_opts(),
                photo_hint_en=(
                    "Left and right are defined looking DOWNSTREAM - the way the water is going."
                ),
                terms=terms,
            )
        )

# --------------------------------------------------------------------------
# The overall verdict: the citizen's call, never the AI's
# --------------------------------------------------------------------------

QUESTIONS.append(
    q(
        "overall", "verdict",
        "Overall stream assessment", "Avaliação global do ribeiro",
        "Your own verdict on this stretch of stream, taking everything you saw into account. "
        "This one is yours alone - StreamLens will never suggest it.",
        "A sua avaliação global deste troço. Esta resposta é apenas sua.",
        [
            opt("GOOD", "Good", "Bom",
                "Looks healthy: natural bed and banks, varied habitat, clean water, living margins."),
            opt("MODERATE", "Moderate", "Moderado",
                "Some clear problems, but the stream still works as a habitat."),
            opt("POOR", "Poor", "Mau",
                "Heavily damaged: hard engineering, pollution signs, little or no habitat."),
        ],
        ai_suggestable=False,
    )
)

# --------------------------------------------------------------------------
# Glossary: every ecology term used above, in plain language
# --------------------------------------------------------------------------

GLOSSARY = {
    "channel": t(
        "The dip or cut in the ground that the stream water runs along.",
        "A depressão no terreno por onde corre a água."),
    "bed": t(
        "The bottom of the stream, under the water.",
        "O fundo do ribeiro, debaixo de água."),
    "bank": t(
        "The sloping side of the channel, between the water and the land above.",
        "O lado inclinado do canal, entre a agua e o terreno."),
    "riffle": t(
        "A shallow, fast stretch where water tumbles over stones and looks broken and "
        "white. Riffles mix air into the water, which stream animals need.",
        "Troço pouco profundo e rápido, onde a água salta sobre pedras e se areja."),
    "instream habitat": t(
        "Any feature inside the water - stones, plants, sand banks - that small animals "
        "can live in, feed on or hide behind.",
        "Qualquer estrutura dentro de água que sirva de abrigo ou alimento."),
    "natural debris": t(
        "Wood and leaves that fell in by themselves. Unlike litter, this belongs in a "
        "stream and feeds it.",
        "Madeira e folhas caídas naturalmente. Ao contrário do lixo, fazem parte do ribeiro."),
    "flow": t(
        "How fast, and whether, the water is moving.",
        "A velocidade a que a água se move."),
    "turbidity": t(
        "How cloudy the water is, from particles floating in it.",
        "O grau de turvação da água."),
    "abstraction": t(
        "Taking water out of the stream, for example by pumping it.",
        "Retirar água do ribeiro, por exemplo com bombas."),
    "longitudinal connectivity": t(
        "Whether animals can travel freely up and down the stream without hitting a "
        "barrier such as a weir.",
        "Se os animais se podem mover livremente ao longo do ribeiro."),
    "weir": t(
        "A low wall built across a stream that water flows over. It raises the water "
        "upstream and can stop fish moving past.",
        "Pequeno muro atravessado no ribeiro, por cima do qual a agua passa."),
    "outfall": t(
        "The point where a pipe or drain empties into the stream.",
        "O ponto onde um tubo ou coletor descarrega no ribeiro."),
    "sewage fungus": t(
        "A white or grey slimy growth on stones and plants. It is bacteria, not fungus, "
        "and it grows where waste water enters.",
        "Crescimento viscoso branco ou cinzento, típico de entradas de águas residuais."),
    "impervious surface": t(
        "Ground rain cannot soak into - tarmac, concrete, paving, roofs. Rain runs "
        "straight off it into the stream.",
        "Solo onde a chuva não se infiltra: alcatrão, betão, telhados."),
    "riparian zone": t(
        "The strip of land right beside a stream, and the plants growing on it. It shades "
        "the water, holds the bank and filters runoff.",
        "A faixa de terreno junto ao ribeiro e as plantas que aí crescem."),
    "invasive species": t(
        "A plant or animal from another region that spreads quickly and pushes out the "
        "species that belong there.",
        "Espécie de outra região que se espalha e substitui as nativas."),
}

SECTIONS = [
    {"id": "channel", "order": 1,
     "label": t("Channel, bed and banks", "Canal, leito e margens")},
    {"id": "habitat", "order": 2,
     "label": t("Habitats and natural debris", "Habitats e detritos naturais")},
    {"id": "water", "order": 3,
     "label": t("Flow and water appearance", "Escoamento e aspeto da água")},
    {"id": "pressures", "order": 4,
     "label": t("Pressures on the stream", "Pressões sobre o ribeiro")},
    {"id": "margin_left", "order": 5,
     "label": t("Left margin (looking downstream)", "Margem esquerda (olhando para jusante)")},
    {"id": "margin_right", "order": 6,
     "label": t("Right margin (looking downstream)", "Margem direita (olhando para jusante)")},
    {"id": "verdict", "order": 7,
     "label": t("Your overall assessment", "A sua avaliação global")},
]



# --------------------------------------------------------------------------
# Questions a single still photograph cannot settle
# --------------------------------------------------------------------------
#
# These stay in the assessment - the citizen still answers them - but the AI is
# never asked, because a guess carrying a confidence number is worse than
# silence. Added in the assess_v2 round; see eval/assess_v2-proposal.md and the
# measured baseline in eval/reports/ for the evidence behind each one.
NOT_PHOTO_ANSWERABLE = {
    # waterFlow was in this list in the original proposal. The measured baseline
    # refuted that: the model answered it on 14 of 29 photographs and agreed with
    # the labeller on 7 of 7 checked, at 0.89 confidence. The distinctions that
    # matter in practice - DRY and FAS - are plainly visible in a still frame.
    # Removing it would have deleted the single most-used, best-agreeing question.
    "invasiveL": "Species identification from an uncontrolled wide shot.",
    "invasiveR": "Species identification from an uncontrolled wide shot.",
    "cutsL": "'Recent' is a time judgement; a photo shows cut stems, not when.",
    "cutsR": "'Recent' is a time judgement; a photo shows cut stems, not when.",
    "withdrawal": "Absence of evidence: a pump out of frame is invisible.",
}

def main() -> int:
    for order, question in enumerate(QUESTIONS, start=1):
        question["order"] = order
        reason = NOT_PHOTO_ANSWERABLE.get(question["id"])
        if reason:
            question["ai_suggestable"] = False
            question["not_suggestable_reason"] = reason

    doc = {
        "version": "1.0.0",
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "generated_by": "scripts/build_questions.py",
        "synthetic": False,
        "languages": LANGS,
        "machine_translated": MACHINE_TRANSLATED,
        "translation_note": (
            "English is authored. Every non-English string in this file is our own "
            "translation, not text supplied by the OneAquaHealth consortium; treat it as "
            "machine translated and have a native speaker review it before field use. "
            "Languages listed in 'languages' but missing from a given string fall back to "
            "English in the app."
        ),
        "provenance": {
            "streamcheck-fhir-docs": {
                "what": "Question ids and answer codes only.",
                "url": "https://github.com/HyunsikParker/streamcheck/tree/main/docs/fhir",
                "files": [
                    "CodeSystem-citizen-question.json",
                    "CodeSystem-citizen-answer.json",
                ],
                "note": (
                    "A public draft CodeSystem which states that its answer codes reuse the "
                    "OneAquaHealth app's own codes (api.enora-oah.eu/api/citizens/*). Used as "
                    "a public secondary source because the app's own endpoint requires "
                    "authentication and returns 401. This is NOT an official OneAquaHealth "
                    "artefact and is not presented as one."
                ),
            },
            "manual": {
                "what": (
                    "Plain-language explanations, photo hints, section grouping, glossary "
                    "and all translations. Written by the StreamLens team."
                ),
            },
        },
        "unknown_code": "NS",
        "unknown_note": (
            "NS ('I'm not sure') is the unknown answer. The AI is instructed to return NS "
            "rather than guess, and NS is always an acceptable citizen answer."
        ),
        "ai_policy": (
            "Questions with ai_suggestable=false are never suggested by the AI. The overall "
            "Good/Moderate/Poor rating is always the citizen's own decision. Questions that "
            "a single still photograph cannot settle are also marked false and carry a "
            "not_suggestable_reason, because a guess with a confidence number attached is "
            "worse than silence. The citizen still answers every question."
        ),
        "sections": SECTIONS,
        "glossary": GLOSSARY,
        "questions": QUESTIONS,
    }

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    suggestable = sum(1 for x in QUESTIONS if x["ai_suggestable"])
    print(f"Wrote {len(QUESTIONS)} questions ({suggestable} AI-suggestable) to {OUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
