# Land use and land-use change in Hyderabad (HMDA)

Land use and transportation planning for the Hyderabad Metropolitan Development Authority area
(7,649 km²). The project has two parts:

1. **Land-use maps.** A LightGBM classifier on Sentinel-2, Open Buildings 2.5D and night lights labels
   every 20 m cell of HMDA with one of five classes (residential, non-residential built, water, trees,
   other open), for every year 2017–2023.
2. **Land-use change model.** A binary logit (discrete-choice) model of which open land gets built on
   within 3 years, following Table 18 of Prof. Eluru's reference report (UCF/FDOT). Built on the maps.

## Where things stand (17 November 2026)

- **Maps: final.** 20 m, 2017–2023, hand-label macro-F1 0.649 [0.583, 0.719]; non-residential F1 0.50.
- **Change model: method final, change rule provisional.** 120,000 sampled 20 m cells across HMDA,
  2017→2020 and 2020→2023; ρ² about 0.24 and cross-validated AUC 0.84 (strict rule). Development follows
  existing development, major roads, the old CBD and the ORR interchanges, and avoids trees, lake edges,
  steep and restricted land. Master Plan 2031 zoning matters in the planned direction.
- **Open question:** how to count "change". The strict rule (map + Open Buildings) keeps only about 1 in 7
  real changes; the persistence rule (built in the map two years running) gives a rate about 6× higher
  and some odd signs. A 60-cell eyeball check (`EYEBALL_CHECK_HOWTO.md`) decides; until then every HMDA
  table, including the zoning odds ratios, is provisional.

## Read this first

| document | what it covers |
|---|---|
| **`DISCRETE_CHOICE_MODELS_REPORT.md`** | **the main report**: the change model's data, method, final results, open questions, and every earlier run |
| `EYEBALL_CHECK_HOWTO.md` | the pending check that settles the change rule |
| `DATA.md` | every data file: how it was made, bands and columns, what runs with what |
| `FEATURES.md` | the classifier's 181 features (10 m model) and the tests of reducing them |
| `scripts/lu20/README.md`, `outputs/lu20/RESULTS.md` | the 20 m production classifier and its evaluation |
| `scripts/change/README.md` | the change-model pipeline: scripts, switches (`REGION`, `OUTCOME`), raw data |
| `scripts/masterplan/README.md` | digitising the Master Plan 2031 zoning from 30 scanned sheets |
| `scripts/lu/README.md` | the original 10 m pipeline and the October 10 m transition models |
| `docs/CLASSIFIER_10M_SEP2026.md` | the September write-up of the first 10 m classifier (the old README) |
| `docs/archive/` | superseded plans and intermediate write-ups, kept for the record (see its README) |

## Repository layout

| folder | contents |
|---|---|
| `scripts/lu/` | 10 m classifier (2023), product audit, 10 m transition / choice models |
| `scripts/lu20/` | 20 m classifier with year-dated OSM labels; final maps 2017–2023 |
| `scripts/change/` | change model: samples, factors, Table 18, tests, bus stops, zoning |
| `scripts/masterplan/` | Master Plan 2031 georeferencing, classification, mosaic |
| `data/processed/` | small processed data kept in git (training samples, hand labels, change-model samples, zoning layer); most of this folder is git-ignored |
| `outputs/lu/`, `outputs/lu20/` | classifier results and the 10 m choice-model outputs |
| `outputs/change/` | change-model tables and test results, one folder per run (see `outputs/change/README.md`) |

The `.md` files inside `outputs/` (`TABLE18.md`, `ZONING.md`, `CONSISTENCY.md`, `ADDED_VALUE.md`,
`BUS_STOPS.md`, `REPORT.md`, `RESULTS.md`) are written by the scripts and are overwritten on a rerun.

## Running

- **Change model:** the model-ready samples are in git (`data/processed/change/*.parquet`), so every model
  and test reruns in a couple of minutes with no raw data. Commands for every run are in §17 of the report.
- **Classifier:** see `DATA.md` §1 (quick start) and §7 (what runs with what). The raster tiles (~8 GB)
  are shared separately as a zip; unzip into the repository root.

Python packages: `numpy pandas pyarrow geopandas rasterio scipy scikit-learn lightgbm statsmodels
matplotlib pyproj shapely requests earthengine-api`
