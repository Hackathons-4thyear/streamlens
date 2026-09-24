# `data/`

Seed data served by the API at runtime. Nothing here is fetched live: the app
has to work in a field with no signal.

| File | What it is | Source |
|---|---|---|
| `sites.json` | 106 OneAquaHealth research sites | `api.enora-oah.eu/api/sites/all` (public, no auth), fetched once by `scripts/fetch_sites.py`. *Site data: OneAquaHealth / ENORA API.* |
| `questions.json` | The assessment question set, 23 questions | Ids and answer codes from a public draft FHIR CodeSystem; our explanations, glossary and translations marked `source: "manual"`. Built by `scripts/build_questions.py`. |
| `measures.json` | Restoration measures mapped to observable problems | The OneAquaHealth **Catalogue of measures** (below), with page references. Built by `scripts/build_measures.py`. |
| `alert_rules.json` | The 48-hour alert rules | Thresholds cited per rule; anything uncited says `project judgement`. |

## The catalogue of measures

`measures.json` cites **D2.4 Catalogue of measures for urban aquatic ecosystems
rehabilitation** (Dias, Serra & Feio, University of Coimbra, 22 December 2025),
OneAquaHealth Horizon Europe, Grant Agreement 101086521.

- **DOI:** [10.5281/zenodo.20040211](https://doi.org/10.5281/zenodo.20040211)
- **Licence:** CC-BY-4.0
- **Page numbers in `measures.json` are the printed document page numbers**, as
  they appear in the PDF's own table of contents — not PDF sheet indices. In
  this document the printed page *N* is PDF sheet *N+2*.

**The PDF is not committed.** It is 15 MB, it belongs to its authors, and citing
it is enough. `data/sources/` is gitignored. To fetch it:

```bash
mkdir -p data/sources
curl -L -o "data/sources/OAH_Catalogue_of_measures.pdf" \
  "https://zenodo.org/api/records/20040211/files/OAH_Catalogue%20of%20measures.pdf/content"

python scripts/build_measures.py      # rebuilds data/measures.json from it
```

`build_measures.py` reads the PDF only to verify that each cited page still
carries the measure named against it. If the PDF is absent it says so and leaves
`measures.json` untouched, so a fresh clone does not need the download.
