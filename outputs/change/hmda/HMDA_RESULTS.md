# Land-use change model: all of HMDA (11 November 2026)

> **Provisional (later the same day).**
> - **The outcome is too strict.** It needs both our map and Open Buildings, and that keeps only about 1 in
>   7 real changes. A check on the yearly maps shows that 80% of the map's new building stays built through
>   2023, at about 0.55% of open land a year (results log #53).
> - **Distance to the existing city dominates.** It alone gives AUC 0.80. Several of the other surviving
>   factors have small effects and pass only because the sample is large.
> - The tables below stand as a record of that run, to be redone with the persistence outcome.

**Question:** do the trial findings (3 constituencies, 1,164 km²) hold for all of HMDA (7,649 km²)? Following
Prof.'s note of 11 Nov, every variable was retested on the larger region, starting again from every candidate.
The trial counts as a check that the data and model work, not as a source of conclusions.

**Short answer:** the model works better on all of HMDA (ρ² 0.236, cross-validated AUC 0.841, against 0.222 and
0.821 in the trial).
- **Land and terrain findings hold:** tree cover, trees nearby, land-use mix, lake beds, slope, restricted
  land, distance to a major road, and the share of jobs in big establishments.
- **The trial's location story does not hold:** across HMDA, development follows the old CBD and the
  nearest ORR interchange. Distance to the airport and to HITEC City drop out (t = −1.23 and 0.16).
  - Fitted on the trial constituencies alone, the HMDA data keep the airport (t = −6.0) and HITEC
    (t = −2.9).
  - So the difference is real geography (the south-west corridor behaves differently), not a data problem.
- **Census factors:** the number of jobs, people and vehicles again add nothing. The kind of jobs nearby
  does matter.

---

## 1. What was run

| | trial (5–8 Nov) | all of HMDA (11 Nov) |
|---|---|---|
| region | ACs 50–52, 1,164 km² | all of HMDA, 7,649 km² (19.1 M cells of 20 m) |
| open land at the start | | 16.3 M cells (2017), 16.0 M (2020) |
| confirmed change (population) | about 0.4% per 3 years | 37,240 cells = 0.23% (2017–20); 34,952 = 0.22% (2020–23) |
| sources disagree, left out | 10–13% | 3.3% (2017–20), 6.2% (2020–23) |
| sample | 19,813 cells, 3,071 changes | 120,000 cells, 12,314 changes (6,034 + 6,280) |
| sampling | one cell per 200 m block per outcome | same; 60,000 cells per period, every changing block kept |
| booth votes | 2018 Form 20, ACs 50–52 | not available outside the 3 ACs, so **not tested** |
| area dummies | AC (Rajendranagar, Serilingampally vs Maheshwaram) | old district of the nearest 2017 polling station (Medak, Nalgonda, Mahabubnagar, Hyderabad vs Rangareddy) |
| candidates | 36 | 35 (no votes), all retested from scratch |

The outcome rule, timing rule, King–Zeng constant correction and 4 km tile clustering are the same as in the
trial (see `CHANGE_MODEL_DEEP_DIVE.md`). The KZ population rate is now 0.242% (trial 0.405%).

**One fix was needed:** outside the HMDA boundary, the Open Buildings grid is NaN, and a moving-window mean
carries a NaN along the whole row. So for the HMDA run, the outside is set to 0 cover (the same as the edge
padding already used). The trial window had no such rows; the trial outputs were rerun and are unchanged.

## 2. Final model, all of HMDA (Table 18 layout)

Backward elimination from all 35 candidates to |t| ≥ 1.96. The district and period dummies are always kept.
Standard errors are clustered by 4 km tile.

| Variable | Estimate | t stat | 2017-20 est. | t | 2020-23 est. | t |
|---|---|---|---|---|---|---|
| Constant | -4.843 | -9.57 | -4.910 | -8.46 | -4.780 | -8.24 |
| ***Land cover of the cell at t-1 (Base: open land)*** | | | | | | |
| Tree cover (vs open land) | -1.099 | -16.19 | -0.941 | -10.83 | -1.263 | -13.70 |
| ***Land use within 1 km (% by area) (Base: open land)*** | | | | | | |
| Residential | -0.012 | -5.12 | -0.015 | -4.37 | -0.009 | -3.02 |
| Non-residential | -0.006 | -2.67 | -0.007 | -2.32 | -0.006 | -2.09 |
| Water | -0.047 | -4.23 | -0.057 | -4.42 | -0.036 | -2.30 |
| Trees | -0.045 | -11.35 | -0.046 | -8.96 | -0.044 | -9.30 |
| Land-use mix (entropy, 0-1) | 3.353 | 15.48 | 3.810 | 12.34 | 2.944 | 11.68 |
| ***Urban form*** | | | | | | |
| Ln(km to the dense city, 1 km built share >= 40%) | -0.231 | -6.01 | -0.219 | -4.47 | -0.238 | -4.92 |
| ***Accessibility*** | | | | | | |
| Ln(km to the old CBD) | -0.655 | -5.49 | -0.561 | -4.02 | -0.737 | -5.48 |
| Ln(km to the nearest ORR interchange) | -0.237 | -5.61 | -0.269 | -5.54 | -0.214 | -4.40 |
| Ln(km to the nearest major road) | -0.170 | -5.64 | -0.151 | -4.23 | -0.192 | -5.26 |
| ***Supply constraints*** | | | | | | |
| Slope (degrees) | -0.055 | -5.49 | -0.050 | -3.71 | -0.059 | -4.28 |
| Relief within 150 m (m) | -0.062 | -3.75 | -0.071 | -3.34 | -0.054 | -2.41 |
| Elevation (100 m) | 0.162 | 2.18 | 0.098 | 1.10 | 0.215 | 2.59 |
| Ln(km to a lake >= 2 ha) | 0.095 | 2.49 | 0.066 | 1.32 | 0.120 | 2.75 |
| Within 100 m of a lake | -1.091 | -10.76 | -1.288 | -9.26 | -0.911 | -7.45 |
| Military, forest, protected or airport land | -1.025 | -3.90 | -1.108 | -3.48 | -0.926 | -3.03 |
| ***Jobs, Economic Census 2013*** | | | | | | |
| Software / IT services (% of jobs within ~5 km) | 0.015 | 2.90 | 0.023 | 3.84 | 0.006 | 1.03 |
| Manufacturing (% of jobs within ~5 km) | -0.006 | -2.48 | -0.006 | -2.15 | -0.006 | -2.13 |
| Establishments with 100+ workers (% of jobs within ~5 km) | 0.011 | 4.50 | 0.011 | 4.04 | 0.011 | 3.70 |
| ***District (Base: Rangareddy)*** | | | | | | |
| Medak | 0.306 | 3.17 | 0.323 | 2.56 | 0.302 | 2.81 |
| Nalgonda | 0.126 | 0.71 | 0.150 | 0.76 | 0.119 | 0.52 |
| Mahabubnagar | 0.173 | 0.97 | 0.525 | 2.23 | -0.158 | -0.91 |
| Hyderabad | -0.740 | -3.66 | -0.440 | -2.04 | -1.056 | -4.47 |
| ***Period (Base: 2017-2020)*** | | | | | | |
| 2020-2023 | -0.021 | -0.58 | -- | -- | -- | -- |

| | pooled | 2017-20 | 2020-23 |
|---|---|---|---|
| cells | 120,000 | 60,000 | 60,000 |
| changes | 12,314 | 6,034 | 6,280 |
| parameters | 25 | 24 | 24 |
| log-likelihood, constant only | -39,695.4 | -19,579.6 | -20,113.0 |
| log-likelihood at convergence | -30,326.0 | -14,674.6 | -15,583.8 |
| rho-squared (vs constant only) | 0.236 | 0.251 | 0.225 |
| adjusted rho-squared | 0.235 | 0.249 | 0.224 |
| AUC, 5-fold cross-validated by 4 km tile | 0.841 | 0.847 | 0.837 |

The 16 eliminated variables together: robust Wald χ² = 11.1 on 16 df, p = 0.80. In order of elimination
(t when dropped):
1. workers per km² in the village (−0.06)
2. workers within ~5 km (−0.12)
3. WorldPop (−0.14)
4. km to HITEC/FD (0.16)
5. four-wheeler households (−0.29)
6. km to metro (0.36)
7. literacy (0.47)
8. road mileage (0.64)
9. GO 111 zone (0.75)
10. night lights (−0.77)
11. farm workers (−0.97)
12. village people per km² (−1.01)
13. SC/ST share (−0.94)
14. two/three-wheeler households (0.97)
15. km to airport (−1.23)
16. inside GHMC (−1.47)

### Odds ratios in readable units (pooled, 95% interval)

| variable | change | odds ratio | 95% interval |
|---|---|---|---|
| Tree cover on the cell | yes vs open | 0.33 | 0.29–0.38 |
| Residential within 1 km | +10 points | 0.89 | 0.85–0.93 |
| Non-residential within 1 km | +10 points | 0.94 | 0.89–0.98 |
| Water within 1 km | +10 points | 0.62 | 0.50–0.78 |
| Trees within 1 km | +10 points | 0.64 | 0.59–0.69 |
| Land-use mix | +0.1 | 1.40 | 1.34–1.46 |
| Distance to the dense city | half as far | 1.17 | 1.11–1.24 |
| Distance to the old CBD | half as far | 1.57 | 1.34–1.85 |
| Distance to the nearest ORR interchange | half as far | 1.18 | 1.11–1.25 |
| Distance to the nearest major road | half as far | 1.13 | 1.08–1.17 |
| Slope | +1 degree | 0.95 | 0.93–0.97 |
| Relief within 150 m | +1 m | 0.94 | 0.91–0.97 |
| Elevation | +100 m | 1.18 | 1.02–1.36 |
| Distance to a lake ≥ 2 ha | half as far | 0.94 | 0.89–0.99 |
| Within 100 m of a lake | yes vs no | 0.34 | 0.28–0.41 |
| Military, forest, protected or airport land | yes vs no | 0.36 | 0.21–0.60 |
| IT share of jobs within ~5 km | +10 points | 1.16 | 1.05–1.28 |
| Manufacturing share of jobs within ~5 km | +10 points | 0.94 | 0.90–0.99 |
| Share of jobs in 100+ worker establishments | +10 points | 1.12 | 1.06–1.17 |
| Medak (vs Rangareddy) | yes vs no | 1.36 | 1.12–1.64 |
| Nalgonda | yes vs no | 1.13 | 0.80–1.61 |
| Mahabubnagar | yes vs no | 1.19 | 0.84–1.68 |
| Hyderabad district | yes vs no | 0.48 | 0.32–0.71 |
| 2020–23 (vs 2017–20) | | 0.98 | 0.91–1.05 |

**How to read it:**
- **Halving the distance to the old CBD** raises the odds of development by 57%. Halving the distance to an
  ORR interchange raises them by 18%.
- **A tree-covered cell** has a third of the odds of an open cell.
- **More mixing within 1 km** raises the odds: each +0.1 of land-use mix raises them by 40%.
- **Already-built land nearby** (residential, non-residential) slightly lowers the odds, once mix and
  distance to the dense city are in. Neighbourhoods that are already full have less room left.

## 3. Trial vs all of HMDA, same candidates and same procedure

Census specification, all candidates: the trial `table18_census` against the HMDA one above.

| variable | trial est. | t | HMDA est. | t | |
|---|---|---|---|---|---|
| Tree cover (vs open land) | -1.151 | -7.87 | -1.099 | -16.19 | kept in both |
| Residential | | | -0.012 | -5.12 | HMDA only |
| Non-residential | | | -0.006 | -2.67 | HMDA only |
| Water | | | -0.047 | -4.23 | HMDA only |
| Trees | -0.029 | -5.69 | -0.045 | -11.35 | kept in both |
| Land-use mix (entropy, 0-1) | 1.788 | 5.11 | 3.353 | 15.48 | kept in both |
| Ln(km to the dense city) | -0.312 | -4.37 | -0.231 | -6.01 | kept in both |
| Ln(km to the airport) | -0.484 | -5.38 | | | trial only |
| Ln(km to HITEC City / Financial District) | -0.410 | -4.63 | | | trial only |
| Ln(km to the old CBD) | | | -0.655 | -5.49 | HMDA only |
| Ln(km to the nearest ORR interchange) | | | -0.237 | -5.61 | HMDA only |
| Ln(km to the nearest major road) | -0.134 | -2.14 | -0.170 | -5.64 | kept in both |
| Road mileage in 4 x 4 km (10 km) | 0.032 | 2.12 | | | trial only |
| Slope (degrees) | -0.039 | -2.28 | -0.055 | -5.49 | kept in both |
| Relief within 150 m (m) | -0.064 | -2.06 | -0.062 | -3.75 | kept in both |
| Elevation (100 m) | | | 0.162 | 2.18 | HMDA only |
| Ln(km to a lake >= 2 ha) | | | 0.095 | 2.49 | HMDA only |
| Within 100 m of a lake | -1.296 | -9.20 | -1.091 | -10.76 | kept in both |
| Military, forest, protected or airport land | -1.535 | -4.32 | -1.025 | -3.90 | kept in both |
| Ln(workers within ~5 km) | -0.256 | -2.16 | | | trial only |
| Software / IT services (% of jobs within ~5 km) | | | 0.015 | 2.90 | HMDA only |
| Manufacturing (% of jobs within ~5 km) | -0.020 | -2.94 | -0.006 | -2.48 | kept in both |
| Establishments with 100+ workers (% of jobs) | 0.036 | 3.33 | 0.011 | 4.50 | kept in both |
| SC / ST (% of people) | -0.009 | -3.25 | | | trial only |
| Agricultural workers (% of workers) | 0.005 | 2.34 | | | trial only |
| Households with a two- or three-wheeler (%) | 0.007 | 2.16 | | | trial only |
| fit: ρ² / AUC (cross-validated) | 0.229 / 0.825 | | 0.236 / 0.841 | | |

**11 of the trial's 18 factors survive, all with the same sign** (the period dummy is kept in both). The 7
that don't survive:
- airport, HITEC/FD, road mileage, jobs within 5 km, SC/ST share, farm workers, two-wheeler ownership.

In their place, HMDA brings in:
- old CBD, ORR, residential, non-residential and water shares, elevation, lake distance, and IT share.

**Florida-style variant on HMDA** (road mileage and distance to the dense city left out, as chosen for the
trial):
- ρ² 0.233, AUC 0.839.
- The same story: CBD t = −6.2, ORR t = −6.4, HITEC eliminated at t = 0.24, airport at t = −1.45.
- In the trial, the reason to leave those two out was that they were near-duplicates of jobs within 5 km
  (r = 0.89 and −0.85). Across HMDA they still are (r = 0.84 and −0.79). But jobs within 5 km is eliminated
  either way, so the choice no longer changes anything.
- **Main specification:** the all-candidates table above.

**Without census factors:** ρ² 0.233, AUC 0.839. The same land, terrain and accessibility set; CBD t = −7.2,
ORR t = −6.5.

## 4. Are the findings the same across HMDA? (`consistency/CONSISTENCY.md`)

The HMDA final specification was refitted in each subregion. Then the elimination was rerun from all 35
candidates, separately in each.

| | HMDA | trial ACs 50–52 | rest of HMDA | CBD < 20 km | CBD 20–35 km | CBD ≥ 35 km |
|---|---|---|---|---|---|---|
| cells | 120,000 | 18,777 | 101,223 | 17,882 | 42,522 | 59,596 |
| changes | 12,314 | 3,059 | 9,255 | 5,279 | 4,829 | 2,206 |
| ρ² (HMDA specification) | 0.236 | 0.232 | 0.231 | 0.131 | 0.168 | 0.173 |
| AUC (cross-validated) | 0.841 | 0.829 | 0.840 | 0.732 | 0.792 | 0.812 |
| variables kept by own elimination | 19 | 12 | 17 | 19 | 14 | 16 |

### Robust findings

These have the same sign and are significant in (almost) every subregion. t is given for HMDA / trial ACs / rest /
< 20 km / 20–35 km / ≥ 35 km.
- **Tree cover on the cell:** −16.2 / −8.5 / −14.0 / −13.5 / −8.9 / −5.3.
- **Trees within 1 km:** −11.3 / −4.0 / −12.3 / −7.0 / −10.6 / −6.4.
- **Land-use mix:** 15.5 / 4.3 / 16.6 / 7.1 / 12.0 / 9.2.
- **Within 100 m of a lake:** −10.8 / −5.2 / −9.5 / −8.6 / −5.6 / −4.7.
- **Share of jobs in 100+ worker establishments:** positive everywhere, t 1.9 to 4.5.
- **Distance to the dense city:** negative everywhere, t −1.4 to −6.0.
- **Distance to a major road:** negative everywhere except inside 20 km of the CBD (0.4), where every cell
  is near a major road anyway.
- **Slope:** negative everywhere except beyond 35 km (−0.8).

### Findings that depend on where you look

- **Airport and HITEC/FD:**
  - In the trial ACs' own elimination: kept (t −6.0 and −2.9), as in the trial.
  - In the rest of HMDA: neither is kept.
  - The airport even turns positive beyond 35 km (3.2): far out, being nearer the airport means being
    nearer the empty south.
  - So these are features of the south-west corridor, not of Hyderabad as a whole.
- **Old CBD:**
  - Strongly negative overall (−5.5).
  - It flips inside 20 km (+0.27, t 1.9; own elimination +2.8): inside the city, new building happens at
    the edge, not near the centre.
- **ORR interchange:** negative inside 35 km (t −2.1 to −5.3); nothing beyond 35 km (0.1).
- **Restricted land:**
  - Beyond 35 km, no restricted cell was developed at all, so the estimate runs off (−17.4). That is
    complete separation, not a real effect size.
  - At 20–35 km: no effect (0.1).
- **IT share:** positive in the rest of HMDA (4.3). Nothing in the trial ACs (−0.7, where almost every cell
  is near IT jobs). Unstable beyond 35 km, where there are hardly any IT jobs.
- **Model strength:** much weaker inside 20 km of the CBD (AUC 0.73, ρ² 0.13). Infill in the city is harder
  to predict from these factors than new building on the fringe.

## 5. The tests (full 25-factor model, `full/`)

| test | trial | all of HMDA |
|---|---|---|
| ρ² / cross-validated AUC, pooled | 0.225 / 0.818 | 0.235 / 0.839 |
| group test, access (8 factors) | χ² 77.7, p < 0.001 | χ² 204.5, p < 0.001 |
| group test, neighbourhood (7) | χ² 72.1 | χ² 512.6 |
| group test, supply constraints (7) | χ² 121.7 | χ² 280.6 |
| group test, people | votes + WorldPop χ² 0.48, p = 0.79 | WorldPop only χ² 0.88, p = 0.35 |
| Moran's I of residuals, 8 nearest | 0.155 / 0.146, p = 0.005 | 0.197 / 0.188, p = 0.005 (median 8th neighbour 0.56 km) |
| slopes differ between periods (Wald) | χ² 81.7, p < 0.001 | χ² 77.0 on 28 df, p < 0.001 |
| temporal transfer AUC (fit 2017–20, predict 2020–23) | 0.809 | **0.834** (own cross-validated AUC 0.836) |
| road km added during the period, added | z = 6.4 | z = 7.9 (odds × 1.16 per SD) |
| share of 1 km developed in 2017–20 (contagion) | p = 0.06 | z = 5.8 (× 1.17 per SD) |
| GO 111 × 2020–23 (after the repeal) | p = 0.57 | z = 1.32, p = 0.19 |

**Calibration** (population scale, deciles of predicted probability, % per 3 years):

| decile | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 |
|---|---|---|---|---|---|---|---|---|---|---|
| predicted | 0.012 | 0.035 | 0.051 | 0.067 | 0.086 | 0.112 | 0.159 | 0.257 | 0.555 | 1.803 |
| observed | 0.011 | 0.026 | 0.039 | 0.051 | 0.072 | 0.093 | 0.173 | 0.304 | 0.653 | 1.581 |

The top decile is over-predicted by about 14%; deciles 8–9 are under-predicted by about 15%.

**Collinearity:**
- The variance inflation factor is still high for the old CBD (15–18) and the metro (10–15).
- Across HMDA, ln distance to the CBD and to the metro correlate at r = 0.88; road mileage and jobs within
  5 km at 0.84.
- The correlations are not lower than in the trial: CBD vs HITEC r = 0.69 (trial 0.65), ORR vs CBD 0.66
  (trial 0.59). What helps is the sample, six times larger and spread over the whole region. Single distance
  coefficients should still be read together with the group tests.

**Things that change between periods** (slope × period interactions, p < 0.05):
- tree cover (stronger in 2020–23);
- residential share;
- lakes;
- WorldPop;
- Mahabubnagar.

## 6. What we can and can't say

**Can say:**
- **Shared across HMDA:** open land with no trees, in mixed neighbourhoods, close to the existing dense city
  and to major roads, away from lake beds and steep ground, is where Hyderabad builds. That holds in every
  part of HMDA.
- **The big location factors** across HMDA are the old CBD and the ORR interchanges. Their effect fades
  beyond about 35 km from the centre.
- **Census factors:** the number of jobs or people nearby adds nothing beyond land use. The kind of
  employment does add something: big establishments and IT pull development, manufacturing holds it back.

**Can't say:**
- **The airport and HITEC/FD** are not Hyderabad-wide drivers. They matter in the south-west, which is
  where the trial was.
- **Booth votes** could not be tested outside the 3 trial ACs. That would need the 2018 Form 20 for every
  AC in HMDA (about 31 more).
- **GO 111:** no effect, but this is still the 10 km stand-in for the 84 notified villages.
- **Residual dependence:** Moran's I of the residuals is about 0.19, so neighbouring cells still share
  something the model misses. The t-values are clustered by 4 km tile, which allows for this within tiles.

**Caveats:**
- **Districts:** they come from the nearest 2017 polling station, so they are approximate near the borders.
  They are the pre-2016 districts.
- **SECC vehicle data:** missing for 7,865 cells (6.5%), filled with the AC median.
- **Map edge:** near the HMDA edge, the 1 km and 4 km windows count land outside HMDA as empty.

## 7. Files and rerun

- **Results:**
  - `outputs/change/hmda/table18_census/` is the main table.
  - `table18_florida/` and `table18/` are the variants.
  - `consistency/` has the subregion tables.
  - `full/` has the 25-factor model and the tests.
  - `added_value/` (how much each group adds), `bus_stops/` and `zoning/` (master-plan zoning) came after
    this write-up; their findings are in `outputs/change/README.md`.
- **Data:** `data/processed/change/hmda_cells.parquet`, `hmda_cells_full.parquet` (with terrain),
  `hmda_cells_census.parquet`; logs `hmda_build.log`, `hmda_terrain.log`, `hmda_census.log`, `m_*.log`.
- **Rerun:**

```
REGION=hmda python scripts/change/02_trial_data.py
REGION=hmda SKIP_EE=1 python scripts/change/04_more_factors.py
REGION=hmda python scripts/change/04_more_factors.py terrain      # Earth Engine
REGION=hmda python scripts/change/07_census_factors.py
REGION=hmda python scripts/change/06_table18.py census            # main
REGION=hmda python scripts/change/06_table18.py florida
REGION=hmda python scripts/change/06_table18.py
REGION=hmda python scripts/change/08_consistency.py
REGION=hmda python scripts/change/05_full_logit.py
REGION=hmda python scripts/change/09_added_value.py
REGION=hmda python scripts/change/10_bus_stops.py
REGION=hmda python scripts/change/11_zoning.py
```

- **Run times:**
  - Steps 02 and 04 (without terrain): 5 minutes in total.
  - Terrain: 14 minutes (120,000 points).
  - Census: 45 seconds.
  - All models and tests: under 2 minutes.
