# Table 18 with census factors: jobs, people and households

*6 Nov 2026. Same trial sample and method as `TABLE18_RESULTS.md` (3 constituencies, 19,813 cells,
3,071 changes; backward elimination to |t| ≥ 1.96 with t from standard errors clustered by 4 km tile).
New candidates, all measured **before 2017**:*

- *jobs: 6th Economic Census 2013–14 microdata, every establishment (exported from the MoSPI DVD);*
- *people: Population Census 2011;*
- *households: SECC 2011–12 vehicle ownership.*

*These are linked to Census 2011 villages and towns with the SHRUG keys and boundaries. Code:
`scripts/change/07_census_factors.py`, then `06_table18.py census`. Tables: `table18_census/`.*

## Data

- **Economic Census 2013:**
  - 5.54 M workers in Telangana, 99.5% linked to a village or town.
  - HMDA: 899 villages/towns with 2.62 M workers. The 2011 population is 9.86 M.
- **Assigning cells to villages:** 87% of cells fall inside a village polygon. The other 13% are in the slivers
  SHRUG's simplified boundaries leave between villages (median 0.4 km wide), so they get the nearest village.
- **GHMC:** comes as two big polygons. The 17% of cells there get city-wide averages for the "own village" variables.
- **Jobs within about 5 km:** each village's workers are spread evenly over its area, then smoothed with a
  Gaussian kernel (σ = 2.5 km).
- **Missing SECC data:** 41 villages, i.e. 1,349 cells, have no SECC data and get their constituency's median.

## Table

| Variable | Estimate | t stat | 2017–20 est. | t | 2020–23 est. | t |
|---|---|---|---|---|---|---|
| Constant | −1.957 | −1.99 | −2.285 | −2.08 | −1.355 | −1.17 |
| ***Land cover of the cell at t−1 (Base: open land)*** | | | | | | |
| Tree cover | −1.151 | −7.87 | −0.988 | −4.91 | −1.323 | −7.74 |
| ***Land use within 1 km (% by area) (Base: open land)*** | | | | | | |
| Trees | −0.029 | −5.69 | −0.027 | −4.29 | −0.030 | −4.73 |
| Land-use mix (entropy, 0–1) | 1.788 | 5.11 | 2.013 | 3.95 | 1.510 | 3.49 |
| ***Urban form*** | | | | | | |
| Ln(km to the dense city) | −0.312 | −4.37 | −0.259 | −3.12 | −0.357 | −3.41 |
| ***Accessibility*** | | | | | | |
| Ln(km to the airport) | −0.484 | −5.38 | −0.509 | −4.51 | −0.459 | −4.15 |
| Ln(km to HITEC City / Financial District) | −0.410 | −4.63 | −0.453 | −4.30 | −0.376 | −3.27 |
| Ln(km to the nearest major road) | −0.134 | −2.14 | −0.112 | −1.36 | −0.176 | −2.62 |
| Road mileage in the 4 km × 4 km window (per 10 km) | 0.032 | 2.12 | 0.047 | 2.45 | 0.030 | 1.74 |
| ***Supply constraints*** | | | | | | |
| Slope (degrees) | −0.039 | −2.28 | −0.051 | −2.01 | −0.028 | −1.35 |
| Relief within 150 m (m) | −0.064 | −2.06 | −0.087 | −2.29 | −0.042 | −1.12 |
| Within 100 m of a lake | −1.296 | −9.20 | −1.565 | −7.49 | −1.034 | −5.77 |
| Military, forest, protected or airport land | −1.535 | −4.32 | −0.843 | −2.10 | −2.072 | −2.51 |
| ***Jobs, Economic Census 2013*** | | | | | | |
| Ln(workers within ~5 km) ⚠ | −0.256 | −2.16 | −0.267 | −2.22 | −0.310 | −2.20 |
| Manufacturing (% of jobs within ~5 km) | −0.020 | −2.94 | −0.018 | −1.85 | −0.021 | −2.48 |
| Establishments with 100+ workers (% of jobs within ~5 km) | 0.036 | 3.33 | 0.045 | 3.93 | 0.031 | 2.33 |
| ***Village / town, Census 2011 and SECC 2011–12*** | | | | | | |
| SC / ST (% of people) | −0.009 | −3.25 | −0.007 | −1.95 | −0.011 | −3.32 |
| Agricultural workers (% of workers) ⚠ | 0.005 | 2.34 | 0.004 | 1.13 | 0.006 | 2.66 |
| Households with a two- or three-wheeler (%) | 0.007 | 2.16 | 0.011 | 2.63 | 0.003 | 0.98 |
| ***Assembly constituency (Base: Maheshwaram)*** | | | | | | |
| Rajendranagar | −0.080 | −0.61 | −0.204 | −1.24 | 0.002 | 0.01 |
| Serilingampally | −0.346 | −1.39 | −0.535 | −1.80 | −0.205 | −0.67 |
| ***Period (Base: 2017–2020)*** | | | | | | |
| 2020–2023 | −0.080 | −1.11 | -- | -- | -- | -- |

| | without census factors | **with census factors** |
|---|---|---|
| parameters | 16 | 22 |
| log-likelihood at convergence | −6,646.8 | −6,589.2 |
| ρ² / adjusted ρ² | 0.222 / 0.220 | 0.229 / 0.226 |
| AUC, cross-validated by 4 km tile | 0.824 | 0.825 |
| census factors jointly (robust Wald) | | χ² = 23.8 on 6 df, p = 0.0006 |

**Eliminated:**
- **Census factors:** four-wheeler ownership (t = −0.39), IT share of nearby jobs (−0.50), inside GHMC (0.56), the village's
  own job density (1.01), its population density (−0.89), literacy (1.05).
- **Others:** the same as before (WorldPop, votes, CBD, ORR, metro, night lights, …).
- **Jointly:** all 18 eliminated variables add nothing (p = 0.47).

## Reading it

**The census factors matter as a group,** but they mostly sharpen what the map and distance variables
already capture. AUC barely moves and ρ² rises by 0.007.

**Robust: same sign alone and in the model**

| factor | alone | in the model | in words |
|---|---|---|---|
| Large establishments (% of nearby jobs in firms with 100+ workers) | + (t = 8.8) | +0.036 (t = 3.3) | +10 points → odds × 1.43. Development follows big employers: IT campuses, SEZs, large industry. |
| Manufacturing (% of nearby jobs) | − (t = −3.7) | −0.020 (t = −2.9) | +10 points → odds × 0.82. Older industrial belts attract less new building. |
| SC/ST share of the village | − (t = −6.8) | −0.009 (t = −3.3) | +10 points → odds × 0.91. The Hyderabad analogue of Table 18's % Hispanic (−0.015). One possible Indian-specific reason, **not tested**: assigned land given to SC/ST households cannot legally be sold. |
| Two/three-wheeler households | + (t = 6.3) | +0.007 (t = 2.2) | +10 points → odds × 1.07. Significant in 2017–20 only. Four-wheeler ownership adds nothing. The closest we get to Table 18's zero-vehicle households (+0.021). |

**⚠ Not interpretable one by one (sign flips because of collinearity):**
- **Workers within 5 km:** positive on its own (t = 12.3), the same as Florida's job density. Negative in the full model,
  because it is almost the same variable as road mileage (r = 0.89) and distance to the dense city (r = −0.85),
  with VIF 11. The defensible statement is "job mass and urban form together", not the sign of either alone.
- **Agricultural workers:** negative alone (t = −9.3), positive in the model, for the same reason.

**What stays the same:** every non-census factor keeps its sign and roughly its size. HITEC/FD distance stays
strong (−0.41). So the job data does **not** replace the distance to the job centres: the pull of HITEC/FD is
more than the number of jobs near a cell.

## Caveats

- Trial region only. In GHMC, village values are city-wide averages; ward boundaries would fix that, and the
  Economic Census already has 125 ward codes for Hyderabad district.
- All census data are cross-sections from 2011–13, so they are the same in both periods.
- Jobs are counted where the establishment is: home-based and street businesses are included, but
  establishments missed by the census (common for IT parks in multi-storey buildings) are not.
- The IT share was eliminated (t = −0.50). In this region IT jobs sit only on the Serilingampally side and
  move together with HITEC/FD distance.

## Final specification: Florida-style (`table18_florida/`)

Here job mass enters the way job density does in Table 18. Road mileage and distance to the dense city are
left out of the candidates, because they are near-duplicates of workers within 5 km. The table above, which keeps
them, is the check. Command: `06_table18.py florida`.

| Variable | Estimate | t stat | 2017–20 est. | t | 2020–23 est. | t |
|---|---|---|---|---|---|---|
| Constant | −3.598 | −6.86 | −3.955 | −6.88 | −3.326 | −5.18 |
| ***Land cover of the cell at t−1 (Base: open land)*** | | | | | | |
| Tree cover | −1.096 | −7.51 | −0.931 | −4.67 | −1.278 | −7.51 |
| ***Land use within 1 km (% by area) (Base: open land)*** | | | | | | |
| Water | −0.040 | −2.88 | −0.054 | −2.81 | −0.023 | −1.38 |
| Trees | −0.042 | −7.56 | −0.042 | −6.34 | −0.042 | −5.97 |
| Land-use mix (entropy, 0–1) | 3.123 | 9.59 | 3.428 | 8.60 | 2.799 | 7.37 |
| ***Accessibility*** | | | | | | |
| Ln(km to the airport) | −0.519 | −6.09 | −0.504 | −4.40 | −0.524 | −5.35 |
| Ln(km to HITEC City / Financial District) | −0.362 | −4.18 | −0.371 | −4.23 | −0.357 | −3.18 |
| Ln(km to the nearest major road) | −0.161 | −2.73 | −0.145 | −1.98 | −0.198 | −2.90 |
| ***Supply constraints*** | | | | | | |
| Slope (degrees) | −0.037 | −2.15 | −0.047 | −1.80 | −0.028 | −1.36 |
| Relief within 150 m (m) | −0.071 | −2.48 | −0.087 | −2.23 | −0.058 | −1.60 |
| Within 100 m of a lake | −1.169 | −7.46 | −1.290 | −5.85 | −1.060 | −5.27 |
| Military, forest, protected or airport land | −1.508 | −4.32 | −0.922 | −2.59 | −1.977 | −2.45 |
| ***Jobs, Economic Census 2013*** | | | | | | |
| Manufacturing (% of jobs within ~5 km) | −0.021 | −3.44 | −0.025 | −2.81 | −0.018 | −2.30 |
| Establishments with 100+ workers (% of jobs within ~5 km) | 0.030 | 3.82 | 0.041 | 4.74 | 0.021 | 2.15 |
| ***Village / town, Census 2011*** | | | | | | |
| SC / ST (% of people) | −0.009 | −3.10 | −0.007 | −1.92 | −0.011 | −3.04 |
| ***Assembly constituency (Base: Maheshwaram)*** | | | | | | |
| Rajendranagar | −0.104 | −0.73 | −0.149 | −0.86 | −0.073 | −0.43 |
| Serilingampally | −0.264 | −1.05 | −0.267 | −0.95 | −0.288 | −1.00 |
| ***Period (Base: 2017–2020)*** | | | | | | |
| 2020–2023 | −0.034 | −0.52 | -- | -- | -- | -- |

| | pooled | 2017–20 | 2020–23 |
|---|---|---|---|
| cells (changes) | 19,813 (3,071) | 9,896 (1,521) | 9,917 (1,550) |
| parameters | 18 | 17 | 17 |
| log-likelihood, constant only / at convergence | −8,545.0 / −6,645.2 | −4,246.1 / −3,195.5 | −4,298.8 / −3,424.1 |
| ρ² / adjusted ρ² | 0.222 / 0.220 | 0.247 / 0.243 | 0.203 / 0.200 |
| AUC, cross-validated by 4 km tile | 0.821 | 0.835 | 0.799 |

The 20 eliminated variables jointly add nothing (robust Wald χ² = 25.5 on 20 df, p = 0.18).

**What happened to job density.** Elimination drops workers within 5 km (t = −0.05), so the Florida-style
model does not end up with a job-density row. Checks:

| specification | workers within 5 km | ρ² |
|---|---|---|
| final model + workers within 5 km (kept by force) | +0.002 (t = 0.03) | 0.222 |
| same, without land-use mix | **+0.242 (t = 3.01)**, the Florida sign | 0.200 |
| same, without land-use mix and tree/water shares | +0.299 (t = 3.85) | 0.193 |
| + the village's own job density as well | +0.008 (t = 0.11); village −0.005 (t = −0.18) | 0.222 |

So job mass does what Florida's job density does (positive, t = 3), but only when land-use mix is left out.
Land-use mix, with r = 0.74 to job mass, carries the same signal and explains more (ρ² 0.222 vs 0.200).

**Jobs enter through their *kind*, not their *number*:**
- more large employers nearby → more development (+10 points → odds × 1.35);
- more manufacturing nearby → less (+10 points → odds × 0.81).

**Robustness across specifications:**
- **Stable:** SC/ST share, the airport, HITEC/FD and all the supply constraints keep their sign and size in all
  three versions (no census / census / Florida-style).
- **Dropped here:**
  - two-wheeler ownership and agricultural workers: once road mileage and the dense-city distance are gone,
    they lose significance (t = 1.6 and 1.25);
  - metro: just misses (t = −1.88).

Collinearity is worst in this small region. The full HMDA run is the place to settle whether job mass, road
mileage and land-use mix can be told apart.
