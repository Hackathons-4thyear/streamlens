# `docs/fhir/`

FHIR R4 export for StreamLens, shaped against the OneAquaHealth IG
([hl7-eu/oah](https://github.com/hl7-eu/oah)).

| File | What it is |
|---|---|
| [`validation-report.md`](validation-report.md) | **Start here.** The validator result, how to reproduce it, every modelling decision and its reasoning, and the state of the IG when this was built. |
| `example-bundle.json` | A real export from a running StreamLens: one assessment as a `collection` Bundle — 1 Location, 14 Observations, 1 Provenance. |
| `validation-oah-ig.json` | Validator `OperationOutcome` against the OAH IG profiles. **0 errors, 0 warnings.** |
| `validation-base-r4.json` | Validator `OperationOutcome` against base R4 alone, for comparison. |
| `CodeSystem-citizen-question.json` | 24 local question codes, `experimental: true`. |
| `CodeSystem-citizen-answer.json` | 85 local answer codes, `experimental: true`. |

## Getting a bundle

```bash
GET /observations/{id}/fhir      # one assessment
GET /cities/{city}/fhir          # recent assessments in a city
```

Both return `application/fhir+json`. The web app has an **Export FHIR** button on
a site page and on the city page.

## In one paragraph

A citizen assessment becomes a `LocationOah` for the site, one
`ObservationIndicatorsOah` per answered question (multi-select answers use
`component`), and a `Provenance` naming the citizen as `author` by pseudonymous
identifier and, where one was used, the AI as an `assembler` `Device` carrying
the model name and prompt version. `Observation.performer` is a contained
`Organization` for the monitoring programme or team, because StreamLens holds no
identity for its citizens and the profile requires a performer. The reasoning
behind each of those choices — including the ones a reviewer might argue with —
is in the validation report.
