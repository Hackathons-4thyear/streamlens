# Evaluation — `assess_v1`

Generated 2026-09-24 07:28 UTC by `eval/run_eval.py`.

## Setup

| | |
|---|---|
| Prompt | `assess_v1` |
| Provider | `gemini` |
| Model | `gemini-3.5-flash-lite` |
| Photos scored | 29 of 29 (0 unreadable, 0 fell back to the mock) |
| Site context | Exploratório, Coimbra |
| Questions offered to the model | 17 |
| Labelled answers | 57 |
| Timeout / retries | 20s / 1 |

## Headline

| Measure | Value | What it means |
|---|---|---|
| Agreement with labels | 89% | 51/57 suggestions matched the labeller exactly |
| Unknown (`NS`) rate | 0% | 0/91 suggestions were "I'm not sure" |
| Dropped by validation | 0% | 0 invalid suggestions never reached a citizen |
| Coverage | 18% | share of offered questions the model answered |
| Mean confidence when right | 0.87 | |
| Mean confidence when wrong | 0.84 | a useful model is more confident when right |
| Calibration gap | 0.03 | right minus wrong; at or below zero the confidence is noise |

## Latency and cost

| Measure | Value |
|---|---|
| Mean | 3838 ms |
| Median | 3695 ms |
| Slowest | 5720 ms |
| p95 | 5650 ms |

Tokens: 139,839 in, 6,274 out (thinking tokens counted as output).

**Approximate cost: $0.0576 for 29 photos** ($0.0020 each, so about $1.99 per 1,000).

At $0.3/M input and $2.5/M output, from `eval/pricing.json` (checked 2026-09-24). Verify before quoting.

## Per question

Sorted by drop rate, then by disagreement: the rows that need attention first.

| Question | Asked | `NS` | Dropped | Labelled | Agreement | Conf. right | Conf. wrong |
|---|---:|---:|---:|---:|---:|---:|---:|
| `bankType` — Bank type | 8 | 0 | 0 | 4 | 50% | 0.88 | 0.85 |
| `habitats` — Instream habitats | 4 | 0 | 0 | 2 | 50% | 0.75 | 0.85 |
| `waterAspect` — Water aspect | 6 | 0 | 0 | 4 | 50% | 0.88 | 0.80 |
| `construction` — Channel works | 3 | 0 | 0 | 3 | 67% | 0.88 | 0.90 |
| `channelForm` — Channel form | 1 | 0 | 0 | 0 | — | — | — |
| `channelType` — Channel bed | 7 | 0 | 0 | 4 | 100% | 0.88 | — |
| `cutsL` — Vegetation management, left bank | 1 | 0 | 0 | 0 | — | — | — |
| `cutsR` — Vegetation management, right bank | 1 | 0 | 0 | 0 | — | — | — |
| `dams` — Longitudinal connectivity | 7 | 0 | 0 | 7 | 100% | 0.91 | — |
| `fallenBiomass` — Natural debris | 5 | 0 | 0 | 2 | 100% | 0.88 | — |
| `imperviousL` — Impervious surface, left bank | 2 | 0 | 0 | 1 | 100% | 0.80 | — |
| `imperviousR` — Impervious surface, right bank | 2 | 0 | 0 | 1 | 100% | 0.80 | — |
| `invasiveL` — Invasive species, left bank | 2 | 0 | 0 | 0 | — | — | — |
| `invasiveR` — Invasive species, right bank | 1 | 0 | 0 | 0 | — | — | — |
| `pollutedPipes` — Polluted outfalls | 1 | 0 | 0 | 1 | 100% | 0.75 | — |
| `sewage` — Sewage discharge | 1 | 0 | 0 | 1 | 100% | 0.80 | — |
| `vegCoverL` — Riparian vegetation cover, left bank | 7 | 0 | 0 | 5 | 100% | 0.86 | — |
| `vegCoverR` — Riparian vegetation cover, right bank | 7 | 0 | 0 | 5 | 100% | 0.86 | — |
| `vegDominantL` — Dominant vegetation, left bank | 5 | 0 | 0 | 5 | 100% | 0.86 | — |
| `vegDominantR` — Dominant vegetation, right bank | 5 | 0 | 0 | 5 | 100% | 0.86 | — |
| `waterFlow` — Flow type | 14 | 0 | 0 | 7 | 100% | 0.89 | — |
| `withdrawal` — Water abstraction | 1 | 0 | 0 | 0 | — | — | — |

## Negative controls

13 of the 29 images do not show a watercourse at all - artwork, diagrams, plant close-ups, dry hillsides. The prompt tells the model to stay silent on those. This counts whether it did.

- **Stayed silent on 9 of 13** (69%).
- Offered suggestions anyway on 4:

| Photo | Suggestions | Highest confidence |
|---|---:|---:|
| pollution_02.jpg | 2 | 0.80 |
| gabion_02.jpg | 1 | 0.95 |
| giantreed_02.jpg | 1 | 0.85 |
| woodydebris_01.jpg | 1 | 0.95 |

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

