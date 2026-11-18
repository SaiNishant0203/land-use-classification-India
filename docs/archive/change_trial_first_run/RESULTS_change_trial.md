# Experiment: what makes undeveloped land get built? First change-model run

**Question.** Of the land that was open or tree-covered in 2017 (or 2020), which cells were built
on three years later, and which factors explain that? Prof. Eluru's template is Table 18 of his reference
report: a binary logit of land-use change (change vs no change) for vacant land, with every factor measured
before the change. This is the first run of that model on our 20 m maps.

**Why.** The land-use maps say *where* land changed. For the transport paper we need to know *why*:
access (airport, job centres, roads, ORR, metro), the neighbourhood, land that can't be built on, and
population. It also tests Prof.'s idea of booth-wise voter counts as a population measure.

## Result

- **The model separates land that got built from land that didn't well:** cross-validated AUC 0.82,
  McFadden ρ² 0.22. AUC 0.82 means a randomly picked built-on cell scores higher than a randomly picked
  unchanged one 82% of the time.
- **Four kinds of factor each matter on their own** (joint test per group, p < 0.001 for each): the land use
  nearby, land that can't or may not be built on, the land cover of the cell itself, and access. **Population
  does not** (p = 0.79), neither booth-wise 2018 votes nor WorldPop.
- **Development is edge growth into open, flat, unrestricted land:**
  - **Pull factors:**
    - mixed land use within 1 km (+0.1 → odds × 1.21);
    - close to the airport and to HITEC City / Financial District (twice as far → × 0.70 and × 0.72);
    - close to the dense city (× 0.81) and to a major road (× 0.91);
    - more road mileage in the 4 × 4 km window (+100 km → × 1.24).
  - **Held back by:**
    - tree cover (× 0.31);
    - lake beds within 100 m of the water (× 0.28);
    - military, forest, protected or airport land (× 0.21);
    - slope and rocky ground.
- **Not significant once the above are in:** distance to the ORR, metro and old CBD, night lights,
  WorldPop and booth votes.
- **The pattern holds over time:** a model fitted on 2017–20 predicts 2020–23 as well as one fitted on
  2020–23 itself (AUC 0.81 vs 0.80). The sizes of the effects do shift (Chow test p < 0.001).
- **Roads come partly *with* development, not before it.** Road km added *during* the period predicts that
  period's change even more strongly (z = 6.4): new layouts bring their own roads. So road mileage is
  partly a consequence, and distance to a major road is the safer road variable.

All odds ratios have 95% intervals in §1. Standard errors are clustered by 4 km tile, because
neighbouring cells are not independent.

## 1. Final model, Table 18 layout (pooled 2017–20 and 2020–23)

Backward elimination from 24 candidates, dropping the least significant one at a time until every
|t| ≥ 1.96. Constituency and period dummies are kept as controls. 19,813 cells, 3,071 changes.

| variable | estimate | t | odds ratio [95% CI] | unit |
|---|---|---|---|---|
| ***Land cover of the cell at the start (base: open)*** | | | | |
| tree cover | −1.162 | −7.88 | 0.31 [0.23, 0.42] | trees vs open |
| ***Land use within 1 km*** | | | | |
| trees (% of area) | −0.029 | −5.90 | 0.75 [0.68, 0.83] | +10 points |
| land-use mix (entropy, 0–1) | 1.893 | 5.65 | 1.21 [1.13, 1.29] | +0.1 |
| ***Urban form*** | | | | |
| ln km to the dense city (1 km built share ≥ 40%) | −0.300 | −4.00 | 0.81 [0.73, 0.90] | twice as far |
| ***Access*** | | | | |
| ln km to the airport | −0.507 | −5.15 | 0.70 [0.62, 0.80] | twice as far |
| ln km to HITEC City / Financial District | −0.480 | −4.68 | 0.72 [0.62, 0.82] | twice as far |
| ln km to the nearest major road | −0.132 | −2.23 | 0.91 [0.84, 0.99] | twice as far |
| road mileage in the 4 × 4 km window (per 10 km) | 0.021 | 2.21 | 1.24 [1.02, 1.50] | +100 km |
| ***Land that can't or may not be built on*** | | | | |
| slope (degrees) | −0.041 | −2.34 | 0.96 [0.93, 0.99] | +1° |
| relief within 150 m (m) | −0.065 | −2.16 | 0.94 [0.88, 0.99] | +1 m |
| within 100 m of a lake | −1.284 | −8.96 | 0.28 [0.21, 0.37] | yes vs no |
| military, forest, protected or airport land | −1.551 | −4.21 | 0.21 [0.10, 0.44] | yes vs no |
| ***Controls*** | | | | |
| constituency: Rajendranagar / Serilingampally (vs Maheshwaram) | −0.109 / −0.355 | −0.75 / −1.34 | | |
| period 2020–23 (vs 2017–20) | −0.056 | −0.78 | | |
| constant (corrected for the sampling) | −3.333 | −6.81 | | |

| | pooled | 2017–20 | 2020–23 |
|---|---|---|---|
| cells (changes) | 19,813 (3,071) | 9,896 (1,521) | 9,917 (1,550) |
| ρ² / adjusted ρ² | 0.222 / 0.220 | 0.246 / 0.243 | 0.204 / 0.201 |
| AUC, cross-validated by 4 km tile | 0.824 | 0.838 | 0.803 |

**Eliminated:** WorldPop, elevation, old CBD, ORR, booth votes, distance to a lake, residential and
non-residential share within 1 km, GO 111 zone, metro, water share, night lights. Jointly they add
nothing (p = 0.21).

## 2. Which kind of factor matters? (all 25 factors in one model)

| group | factors | joint test (robust Wald), p | AUC, group alone | AUC lost when the group is dropped |
|---|---|---|---|---|
| land use nearby | shares in 1 km, mix, dense-city distance, night lights | < 0.001 | 0.80 | −0.014 |
| can't / may not build | slope, relief, elevation, lake, restricted land, GO 111 | < 0.001 | 0.73 | −0.007 |
| cell's own land cover | trees vs open | < 0.001 | 0.64 | −0.007 |
| access | airport, ORR, metro, HITEC/FD, CBD, major road, road km | < 0.001 | 0.78 | −0.006 |
| **population** | booth votes 2018, WorldPop | **0.79** | 0.78 | **+0.003** (better without) |

The full model reaches AUC 0.818; constituency and period alone give 0.605. Each group on its own reaches
0.73–0.80 and all of them together 0.82, so most of the signal is shared: "on the edge of the growing city".

## 3. Other tests

| test | question | result |
|---|---|---|
| temporal transfer | does a 2017–20 model predict 2020–23? | AUC 0.81, as good as 2020–23's own 0.80 |
| Chow test | are the effects the same in both periods? | no (p < 0.001); HITEC pull weaker in 2020–23 |
| variance inflation | are single coefficients trustworthy? | CBD / metro / HITEC distances overlap (VIF 12–20); read them as a group |
| Moran's I of residuals | spatial pattern left over? | yes, within about 500 m (I = 0.15); hence errors clustered by tile and CV by tile |
| calibration by decile | are the predicted probabilities right? | close in deciles 1–9; top decile 2.5% predicted vs 2.0% observed |
| roads added during the period | do roads lead or follow? | they follow (z = 6.4); minor roads come with new layouts |
| previous-period change nearby | does change spread? | weakly (odds × 1.10 per SD, p = 0.06) |
| GO 111 repeal (2022) | did lifting the building ban raise change? | inconclusive with the stand-in zone |

## 4. Method

- **Unit and periods:** 20 m cells from our final maps (2017, 2020, 2023); 2017→2020 and 2020→2023, pooled
  with a period dummy.
- **Area:** 3 assembly constituencies: Maheshwaram, Rajendranagar, Serilingampally (1,164 km² inside HMDA).
  They were chosen because booth-wise 2018 votes could be read for them.
- **At risk:** cells undeveloped at the start (map trees or open, Open Buildings cover < 5%): 2.3 M cells.
- **Change = 1** only when two independent sources agree: our map says built at the end **and** Google Open
  Buildings shows a new building (cover ≥ 20%, 3 × 3 gain ≥ 0.10). **Change = 0** when both say still undeveloped.
  The 10–13% where they disagree are left out. Real development is 0.35–0.37% of undeveloped land per 3 years,
  against the ~19% of pixels whose class flips between maps.
- **Sample:** choice-based, at most one cell per 200 m block for each outcome: all changes (about 1,500 per
  period) plus about 8,500 non-changes. The constant is corrected for the sampling (King & Zeng 2001); the
  slopes are unaffected.
- **Factors**, all measured at the start year:
  - **distances:** airport, nearest ORR interchange, nearest open metro station, HITEC/FD, old CBD, nearest
    major road;
  - **road km in the 4 × 4 km window:** dated OSM, Geofabrik snapshots of 1 Jan 2018 and 1 Jan 2021;
  - **neighbourhood:** land-use shares and mix in 1 km, distance to the dense city, night lights (VIIRS);
  - **terrain:** Copernicus DEM, i.e. slope and relief;
  - **constraints:** lakes ≥ 2 ha from the 2023 map; OSM military, forest, protected and airport land;
  - **population:** WorldPop per km², and votes polled per booth from the 2018 Form 20 sheets (OCR, 1,477 of
    1,479 booths) as a kernel density.
- **Estimation:** logit (statsmodels). Standard errors clustered by 4 km tile; 5-fold cross-validation
  grouped by 4 km tile.

## 5. Caveats

- **Trial area only** (3 constituencies, about 15% of HMDA). The distances to CBD, metro and HITEC are almost
  collinear here. The ORR and metro may come back on the full HMDA sample.
- **Booth locations are approximate.** The 2018 booths were renumbered and are placed on 2017
  coordinates, which gives 1.4–3 km noise and pushes the vote effect towards zero. With a wider kernel (2 km)
  votes become significant (p = 0.02), so "no population effect" is not settled.
- **The lake effect is the lake bed itself** (all within 50 m of the water). It fits the full-tank-level
  building ban but is also just land that floods; the two can't be separated without official FTL maps.
- **Associations, not proven causes.** The factors are measured before the change and the
  causal-direction checks help, but no factor here is a natural experiment yet.
- **The change definition** still has to be checked by eye on 60 cells.

## 6. Reproduce

The sample files are in the repo (branch `exp/change-model`), so no raw data is needed:

```
python scripts/change/06_table18.py        # §1, about a minute
python scripts/change/05_full_logit.py     # §2 and §3, about 2 minutes
```

| file | content |
|---|---|
| `scripts/change/02_trial_data.py`, `04_more_factors.py` | build the sample and the factors (need the maps, OSM files, Earth Engine) |
| `data/processed/change/trial_cells_full.parquet` | the 20,000-cell sample with every factor |
| `results/table18.csv`, `results/elimination.csv`, `results/fit.csv` | §1 |
| `results/groups.csv`, `results/coefs_full.csv`, `results/effects.csv` | §2 (all 25 factors, average marginal effects) |
| `results/checks.csv`, `results/calibration.csv` | §3 |
| `outputs/change/trial/FULL_MODEL_RESULTS.md`, `TABLE18_RESULTS.md` | longer write-ups |
