# Evaluation — `assess_v2`

Generated 2026-09-24 07:28 UTC by `eval/run_eval.py`.

> **2 photographs fell back to the mock provider and are
> EXCLUDED from every figure below.** They are mock output, not the
> model's, and scoring them would contaminate the result. Excluded: weir_02.jpg, woodydebris_01.jpg. Reason: The AI could not be reached.

## Setup

| | |
|---|---|
| Prompt | `assess_v2` |
| Provider | `gemini` |
| Model | `gemini-3.5-flash-lite` |
| Photos scored | 27 of 29 (0 unreadable, 2 fell back to the mock) |
| Site context | Exploratório, Coimbra |
| Questions offered to the model | 17 |
| Labelled answers | 55 |
| Timeout / retries | 20s / 1 |

## Headline

| Measure | Value | What it means |
|---|---|---|
| Agreement with labels | 89% | 49/55 suggestions matched the labeller exactly |
| Unknown (`NS`) rate | 4% | 3/78 suggestions were "I'm not sure" |
| Dropped by validation | 0% | 0 invalid suggestions never reached a citizen |
| Coverage | 17% | share of offered questions the model answered |
| Mean confidence when right | 0.87 | |
| Mean confidence when wrong | 0.81 | a useful model is more confident when right |
| Calibration gap | 0.06 | right minus wrong; at or below zero the confidence is noise |

## Latency and cost

| Measure | Value |
|---|---|
| Mean | 3056 ms |
| Median | 2947 ms |
| Slowest | 4579 ms |
| p95 | 4458 ms |

Tokens: 122,970 in, 6,570 out (thinking tokens counted as output).

**Approximate cost: $0.0533 for 27 photos** ($0.0020 each, so about $1.97 per 1,000).

At $0.3/M input and $2.5/M output, from `eval/pricing.json` (checked 2026-09-24). Verify before quoting.

## Per question

Sorted by drop rate, then by disagreement: the rows that need attention first.

| Question | Asked | `NS` | Dropped | Labelled | Agreement | Conf. right | Conf. wrong |
|---|---:|---:|---:|---:|---:|---:|---:|
| `habitats` — Instream habitats | 4 | 0 | 0 | 3 | 33% | 0.85 | 0.88 |
| `construction` — Channel works | 2 | 0 | 0 | 2 | 50% | 0.80 | 0.95 |
| `bankType` — Bank type | 9 | 0 | 0 | 6 | 67% | 0.84 | 0.82 |
| `channelType` — Channel bed | 9 | 3 | 0 | 4 | 75% | 0.88 | 0.50 |
| `channelForm` — Channel form | 1 | 0 | 0 | 0 | — | — | — |
| `dams` — Longitudinal connectivity | 7 | 0 | 0 | 7 | 100% | 0.90 | — |
| `fallenBiomass` — Natural debris | 2 | 0 | 0 | 1 | 100% | 0.90 | — |
| `imperviousL` — Impervious surface, left bank | 4 | 0 | 0 | 1 | 100% | 0.80 | — |
| `imperviousR` — Impervious surface, right bank | 2 | 0 | 0 | 0 | — | — | — |
| `pollutedPipes` — Polluted outfalls | 1 | 0 | 0 | 1 | 100% | 0.70 | — |
| `sewage` — Sewage discharge | 1 | 0 | 0 | 1 | 100% | 0.70 | — |
| `vegCoverL` — Riparian vegetation cover, left bank | 8 | 0 | 0 | 6 | 100% | 0.88 | — |
| `vegCoverR` — Riparian vegetation cover, right bank | 7 | 0 | 0 | 6 | 100% | 0.89 | — |
| `vegDominantL` — Dominant vegetation, left bank | 8 | 0 | 0 | 6 | 100% | 0.88 | — |
| `vegDominantR` — Dominant vegetation, right bank | 7 | 0 | 0 | 6 | 100% | 0.88 | — |
| `waterAspect` — Water aspect | 6 | 0 | 0 | 5 | 100% | 0.85 | — |

### Questions the model never answered

Either it is being appropriately cautious, or these questions cannot be
judged from a photograph and should be `ai_suggestable: false`.

- `waterFlow` — Flow type

### Every dropped suggestion

| Photo | Question | Codes | Why |
|---|---|---|---|
| weir_02.jpg | `waterFlow` | `NS` | this question is never suggested by the AI |
| weir_02.jpg | `invasiveL` | `NS` | this question is never suggested by the AI |
| weir_02.jpg | `invasiveR` | `NS` | this question is never suggested by the AI |
| weir_02.jpg | `withdrawal` | `NS` | this question is never suggested by the AI |
| weir_02.jpg | `cutsL` | `NS` | this question is never suggested by the AI |
| weir_02.jpg | `cutsR` | `NS` | this question is never suggested by the AI |
| woodydebris_01.jpg | `waterFlow` | `NS` | this question is never suggested by the AI |
| woodydebris_01.jpg | `invasiveL` | `NS` | this question is never suggested by the AI |
| woodydebris_01.jpg | `invasiveR` | `NS` | this question is never suggested by the AI |
| woodydebris_01.jpg | `withdrawal` | `NS` | this question is never suggested by the AI |
| woodydebris_01.jpg | `cutsL` | `NS` | this question is never suggested by the AI |
| woodydebris_01.jpg | `cutsR` | `NS` | this question is never suggested by the AI |

## Negative controls

12 of the 27 images do not show a watercourse at all - artwork, diagrams, plant close-ups, dry hillsides. The prompt tells the model to stay silent on those. This counts whether it did.

- **Stayed silent on 10 of 12** (83%).
- Offered suggestions anyway on 2:

| Photo | Suggestions | Highest confidence |
|---|---:|---:|
| gabion_01.jpg | 1 | 0.95 |
| gabion_02.jpg | 1 | 0.95 |

## How to read this

- **Dropped rate is the first thing to look at.** Anything above zero means
  the model is inventing codes the prompt did not offer it.
- **An unknown rate of zero is a red flag**, not a success: a model that is
  never unsure is guessing. On a mixed set, roughly a fifth to a third is
  healthy.
- **The calibration gap matters more than raw agreement.** A model that is
  70% accurate but visibly less confident when it is wrong is more useful in
  the field than one that is 80% accurate with flat confidence, because the
  citizen can tell which suggestions to check.

