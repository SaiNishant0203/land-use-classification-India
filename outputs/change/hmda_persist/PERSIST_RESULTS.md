# Change model, all of HMDA, with the persistence outcome (11 November 2026)

**Not for sharing yet.** This run answers "what if change is counted from our map's persistence instead of
needing Open Buildings too?" (results log #53, #54). It doesn't settle which outcome is right; the 60-cell
eyeball check does.

## 1. The three ways of counting change

Rates are the share of open land (map trees/open, Open Buildings cover < 5% at the start), all of HMDA.

| outcome | rule | 2017–20 | 2020–23 | signs of the factors |
|---|---|---|---|---|
| **strict** (#52) | map built at t1 **and** Open Buildings cover ≥ 20%, 3×3 gain ≥ 0.10 | 0.23% | 0.22% | sensible |
| **persistence** (this run) | map built in **both** t1−1 and t1 | **1.44%** | **1.40%** | several odd (below) |
| middle (not run yet) | persistence **and** Open Buildings shows some gain (3×3 ≥ 0.05) | about 0.53% | about 0.47% | sensible (§3) |

**How well do the persistence changes last?**
- Of the 2017–20 persistence changes, 87.5% are still built in 2023, and 78.7% are built in every year
  2021–23.
- Of the cells counted as unchanged, 2.7% get built later.
- Cells left out (sources disagree): 1.8% and 4.5%.

## 2. Table 18, persistence outcome (all 35 candidates, backward elimination to |t| ≥ 1.96)

| Variable | Estimate | t stat | 2017-20 est. | t | 2020-23 est. | t |
|---|---|---|---|---|---|---|
| Constant | -5.310 | -12.10 | -6.316 | -11.64 | -4.344 | -9.27 |
| ***Land use within 1 km (% by area) (Base: open land)*** | | | | | | |
| Residential | 0.025 | 11.90 | 0.018 | 7.15 | 0.031 | 13.31 |
| Non-residential | 0.022 | 11.12 | 0.016 | 7.01 | 0.028 | 11.77 |
| Water | -0.058 | -8.55 | -0.054 | -7.31 | -0.061 | -6.89 |
| Trees | -0.044 | -13.32 | -0.044 | -11.99 | -0.043 | -10.67 |
| Land-use mix (entropy, 0-1) | 5.089 | 25.56 | 5.314 | 23.82 | 4.856 | 20.52 |
| ***Urban form*** | | | | | | |
| Ln(km to the dense city, 1 km built share >= 40%) | 0.141 | 6.62 | 0.111 | 4.04 | 0.174 | 7.06 |
| Ln(night lights within 1 km) | -4.055 | -8.08 | -4.498 | -6.68 | -3.745 | -7.22 |
| ***Accessibility*** | | | | | | |
| Ln(km to the airport) | -0.122 | -2.47 | -0.136 | -2.51 | -0.110 | -2.01 |
| Ln(km to the old CBD) | -0.552 | -4.35 | -0.473 | -3.14 | -0.581 | -4.37 |
| Ln(km to the nearest ORR interchange) | -0.111 | -3.85 | -0.103 | -3.10 | -0.125 | -3.59 |
| Ln(km to the nearest major road) | -0.168 | -9.79 | -0.152 | -7.98 | -0.185 | -9.07 |
| Road mileage in the 4 km x 4 km window (10 km) | -0.030 | -5.16 | -0.029 | -3.88 | -0.029 | -4.73 |
| ***Supply constraints*** | | | | | | |
| Slope (degrees) | 0.085 | 11.05 | 0.094 | 9.47 | 0.076 | 8.02 |
| Relief within 150 m (m) | -0.094 | -9.80 | -0.095 | -7.37 | -0.092 | -7.67 |
| Ln(km to a lake >= 2 ha) | 0.047 | 2.08 | 0.049 | 1.75 | 0.043 | 1.67 |
| Within 100 m of a lake | -0.852 | -14.99 | -0.984 | -12.83 | -0.731 | -10.45 |
| ***Population*** | | | | | | |
| Ln(WorldPop people per km2) | 0.275 | 7.23 | 0.421 | 9.04 | 0.135 | 3.21 |
| ***Jobs, Economic Census 2013*** | | | | | | |
| Establishments with 100+ workers (% of jobs within ~5 km) | 0.004 | 3.27 | 0.004 | 2.41 | 0.005 | 3.19 |
| ***District (Base: Rangareddy)*** | | | | | | |
| Medak | 0.285 | 5.69 | 0.325 | 5.28 | 0.232 | 3.89 |
| Nalgonda | 0.224 | 3.59 | 0.217 | 2.82 | 0.215 | 3.07 |
| Mahabubnagar | 0.343 | 3.70 | 0.493 | 4.50 | 0.190 | 1.98 |
| Hyderabad | -0.202 | -1.34 | -0.327 | -1.74 | -0.043 | -0.29 |
| ***Period (Base: 2017-2020)*** | | | | | | |
| 2020-2023 | 0.154 | 6.87 | -- | -- | -- | -- |

| | pooled | 2017-20 | 2020-23 |
|---|---|---|---|
| cells | 120,000 | 60,000 | 60,000 |
| changes | 54,598 | 25,564 | 29,034 |
| rho-squared | 0.292 | 0.298 | 0.286 |
| AUC, cross-validated by 4 km tile | 0.849 | 0.852 | 0.845 |

The 17 eliminated variables together: p = 0.29.
- Eliminated, among others: tree cover on the cell (t 1.63), HITEC/FD (−1.19), restricted land (−0.35),
  jobs within 5 km (0.05), metro (0.35).
- Variants: Florida-style ρ² 0.291, AUC 0.849; without census ρ² 0.292, AUC 0.849.

**Odd signs:**
- Steeper land gets built **more** (slope +0.085).
- Being farther from the dense city **raises** the odds (+0.141).
- Night lights strongly **lower** them (−4.06).
- Tree cover on the cell no longer matters, where in the strict run its odds were 0.33.
- Restricted land no longer matters.

## 3. Where the odd signs come from

The final specification plus tree cover, fitted three ways:
- all persistence changes;
- only those where Open Buildings shows some gain (3×3 ≥ 0.05; 20% of the sampled changes);
- only those where it shows none (80%).

Each is fitted against the same unchanged cells. Estimate, t in brackets.

| factor | all persistence changes | with an Open Buildings gain | without one |
|---|---|---|---|
| tree cover on the cell | 0.058 (1.6) | **−0.885 (−14.3)** | **+0.184 (5.1)** |
| ln km to the dense city | 0.140 (6.6) | **−0.122 (−3.7)** | **+0.195 (9.2)** |
| slope | 0.084 (11.1) | 0.020 (1.7) | **0.095 (12.2)** |
| ln night lights | −4.03 (−8.1) | −1.30 (−2.1) | −4.59 (−9.1) |
| ln WorldPop | 0.274 (7.2) | 0.022 (0.4) | 0.314 (8.3) |
| residential within 1 km (per point) | 0.025 (11.9) | 0.007 (2.5) | 0.029 (13.6) |
| road mileage in 4 x 4 km | −0.030 (−5.2) | 0.010 (1.4) | −0.037 (−6.4) |
| Hyderabad district | −0.207 (−1.4) | −0.971 (−5.6) | −0.008 (−0.1) |
| land-use mix | 5.09 (25.5) | 4.05 (18.4) | 5.18 (24.9) |
| within 100 m of a lake | −0.85 (−15.0) | −0.96 (−10.6) | −0.81 (−13.7) |
| ln km to the old CBD | −0.55 (−4.4) | −0.51 (−2.9) | −0.49 (−4.1) |
| ln km to the ORR | −0.11 (−3.9) | −0.19 (−5.1) | −0.08 (−2.8) |
| ln km to a major road | −0.17 (−9.8) | −0.15 (−5.6) | −0.16 (−9.5) |
| fit (ρ² / AUC) | 0.292 / 0.849 | 0.277 / 0.857 | 0.289 / 0.850 |

**What this shows:**
- **The odd signs come entirely from map changes with no building in Open Buildings.** These are
  more often trees at the start (18.6% vs 6.4%), on steeper ground (slope 2.45° vs 2.00°), and a little
  farther from the dense city (1.33 vs 1.00 km).
- **But they are not out in the countryside.** Their mix, WorldPop and road density are like the supported
  changes, and far above the unchanged cells.
- **What could they be?** Three possibilities, and the eyeball check decides between them:
  - plotted layouts or cleared land with no houses yet (real land conversion);
  - tree-shaded houses the classifier is unsure about;
  - rock or bare ground read as built.
- **The middle outcome looks sensible:** persistence plus a small Open Buildings gain gives the expected
  signs. Tree cover is negative, distance to the city negative, slope near zero.
- **Factors that hold under every outcome:**
  - land-use mix;
  - trees and water within 1 km;
  - within 100 m of a lake;
  - distances to the old CBD, the ORR and a major road;
  - relief;
  - share of jobs in big establishments.

## 4. How much do the factors add? (`added_value/ADDED_VALUE.md`)

| model | ρ² | AUC | loss when left out (ρ² / AUC) |
|---|---|---|---|
| period and district dummies | 0.029 | 0.597 | |
| + distance to the dense city | 0.186 | 0.775 | |
| + land use within 1 km, from our map (shares, mix) | 0.275 | 0.843 | |
| + accessibility | 0.285 | 0.846 | |
| + supply constraints | 0.290 | 0.849 | |
| + jobs and census | 0.292 | 0.849 | |
| final without distance to the dense city | 0.291 | 0.849 | 0.001 / 0.000 |
| final without land use within 1 km | 0.221 | 0.805 | 0.072 / 0.044 |
| final without accessibility | 0.285 | 0.847 | 0.007 / 0.002 |
| final without supply constraints | 0.287 | 0.847 | 0.005 / 0.002 |
| final without jobs and census | 0.290 | 0.849 | 0.002 / 0.000 |
| final without dense-city distance **and** land use within 1 km | 0.212 | 0.802 | 0.080 / 0.047 |

- **Almost all of the fit is "near existing development".** That covers distance to the city and land use
  within 1 km, both from our own map.
- **Accessibility, terrain and census together add about 0.006 of AUC.** That's the same pattern as the
  strict run, where they added 0.018 after tree cover.
- **Many of the t-values above are large** only because the sample has 120,000 cells.

## 5. Tests

| | strict (#52) | persistence |
|---|---|---|
| temporal transfer AUC (fit 2017–20, predict 2020–23) | 0.834 | 0.840 |
| Moran's I of residuals, 8 nearest | 0.197 / 0.188 | 0.138 / 0.128 |
| slopes differ between periods (Wald) | χ² 77.0 | χ² 196.2 |
| road km added during the period | z = 7.9 | p < 0.001 |
| GO 111 × 2020–23 | p = 0.19 | p = 0.12 |

Subregions (`consistency/`): AUC 0.825 in the trial ACs, 0.851 elsewhere, and 0.68 inside 20 km of the CBD,
again the weakest.

## 6. Next

1. **The eyeball check** (60 cells; 40 of them are map-only changes with no Open Buildings gain within
   70 m). Its result decides:
   - mostly layouts / cleared land → use persistence, and treat "layout" as real conversion (or a third
     outcome, as Florida's partial conversion);
   - mostly houses → use persistence;
   - mostly noise or rock → use the middle outcome.
2. Then rerun once with the chosen outcome. That takes about 20 minutes.
3. **The factors stay the weak point under every outcome:** beyond "near existing development", the model
   needs real supply and policy data. That means master-plan zoning (the 30 district maps on OpenCity,
   JPEG only), layout approvals and land values.

**Files:**
- results: `outputs/change/hmda_persist/{table18_census,table18_florida,table18,consistency,full,added_value}/`
- data: `data/processed/change/hmda_persist_cells*.parquet`
- run: `OUTCOME=persist` on every script in `scripts/change/`
