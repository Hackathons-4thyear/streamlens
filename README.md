# StreamLens

**A second pair of eyes for citizen stream assessments — the citizen always decides.**

IEEE OneAquaHealth Global Hackathon 2026.

StreamLens is a photo-first, offline-capable field companion for the
[OneAquaHealth](https://www.oneaquahealth.eu/) Citizen Science App. A vision model
looks at the citizen's upstream and downstream photos and pre-fills the app's own
assessment questions as **suggestion chips**, each with a confidence level and a
short reason in plain language. The citizen confirms or rejects every single one.

> **The AI never sets the overall rating.** It suggests answers to factual
> questions; the Good / Moderate / Poor verdict is always the citizen's.

## The loop

| Part | What it does | Tracks |
|---|---|---|
| **1. Observe** | Photo-first guided assessment, AI suggestion chips with reasons, plain-language glossary, live photo/GPS quality checks, 6 languages, offline-first PWA | 1, 3 |
| **2. Understand & Act** | Stream health card, rule-based 48-hour alert (Open-Meteo + recent reports) that shows its reasons, problems → restoration measures with health benefits | 6, 2 |
| **3. Return** | Quests aimed at real data gaps, points for good photos and agreeing answers, team leaderboard, wellbeing mirror from emotion data | 5, 4 |

Plus **FHIR R4 export** (Observation + Location) following the hl7-eu/oah
Implementation Guide.

**Status: Phase 1 — the Observe vertical slice.** Parts 2 and 3 are scaffolded, not
built. See [docs/STATUS.md](docs/STATUS.md) for exactly what works and what is stubbed.

## Quick start

Requires Node 20+, Python 3.11, and Git.

```powershell
git clone <this repo>
cd "IEEE Hackathon"

# 1. one-time setup (creates the venv, installs api + web dependencies)
npm install
npm run setup

# 2. start both apps
npm run dev
```

Other commands:

```powershell
npm test              # pytest + vitest
npm run test:api      # pytest only
npm run test:web      # vitest only
npm run build         # production build of the web app
npm run data:sites    # re-fetch data/sites.json from the ENORA API
npm run data:questions # rebuild data/questions.json
```

- Web app: <http://localhost:5173>
- API docs: <http://localhost:8000/docs>

No API key is needed to run the demo. With no `GEMINI_API_KEY` set, StreamLens uses
a deterministic **mock** vision provider and the UI shows a **"demo AI (mock)"**
badge so nobody mistakes it for a real model. To use Gemini, copy `.env.example`
to `api/.env` and set `AI_PROVIDER=gemini` plus your `GEMINI_API_KEY`.

## Ethics and data handling

- **AI suggests, humans decide.** Every record stores the citizen's answer *and*
  what the AI suggested, so disagreement is measurable, not hidden.
- **No medical claims.** StreamLens discusses ecosystem health and general One
  Health relevance. It never diagnoses.
- **Synthetic data is labelled.** Every demo record carries `"synthetic": true`.
- **Photos are stripped of EXIF** (including embedded GPS) and downscaled to
  1600 px before storage. Location is stored only in its own field, from an
  explicit user action, after an explicit consent notice.
- **Provenance is visible.** Answer codes are not presented as official unless they
  came from a public source; machine-translated strings are flagged.

## Data sources

- **Research sites** — `https://api.enora-oah.eu/api/sites/all` (public, no auth).
  106 sites across Toulouse, Ghent, Coimbra, Benevento and Oslo, fetched once into
  [`data/sites.json`](data/sites.json) and served from that local file so the app
  works offline. *Site data: OneAquaHealth / ENORA API.*
- **Question set** — the app's `api/citizens/*` endpoints require authentication,
  so [`data/questions.json`](data/questions.json) is reconstructed from the published
  OneAquaHealth assessment categories and marked `"source": "manual"`.
- **Weather** — [Open-Meteo](https://open-meteo.com/) (no key).

## Testing the vision prompt

`docs/photo-sources.md` lists 45 checked, legally usable sources of stream
photographs — the real watercourses of all five research cities, plus one
category per thing the questions ask about (weirs, outfalls, gabions, dry beds,
invasive species), plus licence-filtered search platforms.

## Repository layout

```
api/    FastAPI + Pydantic v2 + SQLModel/SQLite, provider-agnostic AI layer
web/    React + Vite + TypeScript + Tailwind + PWA + Leaflet + Dexie + i18next
data/   sites.json, questions.json
docs/   status, photo test sources, FHIR notes
```

See [CLAUDE.md](CLAUDE.md) for the full brief, architecture and working rules.

## Licence

Code: MIT. Site data belongs to the OneAquaHealth / ENORA consortium and is
redistributed here for hackathon evaluation with attribution.
