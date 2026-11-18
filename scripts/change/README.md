# scripts/change: land-use change choice model

Binary logit of **undeveloped → developed** for 20 m cells, following Table 18 of Prof. Eluru's reference
report (UCF/FDOT *Final Report*, binary logit of land-use change). The write-up is
`DISCRETE_CHOICE_MODELS_REPORT.md` at the repo root; the original design is in
`docs/archive/CHANGE_MODEL_PLAN_2026-11-02.md`; the results are in `outputs/change/` (`outputs/change/README.md`
says what is in each folder).

- **Trial** (default): 3 assembly constituencies (Maheshwaram, Rajendranagar, Serilingampally; 1,164 km²),
  2017→2020 and 2020→2023, 20,000 sampled cells. Results in `outputs/change/trial/`.
- **All of HMDA** (`REGION=hmda`): 7,649 km², 120,000 sampled cells, every factor retested. Results in
  `outputs/change/hmda/`, or `outputs/change/hmda_persist/` with `OUTCOME=persist`.

## Pipeline

| step | script | what it does | output |
|---|---|---|---|
| 0 | `00_eyeball_sample.py` | 60 cells to check the change definition by eye in Google Earth Pro | `data/processed/change/eyeball_*` |
| 1 | `01_form20_ocr.py` | OCR of booth-wise votes from the scanned Form 20 result sheets (2018 assembly election) | `data/processed/change/form20_2018.csv` |
| 2 | `02_trial_data.py` | region, outcome, choice-based sample (one cell per 200 m block per outcome), distances, road km, WorldPop, booth-vote kernel density | `trial_cells.parquet` |
| 3 | `03_trial_logit.py` | first trial: base model ± votes / WorldPop | `outputs/change/trial/` |
| 4 | `04_more_factors.py` | the rest of the §5c factors: land use within 1 km, mix, dense-city distance, night lights, major/minor road km, terrain (Earth Engine), lakes, restricted land, GO 111 stand-in, contagion | `trial_cells_full.parquet` |
| 5 | `05_full_logit.py` | full model and the tests (group Wald, cross-validated AUC, AME, VIF, Chow, temporal transfer, Moran's I, calibration, causal-direction checks) | `outputs/change/trial/full/` |
| 6 | `06_table18.py [census\|florida]` | Table 18-style final model: backward elimination to \|t\| ≥ 1.96, per-period columns, fit statistics | `outputs/change/trial/table18*/` |
| 7 | `07_census_factors.py` | Economic Census 2013 jobs, Census 2011 people, SECC vehicle ownership, linked to villages and attached to the cells | `trial_cells_census.parquet` |
| 8 | `08_consistency.py` | HMDA only: the final specification refitted, and the elimination rerun, in subregions (trial ACs, rest of HMDA, rings around the CBD) | `<results>/consistency/` |
| 9 | `09_added_value.py` | how much each group of factors adds (nested and drop-one ρ² and cross-validated AUC), since with 120,000 cells almost anything passes \|t\| ≥ 1.96 | `<results>/added_value/` |
| 10 | `10_bus_stops.py` | distance to the nearest bus stop and stops within 1 km, added to the final specification | `<results>/bus_stops/` |
| 11 | `11_zoning.py` | HMDA Master Plan 2031 zone dummies (base: conservation), added to the final specification: rates by zone, group Wald, elimination | `<results>/zoning/` |

**Switches** (environment variables, read by every script):

| variable | values | effect |
|---|---|---|
| `REGION` | `trial` (default), `hmda` | `hmda`: all of HMDA. Booth votes are left out (they exist for ACs 50–52 only); AC dummies become old-district dummies (base Rangareddy); 60,000 cells per period. `trial` reproduces the trial exactly |
| `OUTCOME` | `both` (default), `persist` | how change is counted (see Outcome below). `persist` writes to `hmda_persist` / `trial_persist` |
| `SKIP_EE` | `1` | step 4 skips the Earth Engine terrain; add it later with `04_more_factors.py terrain` |

Order for all of HMDA: `02`, `04` with `SKIP_EE=1`, `04 terrain` (Earth Engine), `07`, then `06 census` (main),
`06 florida`, `06`, `08`, `05`, `09`, `10`, `11`. Results: `outputs/change/hmda/` and
`outputs/change/hmda_persist/`, written up in `DISCRETE_CHOICE_MODELS_REPORT.md` §6–10. Run times: about 5 minutes for `02` and `04`, 14 minutes for
terrain, under 2 minutes for all models and tests.

Run order (trial): 2 → 4 → 7 → 3, 5, 6. Steps 3, 5 and 6 take a minute or two each. Step 4 takes about 15 minutes,
because reading the OSM files dominates. Step 7 takes about 10 minutes, because reading the SHRUG CSVs dominates.

**Shortcut:** the samples with every factor are in the repo (`data/processed/change/trial_cells_*.parquet`,
`hmda_cells_*.parquet`, `hmda_persist_cells_*.parquet`, each `_full` and `_census`), so `05`, `06`, `08` and `09`
run without any of the raw data (`11` also needs `data/processed/masterplan/mp2031_zones_20m.tif`, also in the repo):

```
python scripts/change/06_table18.py            # without census factors
python scripts/change/06_table18.py census     # + census factors
python scripts/change/06_table18.py florida    # final: census, job mass as in Table 18
python scripts/change/05_full_logit.py         # all factors + tests
REGION=hmda python scripts/change/06_table18.py census                  # all of HMDA, strict rule
REGION=hmda OUTCOME=persist python scripts/change/06_table18.py census  # all of HMDA, persistence rule
```

## Outcome (change = 1 / 0)

- **At risk:** cells undeveloped at the start: final map class trees or open, and Open Buildings cover < 5%.
- **Strict rule (`OUTCOME=both`, default):**
  - change = 1: map built at the end **and** Open Buildings cover ≥ 20% **and** 3 × 3 cover gain ≥ 0.10;
  - change = 0: still undeveloped by both sources;
  - dropped: cells where the two sources disagree (10–13% in the trial, 3–6% in HMDA);
  - rate in HMDA: 0.23% (2017–20) and 0.22% (2020–23) of open land.
- **Persistence rule (`OUTCOME=persist`):**
  - change = 1: map built in **both** the year before the end and the end year (e.g. 2019 and 2020);
  - change = 0: map trees or open in both of those years, and no Open Buildings gain under the strict rule;
  - rate in HMDA: 1.44% and 1.40%. 80% of the map's new building stays built in every later year, so the
    strict rule keeps only about 1 in 7 real changes.
- **Which rule is final:** not settled. The persistence run has odd signs, all from changes with no Open
  Buildings gain; the 60-cell eyeball check (`EYEBALL_CHECK_HOWTO.md`, repo root) decides between persistence
  and a middle rule (persistence plus an Open Buildings 3 × 3 gain ≥ 0.05, not coded yet).
- **Sampling correction:** the sample over-samples changes, so the constant is corrected (King & Zeng); the
  slopes are unaffected.
- **Standard errors:** clustered by 4 km tile.

## Raw data (not in git; where to get it)

| data | used by | source |
|---|---|---|
| final 20 m maps 2017/2020/2023 | 2, 4 | `outputs/lu20/maps_final/` (our pipeline) |
| 20 m feature grids (Open Buildings cover, VIIRS) | 2, 4 | `data/raw/lu/lu20/grid_<year>/` (our pipeline) |
| Geofabrik OSM snapshots | 2, 4 | `data/raw/osm_snapshots/` (`scripts/lu20/download_snapshots.ps1`) |
| WorldPop 100 m | 2 | `outputs/lu20/worldpop/` |
| Form 20, 2018 (PDF scans) | 1 | ceotelangana.nic.in, GE_2018 Form-20, ACs 050–052 |
| 2017 polling-station coordinates | 2 | Rudkin's scrape of the ECI locator (`data/raw/voter/rudkin/telangana.csv`) |
| Copernicus GLO-30 DEM | 4 | Earth Engine (`COPERNICUS/DEM/GLO30_2024_1`), sampled at the points |
| 6th Economic Census 2013–14 microdata | 7 | microdata.gov.in / MoSPI DVD. The `.Nesstar` file has to be exported with Nesstar Explorer (on the DVD): Datasets → EC6A_ST36_TELANGANA → File → Export Dataset → STATA 8. Saved as `data/raw/ec6/ec6_telangana.parquet` |
| SHRUG 2.2 keys, PCA 2011, SECC, shrid polygons | 7 | devdatalab.org/shrug_download (CSV and GeoPackage; free). `data/raw/shrug/` |
| TGSRTC bus stops (5,177) | 10 | WRI India Transport Analytics Hub, shift-transport.org (Hyderabad → amenities → bus stops). `data/raw/transit_shift/Hyderabad__amenities__bus_stops.geojson` |
| HMDA Master Plan 2031 zoning, 20 m | 11 | `data/processed/masterplan/mp2031_zones_20m.tif` (in the repo), made by `scripts/masterplan/` from the 30 OpenCity sheets |

**Environments:**
- Everything runs in the project env (`.venv-xpu`) except `01_form20_ocr.py`, which needs PyMuPDF and
  RapidOCR (`pip install pymupdf rapidocr-onnxruntime pandas`) in a separate env.
- The 2018 Form 20 PDFs have a broken cross-reference table: pypdf sees only one page, PyMuPDF reads them all.
- Nesstar Explorer is an old program: while it exports, Windows shows it as "Not Responding" for about 4
  minutes. That is normal.

## Known limitations

- **Booth locations:** approximate. The 2018 booths are placed on 2017 coordinates by their position in the
  booth sequence, which gives 1.4–3 km noise. The fix is the 2018 polling-station list with names.
- **GO 111:** the zone is a stand-in (10 km of the two lakes), not the 84 notified villages.
- **Census inside GHMC:** GHMC is only two polygons in SHRUG, so census values there are city-wide averages.
- **Collinearity:** in a 3-constituency region the distances to CBD, metro and HITEC, job mass, road
  mileage and land-use mix overlap strongly. That is why everything was redone on all of HMDA: read the HMDA
  results, and the group tests rather than single coefficients.
- **Districts (HMDA):** taken from the nearest 2017 polling station, so approximate near the borders; they are
  the pre-2016 districts.
- **Change definition:** the 60-cell eyeball check is still to do (`EYEBALL_CHECK_HOWTO.md`).
- **Zoning:** covers 74% of HMDA (not the old city core); read from scans, see `scripts/masterplan/README.md`.
- **Bus stops:** today's stops, not those at the start of each period.
