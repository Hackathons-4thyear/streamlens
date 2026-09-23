# Stream photos you can legally use to test the vision prompt

Written for: whoever is tuning `api/app/ai/prompts/assess_v1.md` against real
imagery before the Gemini key goes in.

Every URL below returned HTTP 200 when checked on 23 September 2026, except the
four marked **(blocked to scripts)** — those sites reject automated requests but
work normally in a browser.

## Before you use anything

1. **Your own photos beat all of these.** They match the real task exactly: a
   phone camera, held by a person standing on a bank, in the weather of the day.
   Twenty of your own photos of any nearby stream, ditch or canal will tell you
   more about the prompt than two hundred stock images.
2. **Wikimedia Commons is not one licence.** Each file carries its own — CC0,
   CC BY, CC BY-SA, or public domain. Check the individual file page, not the
   category. CC BY and CC BY-SA require crediting the photographer and naming
   the licence; CC BY-SA also requires that anything you redistribute built from
   it carries the same licence.
3. **Testing a prompt is not publishing.** Feeding an image to a model privately
   to see what the model says is ordinary use. The licence obligations bite when
   you put the image in a slide deck, a paper, a README or a demo video — at that
   point credit it properly.
4. **Do not commit these images to this repository.** Keep them in an ignored
   local folder. Mixing third-party images into the repo creates a licensing mess
   for whoever picks the project up.
5. **Avoid images with recognisable people**, whatever the licence says. The
   prompt forbids the model from describing people, and testing on such images
   teaches you nothing useful about stream condition.

---

## A. The five OneAquaHealth research cities

The closest thing to the real thing: the actual water bodies the citizens will
be standing next to.

| # | City | Source |
|---|------|--------|
| 1 | Coimbra | [Category:Mondego River](https://commons.wikimedia.org/wiki/Category:Mondego_River) |
| 2 | Coimbra | [Category:Rivers of Portugal](https://commons.wikimedia.org/wiki/Category:Rivers_of_Portugal) |
| 3 | Benevento | [Category:Calore Irpino](https://commons.wikimedia.org/wiki/Category:Calore_Irpino) |
| 4 | Benevento | [Category:Sabato River](https://commons.wikimedia.org/wiki/Category:Sabato_River) |
| 5 | Benevento | [Category:Rivers of Italy](https://commons.wikimedia.org/wiki/Category:Rivers_of_Italy) |
| 6 | Toulouse | [Category:Garonne](https://commons.wikimedia.org/wiki/Category:Garonne) |
| 7 | Toulouse | [Category:Touch (river)](https://commons.wikimedia.org/wiki/Category:Touch_(river)) |
| 8 | Toulouse | [Category:Hers-Mort](https://commons.wikimedia.org/wiki/Category:Hers-Mort) |
| 9 | Toulouse | [Category:Canal du Midi](https://commons.wikimedia.org/wiki/Category:Canal_du_Midi) — hard-engineered channel |
| 10 | Ghent | [Category:Leie](https://commons.wikimedia.org/wiki/Category:Leie) |
| 11 | Ghent | [Category:Rivers of Ghent](https://commons.wikimedia.org/wiki/Category:Rivers_of_Ghent) |
| 12 | Ghent | [Category:Scheldt in Ghent](https://commons.wikimedia.org/wiki/Category:Scheldt_in_Ghent) |
| 13 | Ghent | [Category:Canals in Ghent](https://commons.wikimedia.org/wiki/Category:Canals_in_Ghent) |
| 14 | Oslo | [Category:Akerselva](https://commons.wikimedia.org/wiki/Category:Akerselva) |
| 15 | Oslo | [Category:Alna (river)](https://commons.wikimedia.org/wiki/Category:Alna_(river)) |
| 16 | Oslo | [Category:Hovinbekken](https://commons.wikimedia.org/wiki/Category:Hovinbekken) |
| 17 | Oslo | [Category:Frognerelva](https://commons.wikimedia.org/wiki/Category:Frognerelva) |
| 18 | Oslo | [Category:Rivers of Oslo](https://commons.wikimedia.org/wiki/Category:Rivers_of_Oslo) |

## B. One category per thing the questions actually ask about

Use these to test single questions in isolation. If the model cannot tell a
gabion from a natural bank when handed a category full of gabions, no amount of
prompt wording will save it in the field.

| # | Tests which question | Source |
|---|----------------------|--------|
| 19 | `channelType`, `bankType` | [Category:Stream beds](https://commons.wikimedia.org/wiki/Category:Stream_beds) |
| 20 | `bankType` (laid stones, `LAS`) | [Category:Gabions](https://commons.wikimedia.org/wiki/Category:Gabions) |
| 21 | `habitats` (riffles, `RF`) | [Category:Rapids](https://commons.wikimedia.org/wiki/Category:Rapids) |
| 22 | `fallenBiomass` | [Category:Woody debris](https://commons.wikimedia.org/wiki/Category:Woody_debris) |
| 23 | `waterFlow` (dry, `DRY`) | [Category:Dry riverbeds](https://commons.wikimedia.org/wiki/Category:Dry_riverbeds) |
| 24 | `waterAspect` (unusual colour, `CO`) | [Category:Algal blooms](https://commons.wikimedia.org/wiki/Category:Algal_blooms) |
| 25 | `waterAspect`, `sewage` | [Category:Water pollution](https://commons.wikimedia.org/wiki/Category:Water_pollution) |
| 26 | `sewage` | [Category:Sewage](https://commons.wikimedia.org/wiki/Category:Sewage) |
| 27 | `pollutedPipes` | [Category:Outfalls](https://commons.wikimedia.org/wiki/Category:Outfalls) |
| 28 | `dams` (barriers) | [Category:Weirs](https://commons.wikimedia.org/wiki/Category:Weirs) |
| 29 | `dams` (culverted reaches) | [Category:Culverts](https://commons.wikimedia.org/wiki/Category:Culverts) |
| 30 | `dams` (passable barriers) | [Category:Fish ladders](https://commons.wikimedia.org/wiki/Category:Fish_ladders) |
| 31 | `vegCoverL/R` | [Category:Riparian zones](https://commons.wikimedia.org/wiki/Category:Riparian_zones) |
| 32 | `invasiveL/R` — Japanese knotweed | [Category:Fallopia japonica](https://commons.wikimedia.org/wiki/Category:Fallopia_japonica) |
| 33 | `invasiveL/R` — giant reed | [Category:Arundo donax](https://commons.wikimedia.org/wiki/Category:Arundo_donax) |
| 34 | `invasiveL/R` — pampas grass | [Category:Cortaderia selloana](https://commons.wikimedia.org/wiki/Category:Cortaderia_selloana) |
| 35 | `invasiveL/R` — general | [Category:Invasive plant species](https://commons.wikimedia.org/wiki/Category:Invasive_plant_species) |
| 36 | bank condition | [Category:Erosion](https://commons.wikimedia.org/wiki/Category:Erosion) |
| 37 | before/after, for the Phase 2 measures table | [Category:River restoration](https://commons.wikimedia.org/wiki/Category:River_restoration) |
| 38 | general | [Category:Streams](https://commons.wikimedia.org/wiki/Category:Streams) |

## C. Search platforms, when you need volume

| # | Source | Notes |
|---|--------|-------|
| 39 | [Flickr, filtered to Creative Commons](https://www.flickr.com/search/?text=urban%20stream&license=2%2C3%2C4%2C5%2C6%2C9) | The licence filter is already in that URL. Still check each photo's licence. |
| 40 | [CC Search](https://search.creativecommons.org/) | Front door to Creative Commons' own search. |
| 41 | [Openverse](https://openverse.org) **(blocked to scripts)** | Searches Flickr, Commons and more in one place, licence-filtered. |
| 42 | [iNaturalist](https://www.inaturalist.org) | Filter observations to a CC licence. Strong for invasive plant identification, which is the hardest question in the set. |
| 43 | [Unsplash](https://unsplash.com) **(blocked to scripts)** | Generous licence, but heavily aestheticised — good scenery, poor proxy for a phone snap of a drainage ditch. |
| 44 | [Pexels](https://www.pexels.com) **(blocked to scripts)** | Same caveat as Unsplash. |
| 45 | [Geograph](https://www.geograph.org.uk/) **(blocked to scripts)** | CC BY-SA, British Isles only, but unusually good for *ordinary* watercourses rather than beautiful ones. |

---

## How to actually run the test

1. Put 20–30 images in a local folder that git ignores, spread across the range:
   concrete channel, natural gravel bed, dry bed, foamy water, heavily vegetated
   bank, bare paved bank, weir, outfall.
2. Set `AI_PROVIDER=gemini` and your key in `api/.env`.
3. Post each one and record what comes back:

   ```bash
   curl -s -X POST http://localhost:8000/assess/suggest \
     -F "site_id=C1" -F "upstream=@photo.jpg" | python -m json.tool
   ```

4. Watch three things, in this order of importance:
   - **The `dropped` list.** Anything in it means the model is inventing codes,
     and the prompt's answer list is not landing.
   - **`NS` rate.** A model that never says "not sure" is guessing. A model that
     always says it is useless. On a mixed set, somewhere around a fifth to a
     third of answers being `NS` is a healthy sign.
   - **Whether the reasons point at the photo.** "The bed is grey concrete right
     across" is a good reason. "This appears to be a modified watercourse" is the
     model restating its own answer, and usually means it guessed.
5. Keep a note of which images the model got wrong, and re-run them after every
   prompt change. That set is worth more than the prompt.
