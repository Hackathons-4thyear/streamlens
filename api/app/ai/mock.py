"""The mock vision provider: the default, and the one the demo runs on.

This is NOT a model. It is a small set of colour heuristics over the photo, and
it is labelled as such everywhere it surfaces - the API returns `is_mock: true`
and the web app shows a "demo AI (mock)" badge. Nobody should ever mistake its
output for a vision model's.

It exists for three reasons:

1. The demo works with no API key, no network and no cost.
2. Tests get deterministic output without mocking an SDK.
3. It exercises exactly the same validation path as a real provider, including
   the honest behaviours we want from one - answering `NS` for anything a still
   photo cannot settle (flow speed, invasive species) rather than guessing.

Identical bytes in, identical suggestions out.
"""

from __future__ import annotations

import hashlib
import io

import numpy as np
from PIL import Image

from .base import AssessContext, ImageInput, ProviderResult, RawSuggestion

# Anything a still photograph genuinely cannot settle is answered "not sure" on
# purpose - it is the behaviour we want from the real provider too.
ALWAYS_UNSURE = {
    "waterFlow": "A photo cannot show how fast the water is moving.",
    "invasiveL": "Telling an invasive plant apart needs a closer look than this.",
    "invasiveR": "Telling an invasive plant apart needs a closer look than this.",
    "withdrawal": "No pump, hose or intake is visible in the frame.",
    "vegDominantL": "The bank plants are not clear enough to say which kind dominates.",
    "vegDominantR": "The bank plants are not clear enough to say which kind dominates.",
    "cutsL": "Recent cutting is not something this view settles.",
    "cutsR": "Recent cutting is not something this view settles.",
}


class MockProvider:
    name = "mock"
    is_mock = True

    def __init__(self) -> None:
        self.model = "heuristic-colour-v1"

    # --- image statistics --------------------------------------------------

    @staticmethod
    def _stats(data: bytes) -> dict[str, float]:
        image = Image.open(io.BytesIO(data)).convert("RGB")
        image.thumbnail((64, 64))
        arr = np.asarray(image, dtype=np.float64) / 255.0
        r, g, b = arr[..., 0].mean(), arr[..., 1].mean(), arr[..., 2].mean()
        total = max(r + g + b, 1e-6)
        mx = arr.max(axis=2)
        mn = arr.min(axis=2)
        saturation = float(np.where(mx > 0, (mx - mn) / np.maximum(mx, 1e-6), 0).mean())
        return {
            "green_ratio": float(g / total),
            "saturation": saturation,
            "brightness": float(arr.mean()),
        }

    # --- provider interface ------------------------------------------------

    async def suggest(
        self, images: list[ImageInput], context: AssessContext
    ) -> ProviderResult:
        if not images:
            return ProviderResult(suggestions=[], note="No photo was supplied.")

        stats = [self._stats(img.data) for img in images]
        green = sum(s["green_ratio"] for s in stats) / len(stats)
        saturation = sum(s["saturation"] for s in stats) / len(stats)

        # A stable per-photo jitter so confidences are not all identical, but are
        # reproducible for the same input.
        digest = hashlib.sha256(b"".join(img.data for img in images)).digest()
        jitter = [(digest[i] / 255.0 - 0.5) * 0.08 for i in range(16)]
        j = iter(jitter * 4)

        def conf(base: float) -> float:
            return round(min(0.95, max(0.3, base + next(j))), 2)

        leafy = green > 0.35
        hard = saturation < 0.18

        out: list[RawSuggestion] = []

        def add(qid: str, codes: list[str], base: float, reason: str) -> None:
            out.append(RawSuggestion(qid, codes, conf(base), reason))

        # Channel and banks: grey and unsaturated reads as engineered.
        if hard:
            add("channelType", ["ART"], 0.62,
                "The bed looks grey and evenly coloured, the way concrete does.")
            add("bankType", ["ART"], 0.58,
                "The sides look like a hard grey surface rather than soil.")
        else:
            add("channelType", ["NAT"], 0.60,
                "The bed shows mixed browns and greys, like gravel or sediment.")
            add("bankType", ["NAT"], 0.57,
                "The sides look like earth with plants growing out of them.")
        add("channelForm", ["NS"], 0.40,
            "This view does not show both banks well enough to judge the shape.")

        # Water.
        add("waterAspect", ["CL"] if not hard else ["NS"], 0.52,
            "The water looks even in colour, with nothing standing out."
            if not hard else "Glare and shade make the water hard to read here.")

        # Habitat. Note that 'habitats' and 'fallenBiomass' have no NS option, so
        # being unsure means saying nothing at all rather than sending a code that
        # would only be thrown away by validation.
        if hard:
            add("habitats", ["NONE"], 0.45, "Nothing breaks the surface in this view.")
        add("fallenBiomass", ["NONE"], 0.48,
            "No wood or leaf piles stand out in the channel.")

        # Margins: greenery reads as vegetated, grey as sealed.
        for side, word in (("L", "left"), ("R", "right")):
            add(f"vegCover{side}", ["Y"] if leafy else ["NS"], 0.58,
                f"Plants cover most of the {word} bank in this view."
                if leafy else f"The {word} bank is mostly out of frame.")
            add(f"impervious{side}", ["Y"] if hard else ["N"], 0.50,
                f"Paving or hard surfacing runs close to the {word} bank."
                if hard else f"The ground beside the {word} bank looks soft and planted.")

        # Pressures that a clean-looking photo argues against, weakly.
        add("sewage", ["N"], 0.55, "No waste material or grey slime is visible.")
        add("pollutedPipes", ["N"], 0.52, "No discharging pipe is visible in the frame.")
        add("construction", ["N"], 0.60, "No machinery or fresh works are in view.")
        add("dams", ["NS"], 0.42, "This stretch is too short to tell whether anything blocks it.")

        # The honest unknowns.
        for qid, reason in ALWAYS_UNSURE.items():
            add(qid, ["NS"], 0.35, reason)

        return ProviderResult(
            suggestions=out,
            note=(
                "These came from a colour heuristic, not a vision model. Set "
                "AI_PROVIDER=gemini with a key for real suggestions."
            ),
        )
