# Trial run, full model: what drives land-use change, and how we test it

*5 Nov 2026. Same sample as `TRIAL_RESULTS.md`: 3 constituencies (Maheshwaram, Rajendranagar,
Serilingampally), 1,164 km², 20,000 cells, 3,071 confirmed changes over 2017→20 and 2020→23 (19,813 cells
after dropping 187 at the grid edge). Code: `scripts/change/04_more_factors.py` (factors),
`05_full_logit.py` (models and tests). Tables: `full/*.csv`.*

## Answer in short

All 25 factors in one binary logit (cross-validated AUC 0.818, McFadden R² 0.23; the earlier base model had
0.805 and 0.19). Four mechanisms each matter on their own. Population does not.

| rank | mechanism | does it matter? (robust Wald test) | unique contribution: AUC lost when dropped | the factors that carry it |
|---|---|---|---|---|
| 1 | **neighbourhood**: land use nearby | yes, p < 0.001 | −0.014 | land-use mix (+), tree share nearby (−), distance to the dense city (−) |
| 2 | **supply constraints** | yes, p < 0.001 | −0.007 | lake edge (−), military, forest or airport land (−), slope and boulders (−) |
| 2 | **land at the start** | yes, p < 0.001 | −0.007 | trees convert at a third of the odds of open land |
| 4 | **access** | yes, p < 0.001 | −0.006 | airport (−), HITEC/FD (−), major road (−), metro (− in 2020–23) |
| – | **people** (votes, WorldPop) | **no**, p = 0.79 | **+0.003** (the model gets better without them) | none |

**Groups overlap.** Each group on its own reaches AUC 0.73–0.80 and all of them together 0.82, so most of
the signal is shared: "on the edge of the growing city". Every factor is measured at the start of the period, so these are
*predictive* associations. §4 shows which tests push them towards causes, and how far they go.

## 1. The factors, pooled model

"Twice as far" is the odds ratio for doubling the distance. **AME** is the average marginal effect: the
change in the 3-year probability of development, in percentage points, against an average of **0.42%**.
For a yes/no factor it is 1 vs 0; for others it is +1 SD. Standard errors are clustered by 4 km tile.

| factor | coef | p | in words | AME (pp) |
|---|---|---|---|---|
| **Land at the start** | | | | |
| trees (vs open) | −1.14 | < 0.001 | odds × 0.32 | −0.32 |
| **Neighbourhood** | | | | |
| land-use mix in 1 km (entropy, 0–1) | +2.15 | < 0.001 | +0.1 → odds × 1.24. Largest effect of the continuous factors | **+0.25** |
| tree share in 1 km | −3.42 | < 0.001 | +10 points → odds × 0.71 | −0.15 |
| ln km to the dense city (1 km built ≥ 40%) | −0.34 | < 0.001 | twice as far → odds × 0.79: **edge growth, not leapfrogging** | −0.17 |
| residential / non-residential share in 1 km | −0.56 / −0.30 | 0.24 / 0.49 | not significant once mix and edge distance are in. The earlier "built share" effect was this. | |
| water share in 1 km | −2.61 | 0.06 | | |
| night lights | −0.64 | 0.50 | nothing | |
| **Access** | | | | |
| ln km to airport | −0.52 | < 0.001 | twice as far → odds × 0.70 | −0.11 |
| ln km to HITEC City / Financial District | −0.40 | 0.02 | twice as far → odds × 0.76. Weaker in 2020–23 (§3) | −0.12 |
| ln km to major road | −0.16 | 0.02 | twice as far → odds × 0.90 | −0.06 |
| ln km to open metro station | −0.30 | 0.07 | twice as far → odds × 0.81. Significant in 2020–23 only (p = 0.04) | −0.08 |
| ln km to ORR interchange | −0.11 | 0.26 | not significant once the city edge is in (it was p = 0.06 in the base model) | |
| ln km to old CBD | +0.29 | 0.52 | nothing; collinear (§3) | |
| major-road km in 4 × 4 km | −0.08 | 0.42 | nothing beyond distance to a major road | |
| minor-road km in 4 × 4 km | +0.34 | 0.08 | follows development rather than leading it (§4) | +0.12 |
| **Supply constraints** | | | | |
| within 100 m of a lake (≥ 2 ha) | −1.29 | < 0.001 | odds × 0.28. All of it is within 50 m of the water (raw rate 0.06% vs about 0.5% further out). See §4. | −0.32 |
| military, forest, protected or airport land (OSM) | −1.58 | < 0.001 | odds × 0.21. Raw rate 0.07–0.14% vs 0.4% | −0.34 |
| slope (degrees) | −0.04 | 0.03 | +1° → odds × 0.96 | −0.03 |
| relief within 150 m (boulders, rock) | −0.06 | 0.045 | +1 m → odds × 0.94 | −0.04 |
| elevation, distance to a lake | | 0.94, 0.43 | nothing | |
| GO 111 zone (stand-in) | +0.23 | 0.13 | see §4: the stand-in is not good enough | |
| **People** | | | | |
| ln votes per km² (2018 booths) | −0.06 | 0.53 | nothing | |
| ln WorldPop per km² | 0.00 | 1.00 | nothing | |

## 2. The tests, and what each one found

| # | test | question it answers | result |
|---|---|---|---|
| 1 | **Wald z per coefficient**, cluster-robust (4 km tiles) | Does this factor matter holding all others fixed? | table above |
| 2 | **Wald χ² per group**, cluster-robust | Does the mechanism as a whole matter? Safer than single coefficients when the factors are correlated. | all four mechanisms p < 0.001 in both periods; people p = 0.40 (2017–20), 0.46 (2020–23) |
| 2b | likelihood-ratio test per group | the same, assuming independent cells | People "p = 0.003" in 2020–23. **Too optimistic.** Neighbouring cells aren't independent (test 7), which is why the robust Wald test is the one to report. |
| 3 | **Cross-validated AUC**, 5 folds by 4 km tile: group alone, and full model without the group | How much does each group predict on its own, and what does it add that the others don't? Cells from the same tile are never split between training and test. | full 0.818; AC + period only 0.605; alone: neighbourhood 0.80, access 0.78, people 0.78, constraints 0.73, start 0.64; loss when dropped: see the top table |
| 4 | **Odds ratio per SD and average marginal effect** | How large is the effect, in a unit everyone understands (percentage points of the 3-year probability)? | the AME column |
| 5 | **Variance inflation factors** | Are single coefficients trustworthy, or are factors standing in for each other? | **distance to the CBD 19–20, metro 12–17, HITEC 12–13, WorldPop 13, minor-road km 10–11.** The three distances are almost the same variable in this small region, so read them as a group (test 2), not one by one. All others < 8. |
| 6a | **Chow test**: all slopes × period | Are the effects the same in 2017–20 and 2020–23? | No: χ² 81.7 on 27 df, p < 0.001. HITEC pull weaker in 2020–23 (−0.57 → −0.19), built shares and elevation flip sign, GO 111 up (+0.0 → +0.59) |
| 6b | **Temporal transfer**: fit on 2017–20, predict 2020–23 | Does the model capture lasting drivers, or just one period? | AUC 0.809, as good as 2020–23's own cross-validated 0.797. **Where change happens is stable**; how strongly each factor pulls shifts somewhat. |
| 7 | **Moran's I of residuals** (8 nearest sampled cells, about 0.5 km) | Is there spatial pattern the model misses? | I = 0.15, p = 0.005 in both periods. Unexplained change is clustered within about 500 m (layouts, projects), which is why the standard errors are clustered by 4 km tile and the cross-validation is by tile |
| 8 | **Calibration** by decile of predicted probability | Are the predicted probabilities right in absolute terms? | Close from deciles 1–9 (e.g. 1.34% predicted vs 1.50% observed). Top decile over-predicted: 2.5% vs 2.0% |
| 9 | causal-direction checks | §4 | |

## 3. What the collinearity means

The single coefficients for HITEC, the CBD and the metro shift between specifications. In a 1,164 km²
region south-west of the city, "far from the CBD", "far from the metro" and "far from HITEC" are almost the same
thing (VIF 12–20). Two things are robust:

- the access group as a whole (p < 0.001);
- the airport effect, which runs in a different direction and is significant in every specification.

The same applies to built share. Once land-use mix and distance to the dense city are in, the residential and
non-residential shares are no longer significant: they were measuring "near the edge of the city".

## 4. From correlation to cause: the checks

A logit with factors measured at the start gives "places with X developed more". Each check below tests
one way that reading could be wrong.

1. **Do roads cause development, or follow it?** Add the road km *added during the period* in the 4 × 4 km window.
   It is the strongest single variable we have tried: z = 6.4, odds × 1.23 per SD. Roads and development
   arrive together, mostly as the internal roads of new layouts. The start-year minor-road km goes **up**
   (+0.34 → +0.49) because it picks up areas where layouts were already being laid out.
   - **Conclusion:** minor-road km is not a cause. Distance to a major road (decided years ahead) is the
     defensible road variable.
   - **Caveat:** OSM mapping effort also grows over time.
2. **Contagion: does change in the previous period predict change now?** The share of the 1 km window
   developed in 2017–20, added to the 2020–23 model: positive, odds × 1.10 per SD, p = 0.06. It is weak once the
   neighbourhood is in.
3. **Lakes.** The negative effect is all within 50 m of the 2023 water spread, i.e. mostly the tank bed
   that was dry at the start. This fits the ban on building below the full-tank level, but it is also land
   that floods. The two can't be separated without the official FTL maps. Distance to a lake beyond 50 m
   doesn't matter.
4. **GO 111 (natural experiment).** Building around Osman Sagar and Himayat Sagar was restricted until the
   order was repealed in April 2022, inside our second period. A real effect should show as a rise in the
   zone after 2022 compared with outside.
   - **Raw rates:** in the zone 0.65% → 0.77%; outside 0.26% → 0.26%.
   - **Per-period coefficient:** 0.0 → +0.59 (p = 0.01).
   - **But:**
     - the pooled difference-in-differences term (zone × 2020–23) is +0.10, p = 0.57;
     - our zone is a stand-in, everything within 10 km of the two lakes. It probably takes in fast-growing
       areas that were never in the 84 notified villages, which is why the zone changes 2.5× *more* than
       outside even while the restriction was in force.
   - **Not conclusive.** The fix is the GO's village list plus Census 2011 village boundaries. It is the most
     promising causal test here, because the repeal is a policy change that development didn't cause.
5. **Timing.** All factors are measured at t0. Population is the exception for 2017–20, where the 2018
   votes fall mid-period; it is null in both periods anyway.
6. **Temporal transfer** (test 6b) is the out-of-sample version: drivers estimated on 2017–20 rank 2020–23's
   changes as well as a model fitted on 2020–23.

**What we can say:** development in these three constituencies is edge growth into open, flat, unrestricted land in
mixed neighbourhoods. It is pulled towards the airport and the HITEC/FD side and towards major roads, and held back
by trees, lake beds, military and forest land, and rough terrain.

**What we can't say yet:**
- that any one access factor *causes* change rather than standing in for the others;
- that roads come first;
- that the GO 111 repeal did anything.

## 5. Next steps (none of them started)

1. **GO 111 village boundaries** (Census 2011 village shapefile, SHRUG or datameet, plus the 84 names in the
   GO): a real difference-in-differences test around the 2022 repeal.
2. **The whole of HMDA**, not three constituencies. Distances then stop being collinear (city-wide
   variation), and the ORR and metro effects can be told apart.
3. **Drop the CBD distance** (VIF 20, never significant) or replace the three distances with network travel
   time to jobs (CHANGE_MODEL_PLAN.md §5).
4. **The eyeball check** of the 60 cells is still outstanding: it validates the change definition everything
   here rests on.

## Compute

Factor extraction about 15 minutes (reading the OSM files dominates; restricted-land polygons are cached in
`data/processed/change/osm_constraints_*.gpkg`); terrain point sampling in Earth Engine about 1.5 minutes;
all models and tests under 2 minutes.
