# StreamLens — status after Phase 1

Written for: the judges and anyone picking this repository up mid-build.

Last updated: 23 September 2026.

Phase 1 delivered the **Observe** vertical slice end to end. Phases 2 and 3 are
designed and scaffolded but not built. This document says exactly which is which,
because a demo that hides its seams wastes a reviewer's time.

---

## What works

### The loop, end to end
Pick a site → take upstream and downstream photos → get AI suggestion chips →
confirm, change or reject each one → give your own overall rating and emotions →
consent → send. Verified against the running stack, not only in tests: a
submission stored with two photos, three answers and a measured AI agreement
rate of 0.5 (one suggestion kept, one overridden).

### AI suggests, humans decide — enforced in three places
- **The prompt** (`api/app/ai/prompts/assess_v1.md`, loaded from disk at call
  time) tells the model the `overall` question does not exist for it.
- **The API** drops any suggestion for a question marked `ai_suggestable: false`,
  even at confidence 1.0. There is a test that tries exactly that and asserts it
  is refused.
- **The web app** starts every chip as `pending`, holding no answer. A chip the
  citizen never touched is not submitted. Silence is not consent.

Each stored answer keeps the citizen's choice *and* the AI's suggestion, so
disagreement is measurable rather than invisible.

### Answer validation
Every code a provider returns is checked against `data/questions.json` before a
citizen can see it. Unknown questions, invented codes, duplicates, and multiple
codes on a single-answer question are all discarded into a `dropped` list that
the UI surfaces. A failing prompt shows up as visible drops, not silent nonsense.

### The mock provider, honestly labelled
With no `GEMINI_API_KEY`, StreamLens runs a deterministic colour heuristic. The
API returns `is_mock: true`, and the UI shows a **"demo AI (mock)"** badge plus a
full explanatory notice. The demo works with no key, no network and no cost, and
never pretends to be a vision model.

### Photo handling
EXIF orientation is applied, then *all* metadata — including any GPS the camera
embedded — is destroyed by rebuilding the image from raw pixels. Images are
downscaled to 1600 px. Blur is measured as the variance of the Laplacian and
brightness as mean luma; blurry, dark and overexposed photos produce warnings,
and bad photo quality flags every suggestion for extra review.

### Offline
The site list and question set are cached in IndexedDB, so a cold start with no
signal works. Submissions queue with their photos and flush on reconnect. A
network failure keeps an item queued; a 4xx marks it permanently failed instead
of retrying a bad payload forever. Photos are stored as `ArrayBuffer`, not
`Blob`, because Safari has shipped IndexedDB versions that lose Blobs.

### Data provenance
- **106 real research sites** fetched once from the public ENORA endpoint into
  `data/sites.json` and served locally. Attributed in the file, the API response
  and the UI.
- **23 questions** in `data/questions.json`. The app's own question endpoint
  requires authentication, so ids and answer codes come from a public draft FHIR
  CodeSystem, marked `source: "streamcheck-fhir-docs"` per question and option.
  Our explanations, glossary and translations are marked `source: "manual"`.
  Nothing is presented as an official OneAquaHealth artefact.
- Non-English strings are flagged `machine_translated`, and the UI says so.

### Accessibility
44 px minimum tap targets, visible focus rings, WCAG AA contrast pairings
documented in `web/src/index.css`, labelled controls, and a glossary built as a
tappable popover rather than a hover tooltip — hover does not exist on a phone.

### Tests
- **68 pytest tests**, none touching the network.
- **22 vitest tests** covering the answer state machine and the offline outbox.
- TypeScript compiles clean under `strict`.

---

## What is stubbed or missing

| Area | State | Why |
|---|---|---|
| **Gemini provider** | Written, never executed | No API key yet. The code path, structured-output schema and prompt loading are in place; it has not been run against the real service, so treat it as unverified. |
| **Question translations** | English and Portuguese complete; it, fr, nl, no fall back to English | Priority was the working vertical slice. Interface chrome *is* translated into all six. |
| **All translations** | Ours, not the consortium's | Flagged `machine_translated` in the data and warned about in the UI. A native speaker should review before field use. |
| **Photo storage** | Files on local disk | Fine for a demo; a real deployment needs object storage and a retention policy. |
| **Authentication** | None | Anyone who can reach the API can post an observation. Acceptable for a hackathon demo, not for production. |
| **`GET /observations`** | Unpaginated, capped at 200 | Demo convenience endpoint, not a real query API. |
| **PWA install** | Manifest and service worker build correctly | Not tested on a physical phone. |
| **"Answer contradicts the photo" check** | Not built | Only blur, brightness and GPS distance checks exist. Cross-answer consistency is Phase 2. |
| **Phase 2 and 3** | Not started | See below. |

---

## Suggested next steps

### Phase 2 — Understand & Act

1. **Stream health card.** A read model over stored observations for one site:
   latest rating, trend, which pressures were reported and how often, when it was
   last visited. Needs an aggregation endpoint; the data is already shaped for it
   since answers are stored per question with codes.
2. **48-hour alert.** A rules engine, not a model, so every alert can show its
   reasons. Inputs: Open-Meteo rain and temperature forecast for the site
   coordinates, plus recent `sewage`, `pollutedPipes` and `waterFlow: STA`
   reports. Output: a level plus the list of rules that fired, each with the
   number that triggered it. Rules belong in a JSON file, not in Python, so a
   scientist can read and change them.
   **Keep the no-medical-claims rule here.** An alert says "sewage was reported
   twice this week and 30 mm of rain is forecast", never "this water is unsafe".
3. **Restoration measures table.** Map observed problems to measures from the
   OneAquaHealth catalogue, in `data/measures.json` with the same per-entry
   provenance discipline as `questions.json`. Each row: the problem, the measure,
   the expected ecological effect, and the claimed health benefit *with its
   source*. Where the catalogue is not publicly available, mark entries `manual`
   and say so.

### Phase 3 — Return

4. **Quests from real data gaps.** Compute them: sites with no visit in N days,
   sites never seen after rain (join the visit dates against Open-Meteo history),
   seasons missing for a site. A quest that points at a genuine gap is worth ten
   that gamify busywork.
5. **Points and leaderboard.** Award for photo quality (the blur and brightness
   scores already exist) and for agreement with other visitors to the same site
   within a window. Resist rewarding volume alone — it pays people to submit
   rubbish. Team-level board only; an individual board on a scientific dataset
   creates an incentive to fabricate.
6. **Wellbeing mirror.** Aggregate the emotion sliders by site and season. Report
   only in groups, never per person, and only above a minimum count so a single
   visitor cannot be identified. Present it as *what people felt*, never as a
   health measure.
7. **FHIR R4 export.** `Observation` + `Location` per the hl7-eu/oah IG. The
   citizen answers do not have official FHIR codes yet, so define local
   CodeSystems, mark them `experimental`, and carry the same provenance fields
   already in `questions.json`. Validate the output with the HL7 validator and
   commit the validation report — judges can check it.

### Worth doing before any of the above

8. **Run the Gemini provider against real photos** using `docs/photo-sources.md`,
   and iterate on the prompt. Everything else in Phase 1 is verified; this is the
   one part that is not.
9. **Get a native speaker** to review the Portuguese, and translate the question
   set into the remaining four languages.
