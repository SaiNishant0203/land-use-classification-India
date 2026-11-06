# Hyderabad version of Table 18: binary logit model of land-use change (Base: no change)

*5 Nov 2026, trial region (3 constituencies: Maheshwaram, Rajendranagar, Serilingampally; 1,164 km²).
The "vacant parcel" is a 20 m cell that is undeveloped at t−1 (open land or trees, Open Buildings
cover < 5%). Change = confirmed development by t (our map built + Open Buildings new building). Two
periods, 2017→2020 and 2020→2023, pooled with a period dummy. Code: `scripts/change/06_table18.py`;
tables in `table18/`.*

## Table

Variables are kept as in Table 18: only significant ones (|t| ≥ 1.96). t stats come from standard errors
clustered by 4 km tile, because neighbouring cells aren't independent. Constituency and period are kept as
controls whatever their t.

| Variable | Estimate | t stat | 2017–20 est. | t | 2020–23 est. | t |
|---|---|---|---|---|---|---|
| Constant | −3.333 | −6.81 | −3.523 | −6.94 | −3.292 | −5.44 |
| ***Land cover of the cell at t−1 (Base: open land)*** | | | | | | |
| Tree cover | −1.162 | −7.88 | −0.995 | −4.87 | −1.338 | −7.66 |
| ***Land use within 1 km (% by area) (Base: open land)*** | | | | | | |
| Trees | −0.029 | −5.90 | −0.027 | −4.18 | −0.031 | −4.98 |
| Land-use mix (entropy, 0–1) | 1.893 | 5.65 | 2.221 | 4.65 | 1.575 | 3.52 |
| ***Urban form*** | | | | | | |
| Ln(km to the dense city, 1 km built share ≥ 40%) | −0.300 | −4.00 | −0.270 | −3.12 | −0.325 | −3.14 |
| ***Accessibility*** | | | | | | |
| Ln(km to the airport) | −0.507 | −5.15 | −0.472 | −4.04 | −0.515 | −4.57 |
| Ln(km to HITEC City / Financial District) | −0.480 | −4.68 | −0.541 | −5.08 | −0.418 | −3.32 |
| Ln(km to the nearest major road) | −0.132 | −2.23 | −0.100 | −1.29 | −0.186 | −2.77 |
| **Road mileage in the 4 km × 4 km window (per 10 km)** | **0.021** | **2.21** | 0.037 | 2.85 | 0.009 | 0.77 |
| ***Supply constraints*** | | | | | | |
| Slope (degrees) | −0.041 | −2.34 | −0.052 | −2.04 | −0.030 | −1.42 |
| Relief within 150 m (m) | −0.065 | −2.16 | −0.085 | −2.27 | −0.047 | −1.22 |
| Within 100 m of a lake | −1.284 | −8.96 | −1.537 | −7.15 | −1.038 | −5.77 |
| Military, forest, protected or airport land | −1.551 | −4.21 | −0.833 | −2.04 | −2.087 | −2.52 |
| ***Assembly constituency (Base: Maheshwaram)*** | | | | | | |
| Rajendranagar | −0.109 | −0.75 | −0.236 | −1.37 | −0.026 | −0.15 |
| Serilingampally | −0.355 | −1.34 | −0.495 | −1.70 | −0.294 | −0.97 |
| ***Period (Base: 2017–2020)*** | | | | | | |
| 2020–2023 | −0.056 | −0.78 | -- | -- | -- | -- |

| | pooled | 2017–20 | 2020–23 |
|---|---|---|---|
| cells (changes) | 19,813 (3,071) | 9,896 (1,521) | 9,917 (1,550) |
| parameters | 16 | 15 | 15 |
| log-likelihood, constant only | −8,545.0 | −4,246.1 | −4,298.8 |
| log-likelihood at convergence | −6,646.8 | −3,199.7 | −3,421.2 |
| ρ² (vs constant only) / adjusted ρ² | 0.222 / 0.220 | 0.246 / 0.243 | 0.204 / 0.201 |
| AUC, 5-fold cross-validated by 4 km tile | 0.824 | 0.838 | 0.803 |

**Tested and eliminated** (one at a time, least significant first), with the t when eliminated:

| t | variables |
|---|---|
| \|t\| < 1 | WorldPop (0.08), elevation (−0.19), distance to the old CBD (0.46), distance to the ORR interchange (−0.58), **booth votes (−0.70)**, distance to a lake (−0.74), residential share within 1 km (−0.86), non-residential share within 1 km (−0.99) |
| 1 ≤ \|t\| < 1.96 | GO 111 zone (1.09), distance to metro (−1.28), water share within 1 km (−1.50), night lights (−1.84) |

Jointly the 12 add nothing: robust Wald χ² = 15.6 on 12 df, p = 0.21. The constant is corrected for
the choice-based sample (King & Zeng), since changes are over-sampled about 40 times.

## Reading it

Odds ratios:
- **Tree cover:** trees convert at **0.31×** the odds of open land.
- **Trees within 1 km:** each 10 points of tree share → **× 0.75**.
- **Land-use mix:** +0.1 → **× 1.21**. Development goes where land use is already mixed.
- **Distance to the dense city:** twice as far → **× 0.81**. Growth spreads out from the city edge.
- **Airport:** twice as far → **× 0.70**.
- **HITEC City / Financial District:** twice as far → **× 0.72**.
- **Major road:** twice as far → **× 0.91**.
- **Road mileage:** +100 km of road in the 16 km² window → **× 1.23**.
- **Constraints:**
  - lake edge **× 0.28**;
  - military, forest or airport land **× 0.21**;
  - each degree of slope **× 0.96**;
  - each metre of relief **× 0.94**.

## Compared with Florida's Table 18

| Florida (single-family parcels) | Hyderabad (here) |
|---|---|
| % Hispanic, % zero-vehicle households (block group / tract) | none: no small-area socio-demographics yet. Census 2011 village/ward tables are the candidates (CHANGE_MODEL_PLAN.md §5b). Booth votes and WorldPop were tested and are not significant. |
| Job density | distance to HITEC City / Financial District (no job-density data at this scale yet) |
| Ln(parcel area) | none: 20 m cells all have the same area; there is no parcel map |
| Block-group land use (% by area): SF −, MF + | land use within 1 km (% by area): trees −, mix +; residential and non-residential shares eliminated |
| % flood zone A (+) | supply constraints: lake edge, restricted land, slope, relief (all −) |
| none | accessibility: airport, HITEC/FD, major road, road mileage (Prof.'s list) |
| t stats 2.8–53 | t stats 2.2–9.0 (fewer observations, clustered standard errors) |

## About road mileage

Road km within a 4 km × 4 km window around each cell is in every model.
- **Base model:** total road km.
- **Full model:** split into major roads (motorway–secondary) and minor roads.
- **Data:** OSM as of the start year (Geofabrik snapshot of 1 Jan 2018 for 2017, 1 Jan 2021 for 2020).
- **Result:** in the final model it is positive and significant pooled (t = 2.21) and in 2017–20 (t = 2.85), but not in 2020–23 (t = 0.77).
- **Caveat:** the road km *added during* a period predicts that period's change even more strongly (z = 6.4, `FULL_MODEL_RESULTS.md` §4). So part of the road-mileage effect is roads that come with the new layouts, not roads that came first.

## Caveats

- Trial region only (3 constituencies, about 15% of HMDA's area). Over this area the distances to CBD, metro and HITEC
  are almost collinear, so which one survives the elimination is partly chance; the ORR and metro may
  well come back on the full HMDA sample.
- Booth locations for the votes variable are approximate (`TRIAL_RESULTS.md` §5).
- The 60-cell eyeball check of the change definition is still outstanding.
- Florida estimates one such model per current land use (18 types). With only undeveloped land at risk, a
  tree-cover dummy does that job here. Separate open and tree models are possible, but the tree model would have only 167 changes.
