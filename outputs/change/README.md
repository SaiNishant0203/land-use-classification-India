# Land-use change model (discrete choice): trial run

*Hyderabad / HMDA, November 2026. Branch `exp/change-model` of
`SaiNishant0203/land-use-classification-India`.*

## What this is

Prof. Eluru asked for the next step after the land-use maps. The question is **why** land changes, not
only where. The template is Table 18 in his reference report: a UCF/FDOT study for Florida, where the
first step is a **binary logit of land-use change** (change vs no change, for vacant parcels).

Our version:
- **Unit:** a 20 m cell from our final maps (we have no parcels).
- **Outcome:** **undeveloped → developed**, 2017→2020 and 2020→2023.
- **Explanatory factors:** all measured **before** the period.
- **Trial area:** 3 assembly constituencies (Maheshwaram, Rajendranagar, Serilingampally; 1,164 km²), so that
  booth-wise voter data could be tested as a population measure (Prof.'s idea).
- **Sample:** 20,000 cells (about 3,000 changes).

## How change is defined

Most pixel-level "change" between two classified maps is classification noise: about 19% of pixels change
class in 3 years, but real development is about 0.1% of open land a year. So a cell counts as developed only
when **two independent sources agree**:
- our map says built at the end, and
- Google Open Buildings shows a new building (cover from < 5% to ≥ 20%).

A cell counts as unchanged when both say still undeveloped. Cells where the two disagree (10–13%) are left out.

## Main results

### 1. Final model (Table 18 layout, `trial/TABLE18_CENSUS.md`)

Backward elimination to |t| ≥ 1.96. Standard errors are clustered by 4 km tile, because neighbouring cells aren't independent.
Fit: ρ² = 0.22, cross-validated AUC 0.82.

| pulls development | holds it back |
|---|---|
| mixed land use within 1 km (strongest factor) | tree cover on the cell (odds × 0.33) and trees nearby |
| near the airport (twice as close → odds × 1.43) | lake beds, within 100 m of a lake (× 0.31) |
| near HITEC City / Financial District (× 1.29) | military, forest, protected or airport land (× 0.22) |
| near a major road (× 1.12) | slope and rocky ground (boulders) |
| more nearby jobs in **large establishments** (100+ workers) | more nearby jobs in **manufacturing** |
| road mileage in the 4 × 4 km window (+, in the version that keeps it) | higher SC/ST share in the village (Florida's % Hispanic analogue) |

- **Not significant once the above are in:** population (2018 booth votes, WorldPop, Census 2011), night lights,
  distance to the ORR, metro, old CBD, IT share of jobs, car ownership.
- **Job mass:** jobs within 5 km is positive on its own (as in Florida), but it adds nothing once land-use mix
  is in, because the two overlap (r = 0.74).

### 2. Booth-wise voter data (`trial/TRIAL_RESULTS.md`)

- **Data:** votes polled per booth, from the scanned 2018 Form 20 result sheets by OCR (1,477 of 1,479 booths read).
- **Raw correlation:** strong. The most populated fifth of the area developed 10–15 times more often than the least
  populated fifth.
- **In the model:** it adds nothing once the built neighbourhood and roads are in.
- **Caveat:** booth locations are approximate (2017 coordinates, renumbered booths), which biases the effect
  towards zero. That is not settled until the 2018 polling-station list with names is found.

### 3. The tests used (`trial/FULL_MODEL_RESULTS.md`)

- **Individual effects:**
  - z-test per factor;
  - **joint Wald test per group of factors** (robust to clustering; safer than single coefficients
    when factors overlap);
  - average marginal effects (change in the 3-year probability of development).
- **Prediction:** cross-validated AUC with whole 4 km tiles held out (group alone, and loss when dropped).
- **Collinearity:** variance inflation factors.
- **Stability over time:**
  - Chow test (same effects in both periods? no, the sizes shift);
  - temporal transfer: a model fitted on 2017–20 predicts 2020–23 as well as one fitted on 2020–23.
- **Model checks:**
  - Moran's I of residuals (unexplained change clusters within about 500 m);
  - calibration by decile.
- **Causal-direction checks:**
  - roads added *during* the period (minor roads follow development, so they are not a cause);
  - previous-period change nearby (contagion);
  - GO 111 repeal in 2022 (natural experiment; inconclusive with a stand-in zone).

## Where things are

| | |
|---|---|
| `CHANGE_MODEL_PLAN.md` (repo root) | design: outcome, sampling, candidate factors, Indian-context factors, plan |
| `scripts/change/` | code, step 0–7; `scripts/change/README.md` has the pipeline, run order and data sources |
| `outputs/change/trial/TRIAL_RESULTS.md` | first trial: voter data |
| `outputs/change/trial/FULL_MODEL_RESULTS.md` | all 25 factors and the tests |
| `outputs/change/trial/TABLE18_RESULTS.md` | Table 18 layout, without census data |
| `outputs/change/trial/TABLE18_CENSUS.md` | Table 18 with Economic Census 2013 jobs, Census 2011 and SECC; final Florida-style table |
| `outputs/change/trial/table18*/`, `full/` | the tables as CSV |
| `data/processed/change/trial_cells_full.parquet`, `trial_cells_census.parquet` | the 20,000-cell samples with every factor; enough to refit all models |

**Quick start:** from the repo root, in the project env, run `python scripts/change/06_table18.py florida`.
It takes about a minute and needs no raw data.

## Data sources

- **Our final 20 m maps:** 2017, 2020, 2023.
- **Google Open Buildings temporal:** building cover per year.
- **OpenStreetMap:** Geofabrik snapshots dated 1 Jan 2018 and 1 Jan 2021.
- **Copernicus DEM, VIIRS night lights, WorldPop.**
- **Form 20, 2018** (CEO Telangana).
- **6th Economic Census 2013–14 microdata** (MoSPI).
- **SHRUG 2.2** (Development Data Lab): Census 2011, SECC 2011–12, village boundaries, keys.

## Open items

1. **Eyeball check:** check the change definition on 60 cells in Google Earth Pro (`data/processed/change/EYEBALL_GUIDE.md`).
2. **Full HMDA:** run on the whole of HMDA. In 3 constituencies the distances, job mass and road mileage are too
   collinear to separate.
3. **GO 111:** get the GO 111 village list and boundaries for a proper before/after test of the 2022 repeal.
4. **Booth list:** get the 2018 polling-station list with names, to place the booths exactly.
5. **Further steps:** the further steps of the Florida framework (new land-use type: residential vs non-residential).
