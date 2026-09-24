# Evaluation — `assess_v1`

Generated 2026-09-24 06:30 UTC by `eval/run_eval.py`.

> **This run did NOT use a vision model.** Every figure below comes from
> the offline mock provider (a colour heuristic). Agreement and
> calibration numbers are meaningless here; drop rate, unknown rate and
> latency describe the harness and the validation gate, not a model.

> **No labels filled in yet.** Agreement and calibration are blank.
> Fill in `eval/labels.csv` and re-run for those.

## Setup

| | |
|---|---|
| Prompt | `assess_v1` |
| Provider | `mock` |
| Model | `heuristic-colour-v1` |
| Photos | 6 (1 could not be read) |
| Site context | Exploratório, Coimbra |
| Questions offered to the model | 22 |
| Labelled answers | 0 |
| Timeout / retries | 20s / 1 |

## Headline

| Measure | Value | What it means |
|---|---|---|
| Agreement with labels | — | 0/0 suggestions matched the labeller exactly |
| Unknown (`NS`) rate | 50% | 53/106 suggestions were "I'm not sure" |
| Dropped by validation | 0% | 0 invalid suggestions never reached a citizen |
| Coverage | 96% | share of offered questions the model answered |
| Mean confidence when right | — | |
| Mean confidence when wrong | — | a useful model is more confident when right |
| Calibration gap | — | right minus wrong; at or below zero the confidence is noise |

## Latency and cost

| Measure | Value |
|---|---|
| Mean | 2 ms |
| Median | 2 ms |
| Slowest | 3 ms |
| p95 | 3 ms |

Tokens: 0 in, 0 out (thinking tokens counted as output).

No token usage reported — cost cannot be estimated for this run.

## Per question

Sorted by drop rate, then by disagreement: the rows that need attention first.

| Question | Asked | `NS` | Dropped | Labelled | Agreement | Conf. right | Conf. wrong |
|---|---:|---:|---:|---:|---:|---:|---:|
| `bankType` — Bank type | 5 | 0 | 0 | 0 | — | — | — |
| `channelForm` — Channel form | 5 | 5 | 0 | 0 | — | — | — |
| `channelType` — Channel bed | 5 | 0 | 0 | 0 | — | — | — |
| `construction` — Channel works | 5 | 0 | 0 | 0 | — | — | — |
| `cutsL` — Vegetation management, left bank | 5 | 5 | 0 | 0 | — | — | — |
| `cutsR` — Vegetation management, right bank | 5 | 5 | 0 | 0 | — | — | — |
| `dams` — Longitudinal connectivity | 5 | 5 | 0 | 0 | — | — | — |
| `fallenBiomass` — Natural debris | 5 | 0 | 0 | 0 | — | — | — |
| `habitats` — Instream habitats | 1 | 0 | 0 | 0 | — | — | — |
| `imperviousL` — Impervious surface, left bank | 5 | 0 | 0 | 0 | — | — | — |
| `imperviousR` — Impervious surface, right bank | 5 | 0 | 0 | 0 | — | — | — |
| `invasiveL` — Invasive species, left bank | 5 | 5 | 0 | 0 | — | — | — |
| `invasiveR` — Invasive species, right bank | 5 | 5 | 0 | 0 | — | — | — |
| `pollutedPipes` — Polluted outfalls | 5 | 0 | 0 | 0 | — | — | — |
| `sewage` — Sewage discharge | 5 | 0 | 0 | 0 | — | — | — |
| `vegCoverL` — Riparian vegetation cover, left bank | 5 | 1 | 0 | 0 | — | — | — |
| `vegCoverR` — Riparian vegetation cover, right bank | 5 | 1 | 0 | 0 | — | — | — |
| `vegDominantL` — Dominant vegetation, left bank | 5 | 5 | 0 | 0 | — | — | — |
| `vegDominantR` — Dominant vegetation, right bank | 5 | 5 | 0 | 0 | — | — | — |
| `waterAspect` — Water aspect | 5 | 1 | 0 | 0 | — | — | — |
| `waterFlow` — Flow type | 5 | 5 | 0 | 0 | — | — | — |
| `withdrawal` — Water abstraction | 5 | 5 | 0 | 0 | — | — | — |

### Photos that could not be processed

- `not_a_photo.jpg`: could not read the upstream photo as an image: cannot identify image file <_io.BytesIO object at 0x0000022BFC663880>

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

