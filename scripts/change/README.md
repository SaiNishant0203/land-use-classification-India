# scripts/change: land-use change choice model (trial)

Binary logit of **undeveloped → developed** for 20 m cells, following Table 18 of Prof. Eluru's reference
report (UCF/FDOT *Final Report*, binary logit of land-use change). The design is in `CHANGE_MODEL_PLAN.md`
at the repo root; the results are in `outputs/change/trial/` (start with `outputs/change/README.md`).

This is a **trial on 3 assembly constituencies** (Maheshwaram, Rajendranagar, Serilingampally; 1,164 km²),
2017→2020 and 2020→2023, 20,000 sampled cells.

## Pipeline

| step | script | what it does | output |
|---|---|---|---|
| 0 | `00_eyeball_sample.py` | 60 cells to check the change definition by eye in Google Earth Pro | `data/processed/change/eyeball_*` |
| 1 | `01_form20_ocr.py` | OCR of booth-wise votes from the scanned Form 20 result sheets (2018 assembly election) | `data/processed/change/form20_2018.csv` |
| 2 | `02_trial_data.py` | region, outcome, choice-based sample (one cell per 200 m block per outcome), distances, road km, WorldPop, booth-vote kernel density | `trial_cells.parquet` |
| 3 | `03_trial_logit.py` | first trial: base model ± votes / WorldPop | `outputs/change/trial/` (`TRIAL_RESULTS.md`) |
| 4 | `04_more_factors.py` | the rest of the §5c factors: land use within 1 km, mix, dense-city distance, night lights, major/minor road km, terrain (Earth Engine), lakes, restricted land, GO 111 stand-in, contagion | `trial_cells_full.parquet` |
| 5 | `05_full_logit.py` | full model and the tests (group Wald, cross-validated AUC, AME, VIF, Chow, temporal transfer, Moran's I, calibration, causal-direction checks) | `outputs/change/trial/full/` (`FULL_MODEL_RESULTS.md`) |
| 6 | `06_table18.py [census\|florida]` | Table 18-style final model: backward elimination to \|t\| ≥ 1.96, per-period columns, fit statistics | `outputs/change/trial/table18*/` |
| 7 | `07_census_factors.py` | Economic Census 2013 jobs, Census 2011 people, SECC vehicle ownership, linked to villages and attached to the cells | `trial_cells_census.parquet` |
| 8 | `08_consistency.py` | HMDA only: the final specification refitted, and the elimination rerun, in subregions (trial ACs, rest of HMDA, rings around the CBD) | `outputs/change/hmda/consistency/` |

**All of HMDA (11 Nov):** every script takes `REGION=hmda` (default `trial`, which reproduces the trial exactly).
Booth votes are left out (they exist for ACs 50–52 only); AC dummies become old-district dummies; 60,000 cells per
period. Order: `02`, `04` with `SKIP_EE=1`, `04 terrain` (Earth Engine), `07`, then `06 census` (main), `06 florida`,
`06`, `08`, `05`. Results: `outputs/change/hmda/HMDA_RESULTS.md`.

Run order (trial): 2 → 4 → 7 → 3, 5, 6. Steps 3, 5 and 6 take a minute or two each. Step 4 takes about 15 minutes,
because reading the OSM files dominates. Step 7 takes about 10 minutes, because reading the SHRUG CSVs dominates.

**Shortcut:** `data/processed/change/trial_cells_full.parquet` and `trial_cells_census.parquet` are in the
repo, so `05_full_logit.py` and `06_table18.py` run without any of the raw data:

```
python scripts/change/06_table18.py            # without census factors
python scripts/change/06_table18.py census     # + census factors
python scripts/change/06_table18.py florida    # final: census, job mass as in Table 18
python scripts/change/05_full_logit.py         # all factors + tests
```

## Outcome (change = 1 / 0)

- **At risk:** cells undeveloped at the start: final map class trees or open, and Open Buildings cover < 5%.
- **Change = 1 (confirmed development):** map built at the end **and** Open Buildings cover ≥ 20% **and** 3 × 3
  cover gain ≥ 0.10.
- **Change = 0:** still undeveloped by both sources.
- **Dropped:** cells where the two sources disagree, 10–13%.
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
  mileage and land-use mix overlap strongly. Read the group tests, not single coefficients, and redo it on the
  full HMDA sample.
- **Change definition:** the 60-cell eyeball check (`data/processed/change/EYEBALL_GUIDE.md`) is still to do.
