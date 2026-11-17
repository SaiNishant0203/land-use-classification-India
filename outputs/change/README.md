# Land-use change model (discrete choice)

*Hyderabad / HMDA, November 2026. Branch `exp/change-model` of
`SaiNishant0203/land-use-classification-India`. State on 17 November 2026.*

## What this is

Prof. Eluru asked for the next step after the land-use maps. The question is **why** land changes, not
only where. The template is Table 18 in his reference report: a UCF/FDOT study for Florida, where the
first step is a **binary logit of land-use change** (change vs no change, for vacant parcels).

Our version:
- **Unit:** a 20 m cell from our final maps (we have no parcels).
- **Outcome:** **undeveloped → developed**, 2017→2020 and 2020→2023.
- **Explanatory factors:** all measured **before** the period.
- **Estimation:** choice-based sample (one cell per 200 m block per outcome), constant corrected for the
  sampling (King & Zeng), standard errors clustered by 4 km tile, backward elimination to |t| ≥ 1.96.

## Stages so far

| stage | when | results | in short |
|---|---|---|---|
| trial, 3 assembly constituencies (1,164 km²) | 2–8 Nov | `trial/` | 19,813 cells; ρ² 0.222, AUC 0.821. Booth-wise votes add nothing beyond built-up land nearby |
| all of HMDA (7,649 km²), every factor retested | 11 Nov | `hmda/HMDA_RESULTS.md` | 120,000 cells; ρ² 0.236, AUC 0.841. Old CBD and ORR interchanges matter HMDA-wide; airport and HITEC only in the south-west |
| corrected change count (persistence) | 11 Nov | `hmda_persist/PERSIST_RESULTS.md` | change rate 0.23% → about 1.4% per 3 years; ρ² 0.292, AUC 0.849, but some odd signs |
| how much each group of factors adds | 11 Nov | `hmda*/added_value/` | distance to existing development alone takes AUC from 0.60 to 0.80 |
| bus stops | 11 Nov | `hmda*/bus_stops/` | half as far from a stop → odds × 1.12–1.16; AUC +0.001 |
| master-plan zoning (MDP 2031) | 12 Nov | `hmda*/zoning/` | the first real policy factor: residential × 1.76, manufacturing × 3.0, protected land × 0.67 against conservation |

**Provisional:** the tables are final only once the change rule is settled (next section).

## How change is counted: the open question

| rule | a cell counts as changed when | share of open land per 3 years | results |
|---|---|---|---|
| **strict** | our map says built at the end **and** Google Open Buildings cover ≥ 20%, with a 3 × 3 gain ≥ 0.10 | 0.23% (2017–20), 0.22% (2020–23) | `trial/`, `hmda/` |
| **persistence** | our map says built in **both** of the last two years of the period | 1.44%, 1.40% | `hmda_persist/` |
| middle (not run yet) | persistence **and** an Open Buildings 3 × 3 gain ≥ 0.05 | about 0.5% | |

At risk in every rule: cells that are trees or open in our map at the start, with Open Buildings cover < 5%.

**Why the strict rule undercounts:**
- Of the land our map called newly built in 2020, **80% is still built in 2021, 2022 and 2023**, so most of
  it is real. Real building stays built; classifier noise flips back.
- Open Buildings misses most new building at 20 m, so the strict rule keeps only about 1 in 7 real changes.
- The map's built share grew from 13.4% to 16.6% of HMDA in 2017–2023, about 40 km² a year, which fits the
  persistence rate (about 0.55% of open land a year).
- Florida counts a vacant parcel as changed when its tax-roll land-use code changes; their Table 18
  constant implies about 1% a year, the same order.

**Why it is not settled:**
- The persistence run has odd signs: steeper land and land farther from the city get built **more**, and
  trees no longer matter.
- They come entirely from changes where Open Buildings shows no gain at all (80% of the sampled changes).
  These are plotted layouts, tree-shaded houses, or rock read as built.
- A 60-cell **eyeball check** in Google Earth history decides (`EYEBALL_CHECK_HOWTO.md` at the repo root):
  mostly real → persistence; mostly noise → the middle rule.

## Main results

### 1. Trial, 3 constituencies (`trial/TABLE18_CENSUS.md`)

Maheshwaram, Rajendranagar and Serilingampally, picked so that booth-wise voter data could be tested as a
population measure (Prof.'s idea). Strict rule. Fit: ρ² = 0.22, cross-validated AUC 0.82.

| pulls development | holds it back |
|---|---|
| mixed land use within 1 km (strongest factor) | tree cover on the cell (odds × 0.33) and trees nearby |
| near the airport (twice as close → odds × 1.43) | lake beds, within 100 m of a lake (× 0.31) |
| near HITEC City / Financial District (× 1.29) | military, forest, protected or airport land (× 0.22) |
| near a major road (× 1.12) | slope and rocky ground (boulders) |
| more nearby jobs in **large establishments** (100+ workers) | more nearby jobs in **manufacturing** |
| road mileage in the 4 × 4 km window (+, in the version that keeps it) | higher SC/ST share in the village (Florida's % Hispanic analogue) |

- **Booth-wise votes** (2018 Form 20 by OCR, 1,477 of 1,479 booths): the busiest fifth of the area changed
  10–15× more than the quietest fifth, but in the model votes add nothing once the built neighbourhood is in
  (p = 0.76). Booth locations are approximate, which biases the effect towards zero.
- **Not significant:** population (votes, WorldPop, Census 2011), night lights, distance to the ORR, metro,
  old CBD, IT share of jobs, car ownership.

### 2. All of HMDA, every factor retested (`hmda/HMDA_RESULTS.md`)

Prof.'s note of 11 Nov: extend to the larger area and retest every variable; the small region is only a
check that the data and model work. Strict rule; 120,000 cells, 12,314 changes; old-district dummies in
place of constituencies; booth votes not available outside the trial.

- **Hold, same direction (11 of the trial's 18 factors):** tree cover and trees nearby, land-use mix, lake
  beds, slope, restricted land, distance to a major road, the share of jobs in big establishments.
- **New HMDA-wide:** the old CBD (half as far → odds × 1.57) and the nearest ORR interchange (× 1.18).
- **Drop out:** the airport (t = −1.2) and HITEC City (t = 0.2). Fitted on the trial constituencies alone,
  the HMDA data keep them (t = −6.0 and −2.9): the south-west corridor behaves differently. Real geography,
  not a data problem.
- **Consistency** (refitted in five subregions, `hmda/consistency/`): trees, land-use mix and lake beds hold
  everywhere; distance to the CBD changes sign inside 20 km (inside the city, building happens at the edge);
  the ORR effect fades beyond 35 km.
- **Census:** the number of jobs, people and vehicles adds nothing; the kind of jobs does.

### 3. Are the factors any good? (`hmda/added_value/`)

| model (strict rule) | AUC |
|---|---|
| period and district only | 0.60 |
| + distance to the existing city | **0.80** |
| + land use within 1 km | 0.82 |
| + everything else (access, terrain, census) | 0.84 |

- Most of the prediction is "new building happens next to existing building".
- With 120,000 cells, factors with tiny effects still pass |t| ≥ 1.96, so the added fit is reported along
  with the t-values.
- Missing compared with Florida: parcel size and value, zoning (now added, below), income, travel time.

### 4. Master-plan zoning (`hmda/zoning/`, `hmda_persist/zoning/`)

HMDA Metropolitan Development Plan 2031 (approved 2013, so before both periods), read from the 30 scanned
district sheets onto our 20 m grid (`scripts/masterplan/README.md`). It covers 74% of HMDA; the old city
core is not in these sheets. Odds of being built against agricultural conservation land:

| planned zone | strict rule | persistence rule |
|---|---|---|
| manufacturing | × 3.0 | × 1.8 |
| residential | × 1.76 [1.45, 2.15] | × 1.44 |
| commercial / multiple use (incl. the ORR growth corridor) | × 1.5 | × 1.24 |
| public / semi-public | × 1.8 | × 1.4 |
| GO 111 bio-conservation | × 1.7 | × 1.3 |
| peri-urban | × 1.1 (not significant) | × 1.0 (not significant) |
| protected green, water, reserves | **× 0.67** | **× 0.71** |

- Jointly very significant (χ² 185 and 173 on 8 df), in both periods and under both rules.
- The added fit is small (AUC +0.004), because planners zoned residential land around existing towns.
- GO 111 (the lake-protection zone) gets built *more* than ordinary farmland: it lies close to the city,
  and building went ahead despite the restrictions.

### 5. Bus stops (`hmda/bus_stops/`)

5,177 TGSRTC stops from the WRI India Transport Analytics Hub (shift-transport.org). Half as far from a
stop → odds × 1.12–1.16, AUC +0.001. They are today's stops, so some may have followed development.

### 6. The tests used (`*/full/`)

- **Individual effects:** z-test per factor; **joint Wald test per group of factors** (robust to
  clustering); average marginal effects.
- **Prediction:** cross-validated AUC with whole 4 km tiles held out; nested and drop-one added fit.
- **Collinearity:** variance inflation factors.
- **Stability over time:** Chow test; temporal transfer (fit 2017–20, predict 2020–23: AUC 0.834 strict,
  0.840 persistence).
- **Model checks:** Moran's I of residuals (about 0.19 strict, 0.13 persistence); calibration by decile.
- **Causal-direction checks:** roads added *during* the period; previous-period change nearby (contagion);
  GO 111 × 2020–23 (inconclusive).

## Where things are

| | |
|---|---|
| `CHANGE_MODEL_PLAN.md` (repo root) | the original design (2 Nov): outcome, sampling, candidate factors |
| `scripts/change/` | code, steps 0–11; `scripts/change/README.md` has the pipeline, switches and data sources |
| `scripts/masterplan/` | master-plan zoning layer from the 30 scanned sheets |
| `outputs/change/trial/` | trial: `TRIAL_RESULTS.md` (votes), `FULL_MODEL_RESULTS.md` (all factors, tests), `TABLE18_RESULTS.md`, `TABLE18_CENSUS.md` (final trial table) |
| `outputs/change/hmda/` | all of HMDA, strict rule: `HMDA_RESULTS.md`, `table18_census/` (main), `table18_florida/`, `table18/`, `consistency/`, `full/`, `added_value/`, `bus_stops/`, `zoning/` |
| `outputs/change/hmda_persist/` | the same, persistence rule: `PERSIST_RESULTS.md` |
| `data/processed/change/` | the samples with every factor: `trial_cells_full/census.parquet`, `hmda_cells_full/census.parquet`, `hmda_persist_cells_full/census.parquet`; the eyeball form and points |
| `data/processed/masterplan/mp2031_zones_20m.tif` | the zoning layer on the 20 m grid |
| `EYEBALL_CHECK_HOWTO.md` (repo root) | how to do the 60-cell eyeball check |

**Quick start:** from the repo root, in the project env:

```
python scripts/change/06_table18.py florida                       # trial table, about a minute
REGION=hmda python scripts/change/06_table18.py census            # HMDA, strict rule
REGION=hmda OUTCOME=persist python scripts/change/06_table18.py census
```

These need no raw data. The zoning and bus-stop tests (`11`, `10`) also need the zoning layer (in the repo)
and the bus-stop file (not in the repo).

## Data sources

- **Our final 20 m maps:** every year 2017–2023.
- **Google Open Buildings temporal:** building cover per year.
- **OpenStreetMap:** Geofabrik snapshots dated 1 Jan 2018 and 1 Jan 2021.
- **Copernicus DEM, VIIRS night lights, WorldPop.**
- **Form 20, 2018** (CEO Telangana), constituencies 50–52.
- **6th Economic Census 2013–14 microdata** (MoSPI).
- **SHRUG 2.2** (Development Data Lab): Census 2011, SECC 2011–12, village boundaries, keys.
- **HMDA Metropolitan Development Plan 2031**, 30 district sheets (OpenCity, data.opencity.in).
- **TGSRTC bus stops** (WRI India Transport Analytics Hub, shift-transport.org).

## Open items

1. **Eyeball check** → choose the change rule → code the middle rule if needed → one rerun (about 20
   minutes) → the final Table 18 for Prof., with zoning.
2. **Factors beyond "near existing development" are still thin.** Next candidates: network travel time,
   flood exposure, ward-level census, land values.
3. **Data to request through Prof.:**
   - the master plan as GIS (our layer is read from scans);
   - **HMDA / TS-bPASS layout and building approvals with locations**, the closest thing to Florida's
     tax-roll data, which would settle the change question;
   - the traffic-zone data of the 2013 Comprehensive Transportation Study.
4. **Booth votes HMDA-wide:** about 31 more constituencies of 2018 Form 20 sheets, plus the 2018
   polling-station list with names to place the booths exactly.
5. **GO 111:** the 84 notified villages, for a proper before/after test of the 2022 repeal.
6. **Further Florida steps:** the new land-use type (residential vs non-residential) after change.
