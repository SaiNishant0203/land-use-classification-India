# Land-use change in Hyderabad (HMDA): every discrete-choice model, its inputs and its results

*Complete record, September – 17 November 2026. Branch `exp/change-model`.*

This is the main report of the land-use change work. It explains what open land in HMDA gets built on, and
why, using a binary logit (discrete-choice) model that follows Table 18 of Prof. Eluru's reference report
(UCF/FDOT).

**How to read it.**
- **Part 1** is the model as it stands: the question, the current status, the data, the method, and the
  results on all of HMDA (strict and persistence change rules, added fit, bus stops, zoning), then
  limitations and next steps. Read this to understand the final model.
- **Part 2** is how we got here: the timeline, a register of every run with its inputs and results, and
  the earlier models that were superseded (300 m in September, 10 m in October, the 3-constituency trial in
  early November).
- **Part 3** has the commands to reproduce every run, a glossary, and pointers to the longer archived
  write-ups behind each section.

**Status in one line:** the method is final; the factor set and the zoning layer are done; **which change
rule to use is the one open question**, settled by a 60-cell eyeball check. Until then every HMDA table is
*provisional*.

---

## Contents

**Part 1: the model today**

1. [The question](#1-the-question)
2. [Where things stand: final, provisional, dropped](#2-where-things-stand-final-provisional-dropped)
3. [Inputs shared by the models](#3-inputs-shared-by-the-models)
4. [The final method, step by step](#4-the-final-method-step-by-step)
5. [Factor dictionary](#5-factor-dictionary)
6. [Results on all of HMDA, strict change rule (Phase D, 11 Nov)](#6-results-on-all-of-hmda-strict-change-rule-phase-d-11-nov)
7. [Counting change: the strict rule undercounts; the persistence rule (Phase E, 11 Nov)](#7-counting-change-the-strict-rule-undercounts-the-persistence-rule-phase-e-11-nov)
8. [How much does each group of factors add? (Phase F)](#8-how-much-does-each-group-of-factors-add-phase-f)
9. [Bus stops (Phase G)](#9-bus-stops-phase-g)
10. [HMDA Master Plan 2031 zoning (Phase H, 11–12 Nov)](#10-hmda-master-plan-2031-zoning-phase-h-1112-nov)
11. [Comparison with Florida's Table 18](#11-comparison-with-floridas-table-18)
12. [Limitations](#12-limitations)
13. [Next steps and data to request](#13-next-steps-and-data-to-request)

**Part 2: how we got here**

14. [Timeline](#14-timeline)
15. [Run register: inputs and results of every run](#15-run-register-inputs-and-results-of-every-run)
16. [Phase A (Sep): 300 m conversion models](#16-phase-a-sep-300-m-conversion-models)
17. [Phase B (Oct): 10 m transition models](#17-phase-b-oct-10-m-transition-models)
18. [Phase C (2–8 Nov): change model, 3-constituency trial](#18-phase-c-28-nov-change-model-3-constituency-trial)

**Part 3: reference**

19. [How to reproduce every run](#19-how-to-reproduce-every-run)
20. [Glossary](#20-glossary)
21. [Detailed write-ups (archived)](#21-detailed-write-ups-archived)

---

# Part 1: the model today

---

## 1. The question

**Question.** For land that is open or under trees at the start of a period, what makes it more or less
likely to be built on by the end? Which factors raise the odds (access, neighbourhood, jobs, planning) and
which lower them (terrain, lakes, restricted land)?

**Why a discrete-choice model.** Each piece of open land makes a yes/no "choice" over a period: get built
or stay open. A binary logit estimates how each factor shifts the odds of "yes". This is the first step of
the Florida land-use model (UCF/FDOT report, Figure 12, Table 18): a binary logit of whether a vacant parcel
changes use between t−1 and t.

---

## 2. Where things stand: final, provisional, dropped

### 2.1 Final
- **Main tables (provisional only in which change rule they use):**

  | | strict rule (§6.2) | persistence rule (§7.2) |
  |---|---|---|
  | change rate, share of open land per 3 years | 0.22–0.23% | 1.40–1.44% |
  | sample (changes) | 120,000 (12,314) | 120,000 (54,598) |
  | ρ² / AUC, cross-validated by tile | 0.236 / 0.841 | 0.292 / 0.849 |
  | with master-plan zones (§10.3) | 0.244 / 0.845 | 0.297 / 0.850 |

- **Method:** §4 (unit, at risk, choice-based sampling, King–Zeng, clustered errors, elimination, tests).
- **Region:** all of HMDA, every variable retested; the trial is a pipeline check, not a source of
  conclusions.
- **Robust findings:** open, tree-less, flat, unrestricted land in mixed neighbourhoods near existing
  development and major roads, away from lake beds, gets built; the old CBD and ORR interchanges matter
  HMDA-wide; the airport and HITEC matter only in the south-west; master-plan zoning matters in the planned
  direction.
- **Zoning layer:** `data/processed/masterplan/mp2031_zones_20m.tif`.

### 2.2 Provisional: the change rule (the eyeball check decides)
60 cells in Google Earth history (`EYEBALL_CHECK_HOWTO.md`): 40 "map-only" (map says built, Open Buildings
nothing), 10 "confirmed", 10 "stable" as controls; labels U / X / B / C / L / R / S / Q / N.

| what the map-only cells turn out to be | rule used in the final table |
|---|---|
| mostly buildings, construction or layouts (B, C, L) | **persistence**; maybe "layout" as its own outcome if L is common (Florida's partial conversion) |
| mostly no real change (N) | **middle rule**: persistence + Open Buildings gain ≥ 0.05 (≈ 0.5% per 3 years) |
| many solar / quarry (S, Q) | leave them out of "development" |

Then one rerun (about 20 minutes) gives the final Table 18 with zoning.

### 2.3 Dropped, and why
| what | why |
|---|---|
| differencing class maps as change | 19% of pixels "change" in 3 years; mostly noise |
| Dynamic World 300 m outcome | blurs real building with noise; superseded by 20 m maps |
| metro distance | not identified once built land nearby is in (A2, A3, every later run) |
| booth votes as population | null beyond built-up land (p = 0.76); only 3 ACs available |
| WorldPop, night lights | null under the strict rule; they enter only under the persistence rule, driven by the map-only changes |
| airport, HITEC as HMDA-wide drivers | local to the south-west corridor |
| road mileage / minor-road km | follows development (roads added during the period z 6.4–7.9) |
| job mass (number of jobs) | collinear with mix and road km; the *kind* of jobs carries the signal |

---

## 3. Inputs shared by the models

### 3.1 Our land-use maps (the backbone of the change model)

| item | value |
|---|---|
| classes | 1 residential, 2 non-residential built, 3 water, 4 forest / trees, 5 other open (farmland, barren, vacant) |
| resolution | 20 m (from Oct; the first model was 10 m) |
| years | every year 2017–2023 |
| model | LightGBM, 53 physical features (Sentinel-2 bands and indices, Open Buildings 2.5D building form, night lights, neighbourhood windows); AlphaEarth dropped because it adds nothing on hand labels and drifts between years |
| labels | OpenStreetMap **as mapped at the end of each year** (Geofabrik dated snapshots), plus agreement between land-cover products for water / forest / open |
| final variant | `cw_prior` (class weights set to the map shares), mean of 5 seeds |
| accuracy | hand-labelled test set (325 pixels, stratum-weighted): **macro-F1 0.649 [0.583, 0.719]**; non-residential F1 0.50 |
| files | `outputs/lu20/maps_final/` (not in git; regenerated by `scripts/lu20/`) |

**Rule learned in September:** never take the difference of two class maps as "change". About 19% of all
pixels change class in 3 years, mostly trees ↔ open with the seasons and residential ↔ non-residential
uncertainty. Every outcome below therefore uses either a second source or persistence over years.

### 3.2 Data sources

| data | resolution / unit | years | used for | runs |
|---|---|---|---|---|
| Our final land-use maps | 20 m | 2017–2023 | at risk, outcome, land use within 1 km, mix, distance to the dense city | C–H |
| Google Open Buildings 2.5D Temporal | 0.5 m → 10/20 m cover | yearly 2016–2023 | outcome (strict rule), at-risk filter (< 5% cover) | B, C–H |
| Dynamic World | 10 m → 300 m | 2017, 2024 | outcome of the 300 m models | A |
| OpenStreetMap, Geofabrik snapshots 1 Jan 2018 / 1 Jan 2021 | vector | 2017, 2020 | major roads, road km in 4 × 4 km, restricted land, lakes | C–H |
| OSM history (Overpass) | vector | 2017, 2020, 2023 | roads at the start year | B |
| Metro stations with opening dates | points | 2017–2023 | distance to the nearest *open* station | A–H |
| ORR interchanges | points | | distance to the nearest interchange | A–H |
| Copernicus GLO-30 DEM | 30 m | | slope, relief, elevation | C–H |
| VIIRS night lights | ~500 m | start year | night lights within 1 km | B–H |
| WorldPop | 100 m | start year | people per km² | C–H |
| Form 20, 2018 assembly election (CEO Telangana) | booth | 2018 | votes polled per booth, by OCR (1,477 of 1,479 booths) | C |
| ECI polling-station coordinates (April 2017 scrape) | points | 2017 | booth locations; district of each cell | C–H |
| 6th Economic Census 2013–14 microdata (MoSPI) | establishment | 2013 | jobs within ~5 km, kind of jobs | C4–H |
| Census 2011 PCA and SECC 2011–12, via SHRUG 2.2 | village / town | 2011 | density, SC/ST, literacy, farm workers, vehicles | C4–H |
| NRSC SIS-DP 1:10K land use (Bhuvan WMS) | vector → 10 m | 2016–19 | robustness of the start state | B |
| TGSRTC bus stops (WRI India Transport Analytics Hub, shift-transport.org) | 5,177 points | current | bus factors | G |
| HMDA Metropolitan Development Plan 2031 (OpenCity) | 30 scanned sheets → 20 m | approved 2013 | zone dummies | H |

---

## 4. The final method, step by step

This is the method of runs C–H. The 300 m and 10 m models (A, B) are in §16–17, the trial (C) in §18.

### 4.1 Unit and periods
- **Unit:** a 20 m cell of the final maps. There is no parcel map of Hyderabad, so the cell plays the role
  of Florida's parcel.
- **Periods:** 2017 → 2020 and 2020 → 2023, pooled with a period dummy, and also fitted separately.

### 4.2 Who is "at risk" (the vacant parcels)
A cell is at risk in a period if, at the start, the map says **trees or open** and Open Buildings cover is
**below 5%**. In HMDA that is 16.3 M cells in 2017 and 16.0 M in 2020 (of 19.1 M).

### 4.3 The outcome: three rules

| rule | change = 1 | change = 0 | 2017–20 | 2020–23 | runs |
|---|---|---|---|---|---|
| **strict** (`OUTCOME=both`) | map built at the end **and** Open Buildings cover ≥ 20% **and** 3 × 3 cover gain ≥ 0.10 | still undeveloped by both sources (cover < 5%, gain < 0.02); disagreements dropped | 0.23% | 0.22% | C, D, F1, G1, H1 |
| **persistence** (`OUTCOME=persist`) | map built in **both** the year before the end and the end year (e.g. 2019 and 2020) | map trees / open in both years and no strict Open Buildings gain | 1.44% | 1.40% | E1, F2, G2, H2 |
| **middle** (not coded yet) | persistence **and** an Open Buildings 3 × 3 gain ≥ 0.05 | as persistence | ≈ 0.53% | ≈ 0.47% | – |

Rates are shares of at-risk open land, per 3-year period, for all of HMDA. In the trial area the strict rule
gives 0.35–0.37% (8,048 and 8,363 cells).

### 4.4 Choice-based sampling
- Change is rare, so a random sample would hold too few changes. We **over-sample changes**
  (outcome-stratified sampling, standard in discrete choice).
- **Spacing:** at most one cell per 200 m block per outcome, so one layout doesn't count many times.
- **Trial:** per period all spaced changers (~1,500) plus non-changers, to make 10,000 cells per period
  → 20,000 cells.
- **HMDA:** 60,000 cells per period, every changing block kept → 120,000 cells.

### 4.5 The binary logit

Each cell *i* has a latent utility for development:

```
U_i = b0 + b1·x1_i + ... + bK·xK_i + e_i

P(change_i = 1) = 1 / (1 + exp(-(b0 + b1·x1_i + ... + bK·xK_i)))
```

with the error e_i logistic. Estimated by maximum likelihood (statsmodels). Reading the coefficients:

| kind of factor | odds ratio |
|---|---|
| yes/no dummy | exp(β) |
| ln(km + 0.1) distance | twice as far: 2^β; half as far: 2^(−β) |
| a % share | +10 points: exp(10·β) |
| a 0–1 index (land-use mix) | +0.1: exp(0.1·β) |

Distances are logged so that every doubling has the same effect. A negative distance coefficient means
**closer → more development**.

### 4.6 Constant correction (King & Zeng 2001)
With outcome-stratified sampling the slopes are consistent (Manski & Lerman 1977); only the constant is
biased. It is corrected with

```
b0_corrected = b0_fitted - ln[ ((1 - τ) / τ) × (ȳ / (1 - ȳ)) ]
```

where τ is the true change rate and ȳ the sample rate (trial τ = 0.405%, ȳ = 15.4%, a shift of about 3.8;
HMDA strict τ = 0.242%). Predicted probabilities are then on the real scale.

τ here is changes ÷ (changes + cells that both sources call unchanged): the cells where the two sources
disagree are left out of the denominator, as they are left out of the sample (`02_trial_data.py`). That is
why τ is a little above the population rates quoted elsewhere (0.23% / 0.22%), which divide by all at-risk
cells.

### 4.7 Clustered standard errors
Neighbouring cells share unmeasured things (one developer, one village's land market): Moran's I of the
residuals is 0.15–0.20. All t-values and Wald tests use **cluster-robust (sandwich) errors by 4 km tile**.

### 4.8 Specification search (Table 18 style)
- Start from **all candidates**: 24 in the first trial table (C3), 36 once jobs and census were added (C4),
  35 in HMDA (booth votes exist only for the trial).
- **Backward elimination:** drop the least significant factor, refit, repeat until every remaining factor
  has **|t| ≥ 1.96**. Area dummies (constituency or district) and the period dummy are always kept.
- Report pooled estimates plus each period's estimates, and a robust Wald test that all eliminated factors
  are jointly zero.

### 4.9 Tests used

| test | question | runs |
|---|---|---|
| z-test per coefficient (cluster-robust) | does the factor matter, others fixed? | all |
| robust Wald χ² per group of factors | does the mechanism matter as a whole? safer under collinearity | C2, D4, G, H |
| ρ² (McFadden) and adjusted ρ² | overall fit against a constant-only model | all |
| AUC, 5-fold cross-validated by 4 km tile | how well it ranks changed above unchanged cells on unseen areas | all |
| average marginal effect | change in 3-year probability in percentage points | C2 |
| variance inflation factors | can single coefficients be trusted? | C2, D4 |
| Chow test (slopes × period) | same effects in both periods? | C2, D4 |
| temporal transfer | does a 2017–20 model predict 2020–23? | C2, D4, E1 |
| Moran's I of residuals | spatial pattern left over? | C2, D4, E1 |
| calibration by decile | are probabilities right in absolute terms? | C2, D4 |
| causal-direction checks | roads added *during* the period, contagion, GO 111 × post-2022 | C2, D4, E1 |
| nested and drop-one added fit | how much each group adds beyond the rest | F |
| subregion refits | do findings hold everywhere? | D3, E1 |

### 4.10 Timing rule
Every factor is measured **at or before the start** of the period. Change over the *same* period is not
allowed as a factor (reverse causality: new houses bring new roads and people). Roads and metro stations
are taken as they existed at the start year. **One exception:** lakes ≥ 2 ha (lake edge, distance to a lake)
are taken from the **2023** map, the fullest water extent (`04_more_factors.py`), for both periods.

---

## 5. Factor dictionary

| group | factor (variable) | how it is measured | source | trial | HMDA |
|---|---|---|---|---|---|
| land at the start | tree cover (vs open) | final map class at t₀ | maps | ✔ | ✔ |
| neighbourhood | residential / non-res / water / tree share within 1 km | % of the 1 km window at t₀ (base open) | maps | ✔ | ✔ |
| | land-use mix | entropy of the 5 class shares s_k in 1 km: −Σ s_k·ln(s_k) / ln(5), from 0 (one class) to 1 (all equal) | maps | ✔ | ✔ |
| | distance to the dense city | ln km to the nearest cell with 1 km built share ≥ 40% | maps | ✔ | ✔ |
| | night lights | ln VIIRS within 1 km | VIIRS | ✔ | ✔ |
| access | airport, HITEC City / Financial District, old CBD (Abids), nearest ORR interchange, nearest open metro station, nearest major road | ln(km + 0.1); network as at t₀ | OSM, metro dates | ✔ | ✔ |
| | road mileage | km of OSM road in the 4 km × 4 km window at t₀ (also split major / minor) | Geofabrik | ✔ | ✔ |
| supply constraints | slope, relief (st. dev. of elevation within 150 m), elevation | | DEM | ✔ | ✔ |
| | within 100 m of a lake ≥ 2 ha; ln distance to a lake | | OSM / water | ✔ | ✔ |
| | restricted land | inside OSM military, forest, protected or airport land | OSM | ✔ | ✔ |
| | GO 111 zone | within 10 km of Osman Sagar / Himayat Sagar (stand-in for the 84 notified villages) | | ✔ | ✔ |
| people | booth votes per km² | 2018 votes polled, Gaussian kernel σ = 1 km | Form 20 | ✔ | – |
| | WorldPop per km² | 1.1 km window | WorldPop | ✔ | ✔ |
| jobs (EC 2013) | workers within ~5 km | village workers spread over its area, kernel σ = 2.5 km | EC6 | ✔ | ✔ |
| | kind of jobs | % IT, % manufacturing, % in establishments with 100+ workers, within ~5 km | EC6 | ✔ | ✔ |
| | village job density | workers per km² | EC6 | ✔ | ✔ |
| village (Census 2011, SECC) | population density, SC/ST %, literacy, % farm workers, % households with a two/three-wheeler, % with a car, inside GHMC | SHRUG village / town | Census, SECC | ✔ | ✔ |
| design | constituency (trial) / old district (HMDA), period | always kept | | ✔ | ✔ |
| added later | bus stops: ln km to nearest, stops within 1 km (/10) | current stops | WRI hub | – | G |
| | master-plan zone (8 dummies, base conservation) | MDP 2031 sheets | HMDA | – | H |

**Districts (HMDA):** taken from the nearest 2017 polling station; pre-2016 districts (Rangareddy base,
Medak, Nalgonda, Mahabubnagar, Hyderabad).

---

## 6. Results on all of HMDA, strict change rule (Phase D, 11 Nov)

Prof.'s instruction (11 Nov, paraphrased): extend to larger areas, see how consistent the findings are, and
retest every variable; don't draw conclusions for the whole region from a small one.

### 6.1 Inputs
| | trial | all of HMDA |
|---|---|---|
| region | 1,164 km² | 7,649 km² (19.1 M cells) |
| open land at the start | 2.3 M cells | 16.3 M (2017), 16.0 M (2020) |
| strict changes in the population | 0.35–0.37% per 3 years | 37,240 (0.23%), 34,952 (0.22%) |
| disagreements dropped | 10–13% | 3.3%, 6.2% |
| sample | 19,813 (3,071 changes) | **120,000 (12,314 changes)** |
| votes | yes | not available outside the trial |
| area dummies | constituency | old district |
| candidates | 36 | 35, all retested from scratch |

One fix was needed: outside the HMDA boundary the Open Buildings grid is NaN and a moving window spreads the
NaN; the outside is set to 0 cover. The trial was rerun and is unchanged.

### 6.2 D1: main HMDA table, strict rule (`hmda/table18_census/`)

| Variable | Estimate | t | 2017–20 | t | 2020–23 | t |
|---|---|---|---|---|---|---|
| Constant | −4.843 | −9.57 | −4.910 | −8.46 | −4.780 | −8.24 |
| Tree cover (vs open) | −1.099 | −16.19 | −0.941 | −10.83 | −1.263 | −13.70 |
| Residential within 1 km (%) | −0.012 | −5.12 | −0.015 | −4.37 | −0.009 | −3.02 |
| Non-residential within 1 km (%) | −0.006 | −2.67 | −0.007 | −2.32 | −0.006 | −2.09 |
| Water within 1 km (%) | −0.047 | −4.23 | −0.057 | −4.42 | −0.036 | −2.30 |
| Trees within 1 km (%) | −0.045 | −11.35 | −0.046 | −8.96 | −0.044 | −9.30 |
| Land-use mix (0–1) | 3.353 | 15.48 | 3.810 | 12.34 | 2.944 | 11.68 |
| Ln km to the dense city | −0.231 | −6.01 | −0.219 | −4.47 | −0.238 | −4.92 |
| Ln km to the old CBD | −0.655 | −5.49 | −0.561 | −4.02 | −0.737 | −5.48 |
| Ln km to nearest ORR interchange | −0.237 | −5.61 | −0.269 | −5.54 | −0.214 | −4.40 |
| Ln km to nearest major road | −0.170 | −5.64 | −0.151 | −4.23 | −0.192 | −5.26 |
| Slope (°) | −0.055 | −5.49 | −0.050 | −3.71 | −0.059 | −4.28 |
| Relief within 150 m (m) | −0.062 | −3.75 | −0.071 | −3.34 | −0.054 | −2.41 |
| Elevation (100 m) | 0.162 | 2.18 | 0.098 | 1.10 | 0.215 | 2.59 |
| Ln km to a lake ≥ 2 ha | 0.095 | 2.49 | 0.066 | 1.32 | 0.120 | 2.75 |
| Within 100 m of a lake | −1.091 | −10.76 | −1.288 | −9.26 | −0.911 | −7.45 |
| Military / forest / protected / airport land | −1.025 | −3.90 | −1.108 | −3.48 | −0.926 | −3.03 |
| IT services (% of jobs within ~5 km) | 0.015 | 2.90 | 0.023 | 3.84 | 0.006 | 1.03 |
| Manufacturing (% of jobs within ~5 km) | −0.006 | −2.48 | −0.006 | −2.15 | −0.006 | −2.13 |
| 100+ worker establishments (% of jobs) | 0.011 | 4.50 | 0.011 | 4.04 | 0.011 | 3.70 |
| Medak (vs Rangareddy) | 0.306 | 3.17 | 0.323 | 2.56 | 0.302 | 2.81 |
| Nalgonda | 0.126 | 0.71 | | | | |
| Mahabubnagar | 0.173 | 0.97 | | | | |
| Hyderabad | −0.740 | −3.66 | −0.440 | −2.04 | −1.056 | −4.47 |
| 2020–23 | −0.021 | −0.58 | | | | |

| | pooled | 2017–20 | 2020–23 |
|---|---|---|---|
| cells (changes) | 120,000 (12,314) | 60,000 (6,034) | 60,000 (6,280) |
| log-likelihood, constant only / converged | −39,695.4 / −30,326.0 | −19,579.6 / −14,674.6 | −20,113.0 / −15,583.8 |
| ρ² / adjusted | **0.236** / 0.235 | 0.251 / 0.249 | 0.225 / 0.224 |
| AUC, CV by tile | **0.841** | 0.847 | 0.837 |

Eliminated (jointly χ² 11.1 on 16 df, p = 0.80): village job density, workers within 5 km, WorldPop,
**HITEC (t 0.16)**, car ownership, metro, literacy, road mileage, GO 111, night lights, farm workers, village
density, SC/ST, two-wheelers, **airport (t −1.23)**, inside GHMC.

**Odds ratios (pooled, 95% interval):** tree cover 0.33 [0.29–0.38]; trees +10 points 0.64; water +10 points
0.62; mix +0.1 **1.40** [1.34–1.46]; dense city half as far 1.17; **old CBD half as far 1.57 [1.34–1.85]**;
**ORR half as far 1.18 [1.11–1.25]**; major road half as far 1.13; slope +1° 0.95; lake edge 0.34;
restricted 0.36; IT +10 points 1.16; manufacturing +10 points 0.94; big employers +10 points 1.12;
Hyderabad district 0.48.

### 6.3 Trial vs HMDA, same candidates and procedure
- **11 of the trial's 18 factors survive, all with the same sign:** tree cover, trees nearby, mix, dense
  city, major road, slope, relief, lake edge, restricted land, manufacturing share, big-employer share.
- **Dropped:** airport, HITEC / FD, road mileage, workers within 5 km, SC/ST, farm workers, two-wheelers.
- **New:** old CBD, ORR, res / non-res / water shares, elevation, lake distance, IT share.
- **Why the airport and HITEC dropped:** fitted on the trial ACs alone, the HMDA data keep them (t −6.0 and
  −2.9). The trial area *is* the south-west airport–HITEC corridor. Real geography, not a data problem.

### 6.4 D2: variants
Florida-style: ρ² 0.233, AUC 0.839 (CBD t −6.2, ORR t −6.4, HITEC eliminated at t 0.24, airport at −1.45).
No census: ρ² 0.233, AUC 0.839 (CBD t −7.2, ORR t −6.5).

### 6.5 D3: consistency across HMDA

| | HMDA | trial ACs | rest | CBD < 20 km | 20–35 km | ≥ 35 km |
|---|---|---|---|---|---|---|
| cells (changes) | 120,000 (12,314) | 18,777 (3,059) | 101,223 (9,255) | 17,882 (5,279) | 42,522 (4,829) | 59,596 (2,206) |
| ρ² / AUC (HMDA spec) | 0.236 / 0.841 | 0.232 / 0.829 | 0.231 / 0.840 | 0.131 / 0.732 | 0.168 / 0.792 | 0.173 / 0.812 |

- **Hold everywhere:** tree cover (t −5.3 to −16.2), trees nearby, land-use mix (4.3 to 16.6), lake edge,
  big-employer share, distance to the dense city; major road everywhere except inside 20 km; slope except
  beyond 35 km.
- **Depend on place:** airport and HITEC (south-west only); old CBD flips inside 20 km (inside the city,
  building happens at the edge); ORR fades beyond 35 km; IT share only outside the trial ACs.
- **Weakest inside 20 km of the CBD** (AUC 0.73): infill is harder to predict than fringe growth.

### 6.6 D4: tests on all of HMDA

| test | trial | HMDA |
|---|---|---|
| ρ² / AUC (25-factor model) | 0.225 / 0.818 | 0.235 / 0.839 |
| access group (8 factors) | χ² 77.7 | χ² 204.5 |
| neighbourhood group (7) | χ² 72.1 | χ² 512.6 |
| supply constraints (7) | χ² 121.7 | χ² 280.6 |
| people | p = 0.79 | WorldPop p = 0.35 |
| Moran's I | 0.155 / 0.146 | 0.197 / 0.188 |
| Chow | χ² 81.7 | χ² 77.0 on 28 df |
| temporal transfer AUC | 0.809 | **0.834** (own CV 0.836) |
| roads added during period | z 6.4 | z 7.9 |
| contagion | p 0.06 | z 5.8 (× 1.17 per SD) |
| GO 111 × post-2022 | p 0.57 | p 0.19 |

Calibration by decile (% per 3 years): predicted 0.012 … 0.555, 1.803 vs observed 0.011 … 0.653, 1.581: the
top decile is over-predicted by about 14%. VIF still high for the CBD (15–18) and metro (10–15).

---

## 7. Counting change: the strict rule undercounts; the persistence rule (Phase E, 11 Nov)

### 7.1 E0: the check
The strict rule says only **0.23% of open land per 3 years** (0.57% over 2017–23). Prof. expected far more
change, and the user challenged it. So every cell undeveloped in the 2017 map was followed through the
**yearly** final maps 2018–2023. Real building stays built; classifier noise flips back.

| finding | value |
|---|---|
| map built in 2020 (of undeveloped 2017 land) | 175 km², 2.67% |
| of those, still built in 2021, 2022 and 2023 | **80%** |
| built for the first time and every later year, per year (2018–2022) | 0.65%, 0.56%, 0.52%, 0.49%, 0.57% → **≈ 0.55% a year** |
| flicker (built in 2020, not in every later year) | 0.88% |
| map built share of HMDA | 13.4% (2017) → 16.6% (2023), about 40 km² a year |
| Open Buildings on persistent changes | only 25% reach 20% cover |

**Conclusion.** Open Buildings misses most new building at 20 m; the strict rule keeps only about **1 in 6–7
real changes** (0.23% against 1.4% per 3 years). The corrected rate is about **0.55% a year** for land built
for the first time that stays built in every later year; the persistence rule used below (built in both of
the last two years of the period) gives **1.4% per 3 years**.
**Florida for comparison:** Table 18 models the annual change of a vacant parcel's tax-roll use code; its
constant (−4.333) implies about **1% a year**, the same order. 10% of HMDA's open land changing in 3 years
isn't plausible: all built land is only 13–17% of HMDA.

### 7.2 E1: Table 18 under the persistence rule (`hmda_persist/table18_census/`)

| Variable | Estimate | t | 2017–20 | t | 2020–23 | t |
|---|---|---|---|---|---|---|
| Constant | −5.310 | −12.10 | −6.316 | −11.64 | −4.344 | −9.27 |
| Residential within 1 km (%) | 0.025 | 11.90 | 0.018 | 7.15 | 0.031 | 13.31 |
| Non-residential within 1 km (%) | 0.022 | 11.12 | 0.016 | 7.01 | 0.028 | 11.77 |
| Water within 1 km (%) | −0.058 | −8.55 | −0.054 | −7.31 | −0.061 | −6.89 |
| Trees within 1 km (%) | −0.044 | −13.32 | −0.044 | −11.99 | −0.043 | −10.67 |
| Land-use mix (0–1) | 5.089 | 25.56 | 5.314 | 23.82 | 4.856 | 20.52 |
| Ln km to the dense city | **+0.141** | 6.62 | 0.111 | 4.04 | 0.174 | 7.06 |
| Ln night lights within 1 km | **−4.055** | −8.08 | −4.498 | −6.68 | −3.745 | −7.22 |
| Ln km to airport | −0.122 | −2.47 | −0.136 | −2.51 | −0.110 | −2.01 |
| Ln km to old CBD | −0.552 | −4.35 | −0.473 | −3.14 | −0.581 | −4.37 |
| Ln km to ORR interchange | −0.111 | −3.85 | −0.103 | −3.10 | −0.125 | −3.59 |
| Ln km to major road | −0.168 | −9.79 | −0.152 | −7.98 | −0.185 | −9.07 |
| Road mileage in 4 × 4 km (10 km) | −0.030 | −5.16 | −0.029 | −3.88 | −0.029 | −4.73 |
| Slope (°) | **+0.085** | 11.05 | 0.094 | 9.47 | 0.076 | 8.02 |
| Relief within 150 m (m) | −0.094 | −9.80 | −0.095 | −7.37 | −0.092 | −7.67 |
| Ln km to a lake ≥ 2 ha | 0.047 | 2.08 | 0.049 | 1.75 | 0.043 | 1.67 |
| Within 100 m of a lake | −0.852 | −14.99 | −0.984 | −12.83 | −0.731 | −10.45 |
| Ln WorldPop per km² | 0.275 | 7.23 | 0.421 | 9.04 | 0.135 | 3.21 |
| 100+ worker establishments (% of jobs) | 0.004 | 3.27 | 0.004 | 2.41 | 0.005 | 3.19 |
| Medak / Nalgonda / Mahabubnagar / Hyderabad | 0.285 / 0.224 / 0.343 / −0.202 | 5.69 / 3.59 / 3.70 / −1.34 | | | | |
| 2020–23 | 0.154 | 6.87 | | | | |

ρ² **0.292** (0.298 / 0.286), AUC **0.849** (0.852 / 0.845); 120,000 cells, 54,598 changes. 87.5% of the
2017–20 changes are still built in 2023; 2.7% of the "unchanged" cells get built later. Eliminated (p = 0.29)
include **tree cover on the cell (t 1.63)**, HITEC, restricted land, workers within 5 km, metro.
Florida-style variant: ρ² 0.291, AUC 0.849.

**Odd signs:** steeper land built *more*; farther from the dense city built *more*; night lights strongly
negative; tree cover and restricted land no longer matter.

### 7.3 E2: where the odd signs come from
The final spec plus tree cover, fitted on (a) all persistence changes, (b) only those with an Open Buildings
3 × 3 gain ≥ 0.05 (20% of sampled changes), (c) only those without (80%), each against the same unchanged
cells.

| factor | all | with OB gain | without OB gain |
|---|---|---|---|
| tree cover on the cell | 0.058 (1.6) | **−0.885 (−14.3)** | **+0.184 (5.1)** |
| ln km to the dense city | 0.140 (6.6) | **−0.122 (−3.7)** | **+0.195 (9.2)** |
| slope | 0.084 (11.1) | 0.020 (1.7) | **0.095 (12.2)** |
| ln night lights | −4.03 | −1.30 | −4.59 |
| land-use mix | 5.09 | 4.05 | 5.18 |
| within 100 m of a lake | −0.85 | −0.96 | −0.81 |
| ln km to old CBD / ORR / major road | −0.55 / −0.11 / −0.17 | −0.51 / −0.19 / −0.15 | −0.49 / −0.08 / −0.16 |
| ρ² / AUC | 0.292 / 0.849 | 0.277 / 0.857 | 0.289 / 0.850 |

**The odd signs come entirely from map changes with no Open Buildings gain.** These cells are more often
trees at the start (18.6% vs 6.4%), on steeper ground (2.45° vs 2.00°), a little farther from the city, but
not rural: their mix, WorldPop and road density are like the supported changes. They are one of: plotted
layouts / cleared land (real change), tree-shaded houses, or rock read as built. **The eyeball check
decides** (§2).

**Factors that hold under every rule:** land-use mix; trees and water within 1 km; lake edge; old CBD, ORR
and major road; relief; big-employer share. Persistence tests: temporal transfer 0.840; Moran's I 0.138 /
0.128; subregion AUC 0.825 (trial ACs), 0.851 (rest), 0.68 (inside 20 km of the CBD).

---

## 8. How much does each group of factors add? (Phase F)

With 120,000 cells almost anything passes |t| ≥ 1.96, so t-values say little about importance. Nested
(groups added in order) and drop-one (each group left out of the final model) fits:

| model | strict ρ² | strict AUC | persistence ρ² | persistence AUC |
|---|---|---|---|---|
| period and district only | 0.025 | 0.595 | 0.029 | 0.597 |
| + distance to the dense city | 0.171 | **0.796** | 0.186 | **0.775** |
| + land use within 1 km (shares, mix) | 0.199 | 0.818 | 0.275 | 0.843 |
| + tree cover on the cell | 0.208 | 0.823 | | |
| + accessibility | 0.224 | 0.835 | 0.285 | 0.846 |
| + supply constraints | 0.233 | 0.840 | 0.290 | 0.849 |
| + jobs and census | 0.236 | 0.841 | 0.292 | 0.849 |

| drop-one (strict) | loss in ρ² / AUC |
|---|---|
| without distance to the dense city | 0.002 / 0.001 |
| without land use within 1 km | 0.015 / 0.012 |
| without tree cover | 0.009 / 0.004 |
| without accessibility | 0.012 / 0.010 |
| without supply constraints | 0.010 / 0.005 |
| without jobs and census | 0.003 / 0.001 |
| without dense-city distance **and** land use within 1 km | 0.043 / 0.028 |

**Honest reading.** Most of the prediction is "new building happens next to existing building" (distance
to the city and land use nearby, both from our own map). Accessibility, terrain and census add a little
(about 0.018 of AUC under the strict rule, 0.006 under persistence). That is why policy data such as zoning
(§10) matter: they are the factors that explain *why*, not only *where*.

---

## 9. Bus stops (Phase G)

**Input:** 5,177 current TGSRTC stops (WRI India Transport Analytics Hub). Median distance of a sampled cell
to a stop 1.12 km (strict sample), 0.87 km (persistence).

| added to the final spec (pooled, both factors together) | strict | persistence |
|---|---|---|
| ln km to nearest stop | −0.161 (t −3.75) → half as far **× 1.12** | −0.215 (t −8.16) → **× 1.16** |
| stops within 1 km (/10) | −0.488 (t −5.32) → +10 stops × 0.61 | −0.573 (t −7.89) → × 0.56 |
| ρ² gain / AUC gain | 0.0018 / +0.0009 | 0.0029 / +0.0007 |

Both factors survive backward elimination. Being near *a* stop helps; many stops within 1 km means an
already-built area with little open land left, so the count is negative. **Caveat:** these are today's
stops, so some followed development; the 2020–23 period is the fairer test. **Verdict:** small but usable as
a transport factor.

---

## 10. HMDA Master Plan 2031 zoning (Phase H, 11–12 Nov)

### 10.1 Making the layer (`scripts/masterplan/`)
- **Source:** 30 scanned district sheets, "Proposed land use zoning and road network", HMDA Metropolitan
  Development Plan 2031 (approved by Government order in 2013, so **before both periods**), from OpenCity.
  1:25,000, mostly 200 dpi (3.175 m per pixel), no coordinate ticks.
- **Georeferencing:** first fit by matching each sheet's zoned area to the Census 2011 mandal outline
  (SHRUG, IoU); then the real fit by chamfer-matching the red roads and HMDA boundary on the sheet to OSM
  roads (1 Jan 2021). All 30 sheets fit, with 34–75% of red pixels within 40 m of an OSM road, rotation
  under 0.05°.
- **Classification:** nearest reference colour (legend swatches plus map samples; roads, boundaries and
  labels ignored), majority vote in ~200 m windows, clipped to each sheet's own zoned area, resampled to the
  20 m grid. One low-resolution sheet (Ibrahimpatnam_Manchal, 8.82 m/px) calibrated on its own legend.
- **Mosaic:** where sheets overlap, the one with more colour votes wins. **Coverage 74.2% of HMDA**; the
  erstwhile HUDA core is not in these sheets.

| zone (code) | km² | share of HMDA |
|---|---|---|
| conservation, agriculture (7) | 2,372 | 31.0% |
| residential (1) | 949 | 12.4% |
| protected green (8) | 553 | 7.2% |
| peri-urban (2) | 417 | 5.5% |
| water bodies (10) | 348 | 4.5% |
| GO 111 bio-conservation (9) | 326 | 4.3% |
| multiple use, incl. ORR growth corridor (6) | 280 | 3.7% |
| manufacturing (4) | 224 | 2.9% |
| public / semi-public (5) | 93 | 1.2% |
| special reservations (11), commercial (3), settlements (12) | 66, 41, 7 | 0.9%, 0.5%, 0.1% |
| not covered (0) | 1,973 | 25.8% |

### 10.2 Raw development rates by zone (% of open land per 3 years)

| zone | strict 2017–20 | strict 2020–23 | persistence 2017–20 | persistence 2020–23 |
|---|---|---|---|---|
| commercial / multiple use | 0.57% | 0.63% | 2.59% | 2.76% |
| manufacturing | 0.38% | 0.35% | 2.13% | 1.91% |
| residential | 0.26% | 0.30% | 1.83% | 1.92% |
| public / semi-public | 0.23% | 0.21% | 1.73% | 1.61% |
| GO 111 | 0.21% | 0.30% | 1.11% | 1.49% |
| peri-urban | 0.11% | 0.12% | 0.84% | 0.87% |
| conservation (base) | 0.06% | 0.08% | 0.54% | 0.60% |
| protected green / water / special | 0.05% | 0.06% | 0.50% | 0.53% |
| not covered (mostly the core) | 0.55% | 0.45% | 3.07% | 2.90% |

### 10.3 Zone dummies added to the final specification (odds vs conservation, 95% interval)

| zone | strict | persistence |
|---|---|---|
| manufacturing | **2.99** [2.32, 3.86] | **1.80** [1.49, 2.17] |
| residential | **1.76** [1.45, 2.15] | **1.44** [1.30, 1.58] |
| public / semi-public | 1.77 [1.33, 2.35] | 1.36 [1.14, 1.62] |
| GO 111 bio-conservation | 1.69 [1.33, 2.13] | 1.31 [1.13, 1.52] |
| commercial / multiple use | 1.50 [1.18, 1.90] | 1.24 [1.07, 1.42] |
| not covered | 1.49 [1.20, 1.83] | 1.16 [1.04, 1.29] |
| peri-urban | 1.13 (ns) | 0.98 (ns) |
| protected green / water / special | **0.67** [0.54, 0.83] | **0.71** [0.63, 0.80] |
| zones jointly (robust Wald, 8 df) | χ² 184.8, p ≈ 1e-35 | χ² 172.9, p ≈ 3e-33 |
| ρ² gain / AUC gain | 0.0077 / +0.0038 | 0.0042 / +0.0012 |
| backward elimination with zones | 7 of 8 kept; ρ² 0.244, AUC 0.845 | 7 of 8 kept; ρ² 0.297, AUC 0.850 |

Per period the pattern holds (e.g. strict residential 1.92 then 1.64; manufacturing 3.57 then 2.56).

**Reading it.**
- **Zoning matters, in the planned direction:** land zoned for residential, manufacturing or public use is
  built much more than agricultural conservation land; protected land much less. It is the first factor
  that is about *policy*, and it holds in both periods and under both rules.
- **Added fit is small** because planners zoned residential land around existing towns, which the
  neighbourhood factors already capture.
- **GO 111 gets built more than ordinary farmland.** The lake-protection zone lies close to the city, and
  building went ahead despite the restrictions (the order was repealed in 2022). Worth one careful sentence
  in the paper.

---

## 11. Comparison with Florida's Table 18

| Florida (UCF/FDOT, vacant parcels, annual) | Hyderabad (ours, open 20 m cells, 3-year periods) |
|---|---|
| change = tax-roll land-use code changes | change = built in our map (strict: + Open Buildings; persistence: built two years running) |
| ≈ 1% of vacant parcels a year (from the constant −4.333) | 0.23% (strict) or 1.4% (persistence) per 3 years, i.e. about 0.08% or 0.5% a year |
| % Hispanic, % zero-vehicle households | SC/ST share (trial), two-wheeler households (trial); dropped HMDA-wide |
| job density (+) | job mass + only without land-use mix; HMDA keeps the *kind* of jobs: big employers +, IT +, manufacturing − |
| ln parcel area | none (all cells are 400 m²; no parcel map) |
| block-group land use % | land use within 1 km %, land-use mix, distance to the dense city |
| % flood zone A | lake edge, distance to lakes, slope, relief, restricted land |
| – | accessibility: old CBD, ORR interchanges, major roads (HMDA-wide); airport, HITEC (south-west) |
| – (zoning not in Table 18) | Master Plan 2031 zones |
| t-stats 2.8–53 | t-stats 2–25 (cluster-robust) |

---

## 12. Limitations

1. **The change rule** is not settled (§2.2).
2. **The maps** have hand-label macro-F1 0.649 and non-residential F1 0.50, so residential vs non-res
   *type* of change is not modelled yet.
3. **No parcels:** 20 m cells, so no parcel size or value (Florida's ln parcel area).
4. **Collinearity:** CBD and metro distance still have VIF 10–18 across HMDA; read the group tests.
5. **Residual clustering:** Moran's I 0.13–0.20 remains; handled by tile-clustered errors.
6. **GO 111** is a 10 km stand-in, not the 84 notified villages.
7. **Census inside GHMC:** two polygons in SHRUG, so city-wide averages there.
8. **Districts** come from the nearest 2017 polling station and are approximate near borders.
9. **Bus stops** are today's stops; **zoning** covers 74% of HMDA (not the core) and is read from scans.
10. **Straight-line distances**, not network travel time.
11. **Lakes from the 2023 map** in both periods (§4.10): a lake that shrank or was filled before 2023
    is missed. Lakes change slowly, so the effect is likely small, but it breaks the timing rule.
12. **The first change-rate claim** (about 0.1% a year, "most map change is noise") was wrong and was
    corrected on 11 Nov (§7).

---

## 13. Next steps and data to request

1. **Eyeball check** → choose the rule → code the middle rule if needed → rerun → final Table 18 with
   zoning for Prof.
2. **Factors beyond "near existing development":** network travel time to jobs, flood exposure, ward-level
   census, land values.
3. **Data to request through Prof.:**
   - the master plan as GIS (ours is read from scans);
   - **HMDA / TS-bPASS layout and building approvals with locations**, the closest thing to Florida's
     tax-roll data, which would settle the change question for good;
   - the traffic-zone data of the 2013 Comprehensive Transportation Study.
4. **Booth votes HMDA-wide:** about 31 more constituencies of 2018 Form 20, plus the 2018 polling-station
   list with names.
5. **GO 111:** the 84 notified villages, for a before / after test of the 2022 repeal.
6. **Further Florida steps:** the new land-use type after change (residential vs non-residential).

---

# Part 2: how we got here

---

## 14. Timeline

| period | what happened | outcome |
|---|---|---|
| 2–16 Sep | 300 m grid, Dynamic World conversion, first logits; metro tests | ORR and highways robust; metro not identified |
| 20 Sep – 31 Oct | land-use classifier built and tested (10 m, then 20 m with year-dated labels) | final maps 2017–2023, hand-label macro-F1 0.649 |
| 2–3 Oct | 10 m transition models (binary, MNL, context, two periods, latent segmentation) | ORR effect robust; employment-core / residential-ring pattern |
| ~2 Nov | meeting with Prof.: build the Table 18 analogue, about 15–20k pixels, test voter data, airport, ORR, metro, road length in 4 × 4 km, Indian factors; years 2017, 2020, 2023 | plan in `docs/archive/CHANGE_MODEL_PLAN_2026-11-02.md` |
| 2–8 Nov | trial on 3 constituencies: booth votes, full model and tests, Table 18 with census | final trial table: ρ² 0.222, AUC 0.821 |
| 11 Nov | Prof.: "extend to larger areas … retest all variables … small region testing should only be an initial step" | HMDA-wide run |
| 11 Nov | change rate found too low; persistence rule; added fit; bus stops | outcome rule reopened |
| 11–12 Nov | Master Plan 2031 digitised from 30 scanned sheets and tested | first real policy factor |
| next | eyeball check → final change rule → one rerun → final Table 18 with zoning | |

---

## 15. Run register: inputs and results of every run

| run | date | region | unit | sample (changes) | outcome | method | fit | results file |
|---|---|---|---|---|---|---|---|---|
| A1 | 16 Sep | HMDA | 300 m cell | 71,607 (8.76%) | Dynamic World built 2017 → 2024 | binary logit, MNL, latent classes, LightGBM | McFadden R² 0.204, AUC 0.823 | `OVERNIGHT_RESULTS.md`, `outputs/overnight/m2_choice_models/` (local only, not in the repository) |
| A2–A4 | 16 Sep | HMDA | 300 m | same | metro specification path, event study, densification | logit, stacked DiD | metro effect not identified | `outputs/overnight/m3…m6/` (not in the repository) |
| B1 | 2–3 Oct | HMDA | 10 m pixel | 299,453 at risk (0.70%) | Open Buildings: undeveloped 2017 → developed 2023, typed res / non-res | binary logit, MNL, LightGBM + SHAP, context classes | R² 0.17, AUC 0.86 (LightGBM 0.89) | `docs/archive/CHOICE_MODEL_RESULTS_10m_Oct.md`, `outputs/lu/choice_2017_2023/` |
| B2 | 3 Oct | HMDA | 10 m | same pixels, 3 dates | 2017→20 and 2020→23 separately | same, per period | effects stable | `outputs/lu/choice_periods/` |
| B3 | 3 Oct | HMDA | 10 m | 2017→23 | developed | latent segmentation logit, K = 1–3 | BIC picks K = 3 | `outputs/lu/choice_latent/` |
| C1 | 5 Nov | 3 ACs, 1,164 km² | 20 m cell | 20,000 (3,071) | **strict**: map built + Open Buildings ≥ 20% | binary logit, base ± votes / WorldPop | ρ² 0.192, AUC 0.80 | `docs/archive/trial/TRIAL_RESULTS.md`, `outputs/change/trial/` |
| C2 | 5 Nov | 3 ACs | 20 m | 19,813 (3,071) | strict | full 25-factor logit + 9 tests | ρ² 0.23, AUC 0.818 | `docs/archive/trial/FULL_MODEL_RESULTS.md`, `outputs/change/trial/full/` |
| C3 | 5 Nov | 3 ACs | 20 m | 19,813 (3,071) | strict | Table 18: backward elimination, no census | ρ² 0.222, AUC 0.824 | `docs/archive/trial/TABLE18_RESULTS.md`, `outputs/change/trial/table18/` |
| C4 | 6 Nov | 3 ACs | 20 m | 19,813 (3,071) | strict | Table 18 + jobs and census | ρ² 0.229, AUC 0.825 | `docs/archive/trial/TABLE18_CENSUS.md`, `outputs/change/trial/table18_census/` |
| C5 | 6 Nov | 3 ACs | 20 m | 19,813 (3,071) | strict | Table 18, Florida-style (**final trial table**) | ρ² 0.222, AUC 0.821 | same file, `trial/table18_florida/` |
| D1 | 11 Nov | **all of HMDA**, 7,649 km² | 20 m | 120,000 (12,314) | strict | Table 18 + census, all 35 candidates retested (**main HMDA table, strict**) | ρ² 0.236, AUC 0.841 | `docs/archive/HMDA_RESULTS.md`, `outputs/change/hmda/table18_census/` |
| D2 | 11 Nov | HMDA | 20 m | 120,000 | strict | Florida-style and no-census variants | ρ² 0.233, AUC 0.839 | `hmda/table18_florida/`, `hmda/table18/` |
| D3 | 11 Nov | 5 subregions of HMDA | 20 m | 17,882–101,223 | strict | final spec refitted + own elimination | AUC 0.73–0.84 | `hmda/consistency/CONSISTENCY.md` |
| D4 | 11 Nov | HMDA | 20 m | 120,000 | strict | full 25-factor model + tests | ρ² 0.235, AUC 0.839 | `hmda/full/` |
| E0 | 11 Nov | HMDA | 20 m, every cell | all open land | yearly maps 2017–2023 | persistence check (no model) | 80% of new built stays built | §7.1 |
| E1 | 11 Nov | HMDA | 20 m | 120,000 (54,598) | **persistence**: map built in both last 2 years | Table 18 + census, all candidates | ρ² 0.292, AUC 0.849 | `docs/archive/PERSIST_RESULTS.md`, `outputs/change/hmda_persist/table18_census/` |
| E2 | 11 Nov | HMDA | 20 m | 120,000 | persistence, split by Open Buildings gain | same spec on two subsets | odd signs located | `docs/archive/PERSIST_RESULTS.md` §3 |
| F1–F2 | 11 Nov | HMDA | 20 m | 120,000 | strict / persistence | nested and drop-one added fit | distance to city alone: AUC 0.60 → 0.80 | `hmda*/added_value/ADDED_VALUE.md` |
| G1–G2 | 11 Nov | HMDA | 20 m | 120,000 | strict / persistence | + bus-stop factors | AUC +0.001 | `hmda*/bus_stops/BUS_STOPS.md` |
| H1–H2 | 12 Nov | HMDA | 20 m | 120,000 | strict / persistence | + master-plan zone dummies | χ² 185 / 173 on 8 df; AUC +0.004 / +0.001 | `hmda*/zoning/ZONING.md` |

Short paths such as `hmda/full/` or `trial/table18/` are under `outputs/change/`.

**Sample data for every change-model run** (enough to refit all of them, in the repo):
`data/processed/change/trial_cells_{full,census}.parquet`, `hmda_cells_{full,census}.parquet`,
`hmda_persist_cells_{full,census}.parquet`.

---

## 16. Phase A (Sep): 300 m conversion models

**Inputs.** 300 m grid of HMDA (84,984 cells); 71,607 developable cells (Dynamic World built < 0.5 in 2017);
outcome = Dynamic World built by 2024 (base rate 8.76%). Predictors: distances to CBD, HITEC, metro,
highway, ORR interchange, rail; job accessibility; land-use entropy 2015; built land within 1 km; slope.

**A1. Binary logit and friends.**
- McFadden R² 0.204, spatial-block CV AUC **0.823** (LightGBM 0.842).
- Standardised coefficients: ORR interchange **−0.569** (p ≈ 7e-69), highway **−0.401**, built land within
  1 km +0.738, metro −0.025 (p = 0.64).
- Residual Moran's I 0.172; inside vs outside the ORR behave differently (LR test p ≈ 0); latent classes:
  BIC picks K = 3.

**A2. Does the metro coefficient survive controls?** No.

| specification | metro (std.) | p |
|---|---|---|
| metro only | −0.974 | 0 |
| + other transport | −0.554 | ~0 |
| + centrality | −0.238 | 1e-08 |
| + job access | +0.200 | 0.0001 |
| + physical controls | +0.143 | 0.006 |
| + built land nearby (full) | **−0.025** | **0.64** |

**A3. Metro opening event study** (stacked difference-in-differences, 0–2 km bands vs the 2–5 km ring, 814
units, 66 clusters): 0–0.5 km −0.046 (z −2.2), others not significant. **A4. Densification near metro**
(GHS-BUILT-V volume 2015 → 2025): no station effect.

**Verdict.** ORR access and highways are robust; the metro effect is an artefact of where the metro was
built. Superseded by the 10 m models, because Dynamic World at 300 m blurs real building with noise.

---

## 17. Phase B (Oct): 10 m transition models

Code: `scripts/lu/21_transition_data.py`, `22_choice_models.py`, `23_sisdp_raster.py`, `24_period_compare.py`,
`25_latent_segmentation.py`. Write-up: `docs/archive/CHOICE_MODEL_RESULTS_10m_Oct.md`.

### 17.1 Inputs
| item | definition |
|---|---|
| unit | 333,600 random 10 m pixels (600 per 4 km tile); **299,453 undeveloped in 2017** |
| undeveloped 2017 | Open Buildings cover < 5% in the pixel and < 10% within 70 m, not water |
| developed by 2023 | cover ≥ 20% in the pixel and ≥ 10% within 70 m (checks at 10% and 30%) |
| residential vs non-res | 53-feature physical classifier on 2023 inputs; non-res if P(nr) / (P(r) + P(nr)) > 0.5 |
| proximity (2017) | employment centre (nearer of HITEC / FD), old CBD, airport, ORR interchange, major road (2017 OSM), metro open by 2017 |
| controls (2017) | building cover within 150 m and 610 m, NDVI within 150 m, night lights within 610 m, forest start |

**Outcome:** 99.3% stayed undeveloped, **0.37% became residential** (1,108), **0.33% non-residential** (985).

### 17.2 Observed rates by distance (no model)

| distance to HITEC / FD | became residential | became non-residential |
|---|---|---|
| 0–2.5 km | 1.9% | **4.2%** |
| 2.5–5 km | 2.3% | 1.8% |
| 5–10 km | **2.4–2.7%** | 1.0–1.6% |
| 10–20 km | 1.1–1.6% | 0.8% |
| 20–30 km | 0.5–0.8% | 0.4–0.6% |
| 30–50 km | 0.1% | 0.1–0.2% |

Non-residential development is concentrated at the employment core; residential peaks in a 5–10 km ring.

### 17.3 Multinomial logit (standardised ln distance; negative = closer → more likely; metro dropped for VIF)

| proximity | residential vs none | non-residential vs none |
|---|---|---|
| HITEC City / FD | −0.13 (ns) | **−0.10 \*** |
| old CBD | **−0.58 \*\*\*** | −0.04 (ns) |
| ORR interchange | **−0.42 \*\*\*** | **−0.34 \*\*\*** |
| major road (2017) | +0.07 (ns) | **−0.19 \*\*\*** |
| airport | +0.27 \*\* | −0.03 (ns) |

| model | McFadden R² | CV AUC |
|---|---|---|
| binary logit | 0.17 | 0.86 |
| MNL | 0.16 | – |
| LightGBM | – | 0.89 |

**Robustness of the ORR coefficient (binary):** main −0.37; ≥ 10% threshold −0.32; ≥ 30% −0.39; SIS-DP
start state −0.33; 2023 roads −0.36.

### 17.4 Context classes, two periods, latent segmentation
- **Context:** in the middle ring (10–25 km) ORR interchanges drive non-res conversion (−0.20 \*\*); in the
  periphery (> 25 km) major roads do (−0.23 \*\*\*).
- **Two periods (B2):** the pace is steady (0.33% and 0.32% per 3 years). ORR → developed −0.34 / −0.38,
  old CBD → residential −0.53 / −0.41: **stable**. HITEC → residential fades (−0.16 \* → −0.04 ns).
- **Latent segmentation (B3), BIC picks 3 segments:** "dormant" land (93%, almost never develops), "infill"
  (5%, dense inner land, *off* major roads), "growth corridor" (3%, pulled by HITEC −0.56 \*\*\*, ORR −0.71
  \*\*\*, major roads, and lit at night).

**Verdict.** The proximity story is real and stable, but the outcome relied on Open Buildings at 10 m and
the res / non-res split relied on the 10 m classifier, whose non-res F1 was ≈ 0.4 (the 20 m maps used from Phase C reach 0.50). Superseded by the Table 18 analogue on
the final 20 m maps (Phase C onwards), which Prof. asked for in early November.

---

## 18. Phase C (2–8 Nov): change model, 3-constituency trial

**Region:** Maheshwaram, Rajendranagar and Serilingampally (ACs 50–52), 1,164 km² (700 + 344 + 120), cells
whose nearest 2017 polling station is in those ACs. Chosen so that booth-wise voter data could be tested.
**Outcome:** strict rule (0.35–0.37% per 3 years). **Sample:** 20,000 cells (19,813 after the grid edge),
3,071 changes (1,521 + 1,550).

### 18.1 C1: booth votes as population (5 Nov)

**How votes were obtained:** booth-wise electoral rolls sit behind a captcha (not bypassed), so we read the
**votes polled per booth** from the 2018 Form 20 result sheets by OCR: 1,479 booths, 759k votes. Booths were
placed on the April 2017 polling-station coordinates by their position in the booth sequence; a Gaussian
kernel (σ = 1 km) gave votes per km².

**Raw link: strong.** Share of undeveloped land developed, by fifth of votes density:

| fifth | votes / km² (median) | 2017–20 | 2020–23 |
|---|---|---|---|
| Q1 | 28 | 0.09% | 0.18% |
| Q3 | 154 | 0.20% | 0.23% |
| Q5 | 1,200 | **1.27%** | **1.23%** |

**In a model: nothing.**

| model | 2017–20 AUC | 2020–23 AUC | pooled R² | LR vs M0 |
|---|---|---|---|---|
| M0 base (distances, roads, built share, start class, AC) | 0.819 | 0.797 | 0.192 | |
| M1 + votes | 0.819 | 0.794 | 0.192 | p = 0.27 |
| M2 + WorldPop | 0.822 | 0.796 | 0.193 | p < 0.001 (2017–20 only) |
| votes only | 0.761 | 0.709 | 0.098 | |

Votes coefficient +0.03, p = 0.76: votes correlate 0.65 with built share in 1 km and 0.72 with road km.
"Many people nearby" means "next to the existing city". Caveats: booth locations are approximate (booths 5
numbers apart are 1.4–3 km apart), which biases towards zero; with a 2 km kernel votes become significant
(+0.29, p = 0.02).

### 18.2 C2: full 25-factor model and all the tests (5 Nov)

ρ² 0.23, cross-validated AUC 0.818. Four mechanisms each matter; people don't.

| mechanism | robust Wald | AUC lost when dropped | carried by |
|---|---|---|---|
| neighbourhood | p < 0.001 | −0.014 | mix (+), trees nearby (−), distance to the dense city (−) |
| supply constraints | p < 0.001 | −0.007 | lake edge, restricted land, slope, relief (all −) |
| land at the start | p < 0.001 | −0.007 | trees convert at a third of the odds |
| access | p < 0.001 | −0.006 | airport, HITEC / FD, major road (−) |
| people (votes, WorldPop) | **p = 0.79** | **+0.003** | none |

Key factor effects (average marginal effects against a mean of 0.42% per 3 years): land-use mix +0.25 pp per
SD, restricted land −0.34 pp, lake edge −0.32 pp, trees −0.32 pp.

| test | result |
|---|---|
| VIF | CBD 19–20, metro 12–17, HITEC 12–13: the three distances are nearly one variable in this small area |
| Chow (slopes × period) | χ² 81.7 on 27 df, p < 0.001: sizes shift between periods |
| temporal transfer | fit 2017–20 → AUC 0.809 on 2020–23 (its own CV 0.797): *where* is stable |
| Moran's I | 0.15, p = 0.005: unexplained change clusters within ~500 m |
| calibration | close in deciles 1–9; top decile over-predicted (2.5% vs 2.0%) |
| roads added during the period | z = 6.4: roads arrive *with* layouts, so minor-road km is not a cause |
| contagion (2017–20 change nearby) | × 1.10 per SD, p = 0.06 |
| GO 111 (stand-in) × after 2022 | DiD +0.10, p = 0.57: inconclusive |

### 18.3 C3: Table 18, no census (5 Nov)

ρ² 0.222, AUC 0.824. Kept: tree cover −1.162; trees within 1 km −0.029; mix +1.893; dense city −0.300;
airport −0.507; HITEC −0.480; major road −0.132; road mileage +0.021 per 10 km; slope −0.041; relief −0.065;
lake edge −1.284; restricted −1.551. Eliminated (jointly p = 0.21): WorldPop, elevation, CBD, ORR, **booth
votes (t −0.70)**, lake distance, res / non-res share, GO 111, metro, water share, night lights.

### 18.4 C4: + jobs and census (6 Nov)

ρ² 0.229, AUC 0.825; census factors jointly χ² 23.8 on 6 df, p = 0.0006. New rows: workers within 5 km
−0.256 (⚠ sign flips: collinear with road km, r = 0.89), manufacturing % −0.020, **100+ worker
establishments % +0.036**, SC/ST % −0.009, farm workers % +0.005 (⚠), two/three-wheeler % +0.007.

### 18.5 C5: Florida-style final trial table (6 Nov)

Road mileage and distance to the dense city left out of the candidates (near-duplicates of job mass), as job
density enters Table 18. **This is the final trial table.**

| Variable | Estimate | t | 2017–20 | t | 2020–23 | t |
|---|---|---|---|---|---|---|
| Constant | −3.598 | −6.86 | −3.955 | −6.88 | −3.326 | −5.18 |
| Tree cover (vs open) | −1.096 | −7.51 | −0.931 | −4.67 | −1.278 | −7.51 |
| Water within 1 km (%) | −0.040 | −2.88 | −0.054 | −2.81 | −0.023 | −1.38 |
| Trees within 1 km (%) | −0.042 | −7.56 | −0.042 | −6.34 | −0.042 | −5.97 |
| Land-use mix (0–1) | 3.123 | 9.59 | 3.428 | 8.60 | 2.799 | 7.37 |
| Ln km to airport | −0.519 | −6.09 | −0.504 | −4.40 | −0.524 | −5.35 |
| Ln km to HITEC / FD | −0.362 | −4.18 | −0.371 | −4.23 | −0.357 | −3.18 |
| Ln km to major road | −0.161 | −2.73 | −0.145 | −1.98 | −0.198 | −2.90 |
| Slope (°) | −0.037 | −2.15 | −0.047 | −1.80 | −0.028 | −1.36 |
| Relief within 150 m (m) | −0.071 | −2.48 | −0.087 | −2.23 | −0.058 | −1.60 |
| Within 100 m of a lake | −1.169 | −7.46 | −1.290 | −5.85 | −1.060 | −5.27 |
| Military / forest / protected / airport land | −1.508 | −4.32 | −0.922 | −2.59 | −1.977 | −2.45 |
| Manufacturing (% of jobs within ~5 km) | −0.021 | −3.44 | −0.025 | −2.81 | −0.018 | −2.30 |
| 100+ worker establishments (% of jobs) | 0.030 | 3.82 | 0.041 | 4.74 | 0.021 | 2.15 |
| SC / ST (% of people) | −0.009 | −3.10 | −0.007 | −1.92 | −0.011 | −3.04 |
| Rajendranagar (vs Maheshwaram) | −0.104 | −0.73 | | | | |
| Serilingampally | −0.264 | −1.05 | | | | |
| 2020–23 | −0.034 | −0.52 | | | | |

ρ² 0.222 (2017–20 0.247, 2020–23 0.203), AUC 0.821. The 20 eliminated variables jointly p = 0.18.
**Readings:** trees × 0.33; airport twice as far × 0.70; HITEC twice as far × 0.78; lake edge × 0.31;
restricted × 0.22; +10 points of big-employer jobs × 1.35; +10 points of manufacturing × 0.81.
**Job density** is positive (+0.242, t 3.0, the Florida sign) only when land-use mix is left out; mix
(r = 0.74 with job mass) carries the same signal and fits better.

**Trial verdict.** The pipeline works; the trial's location story (airport, HITEC) had to be checked on the
whole region, because in 1,164 km² the distances are too collinear (VIF 12–20).

---

# Part 3: reference

---

## 19. How to reproduce every run

From the repo root, in the project environment. The `*_full` / `*_census` samples are in the repo, so the
model steps (05, 06, 08, 09, 11) need no raw data.

```
# Phase B (10 m transition models; needs the raster tiles)
python scripts/lu/21_transition_data.py
python scripts/lu/22_choice_models.py 2017 2023
python scripts/lu/24_period_compare.py
python scripts/lu/25_latent_segmentation.py

# Phase C (trial)
python scripts/change/03_trial_logit.py           # C1 votes
python scripts/change/05_full_logit.py            # C2 full model and tests
python scripts/change/06_table18.py               # C3
python scripts/change/06_table18.py census        # C4
python scripts/change/06_table18.py florida       # C5 final trial table

# Phase D (all of HMDA, strict rule)
REGION=hmda python scripts/change/06_table18.py census     # D1 main
REGION=hmda python scripts/change/06_table18.py florida    # D2
REGION=hmda python scripts/change/06_table18.py            # D2
REGION=hmda python scripts/change/08_consistency.py        # D3
REGION=hmda python scripts/change/05_full_logit.py         # D4

# Phase E-H (strict rule as written; put OUTCOME=persist in front for the persistence-rule versions)
REGION=hmda OUTCOME=persist python scripts/change/06_table18.py census   # E1
REGION=hmda python scripts/change/09_added_value.py                      # F
REGION=hmda python scripts/change/10_bus_stops.py                        # G (needs the bus-stop file)
REGION=hmda python scripts/change/11_zoning.py                           # H

# Building the samples from raw data (maps, Open Buildings grids, OSM, EC6, SHRUG)
REGION=hmda python scripts/change/02_trial_data.py
REGION=hmda SKIP_EE=1 python scripts/change/04_more_factors.py
REGION=hmda python scripts/change/04_more_factors.py terrain   # Earth Engine
REGION=hmda python scripts/change/07_census_factors.py

# Zoning layer from the 30 sheets
python scripts/masterplan/01_georef.py && python scripts/masterplan/02_refine_roads.py
python scripts/masterplan/03_zones.py && python scripts/masterplan/04_mosaic.py
```

Run times: sample building about 5 minutes (terrain 14 minutes); every model and test under 2 minutes; a
full rerun with a new change rule about 20 minutes.

**More detail:** `scripts/change/README.md` (pipeline, switches, raw data), `scripts/masterplan/README.md`
(digitising), `outputs/change/README.md` (what is in each results folder), and the archived write-ups in §21.

---

## 20. Glossary

| term | meaning |
|---|---|
| binary logit | model of a yes/no outcome; each factor shifts the log-odds linearly |
| MNL | multinomial logit: more than two outcomes (none / residential / non-residential) |
| latent segmentation | the model finds groups of cells that respond differently, instead of fixing them by hand |
| odds ratio | how many times a factor multiplies the odds of change |
| ρ² (McFadden) | 1 − LL(model) / LL(constant only); 0.2–0.4 is a good fit for a logit |
| AUC | probability the model ranks a random changed cell above a random unchanged one (0.5 guess, 1 perfect) |
| cross-validated by tile | fitted on some 4 km tiles, scored on others never seen |
| choice-based sampling | over-sampling the rare outcome; slopes stay right, the constant is corrected |
| King–Zeng correction | the formula that shifts the constant back to the real change rate |
| cluster-robust SE | standard errors that allow cells in the same 4 km tile to be correlated |
| robust Wald test | tests whether a group of coefficients is jointly zero, with clustered errors |
| backward elimination | drop the least significant factor and refit until all have \|t\| ≥ 1.96 |
| VIF | variance inflation factor; above ~10, single coefficients are unreliable |
| Moran's I | spatial autocorrelation of residuals (0 = none) |
| temporal transfer | fit on one period, predict the next |
| strict / persistence / middle rule | the three ways of counting change (§4.3) |
| GO 111 | Government order restricting building around Osman Sagar and Himayat Sagar (repealed 2022) |
| MDP 2031 | HMDA Metropolitan Development Plan 2031, the master plan approved in 2013 |

---

## 21. Detailed write-ups (archived)

Before this report, each stage had its own longer write-up. They are kept in `docs/archive/` (see its README). This
report covers their results; they hold extra detail that is not repeated here.

| section here | archived write-up | extra detail it holds |
|---|---|---|
| §1, §5, §13 | `docs/archive/CHANGE_MODEL_PLAN_2026-11-02.md` | the original plan: Florida's four-step framework, factors considered but never tested (FTL buffers, flood extent, new municipalities, guideline values, state projects), natural-experiment ideas, the voter-roll feasibility notes |
| §6 | `docs/archive/HMDA_RESULTS.md` | full odds-ratio table, elimination order, every subregion's own elimination, factor correlations, full calibration deciles |
| §7 | `docs/archive/PERSIST_RESULTS.md` | persistence-rule elimination order, per-period counts, drop-one table, Chow test |
| §17 | `docs/archive/CHOICE_MODEL_RESULTS_10m_Oct.md` | the October 10 m models: gradients by distance, per-period MNL, SHAP, latent-segment coefficients |
| §18.1 | `docs/archive/trial/TRIAL_RESULTS.md` | booth-vote fifths, booth renumbering and placement, booth-shift checks |
| §18.2 | `docs/archive/trial/FULL_MODEL_RESULTS.md` | full 25-factor coefficient and marginal-effect table, each group's AUC alone, GO 111 raw rates |
| §18.3 | `docs/archive/trial/TABLE18_RESULTS.md` | per-period C3 estimates, t-values of eliminated factors |
| §18.4–18.5 | `docs/archive/trial/TABLE18_CENSUS.md` | Economic Census and SHRUG linkage, univariate census t-values, job-density check |
| §18.2–18.3 | `docs/archive/change_trial_first_run/` | the very first trial run, with 95% intervals for the C3 odds ratios |
| overview | `docs/archive/CHANGE_OVERVIEW_2026-11-17.md` | the earlier one-page overview of the change model (now this report's Part 1) |
