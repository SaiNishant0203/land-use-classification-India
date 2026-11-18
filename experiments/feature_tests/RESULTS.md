# New-factor tests on the HMDA change model (18 Nov 2026)

**Question:** do new, leakage-free factors add to the final HMDA specification (`06_table18.py census`),
under both change rules?

**How:** `harness.py` adds each candidate to the final specification of each rule and reports:
- coefficient and t-value, using the same estimator as `06` (cluster-robust by 4 km tile);
- per-period estimates;
- the robust Wald test;
- Δρ²;
- ΔAUC, 5-fold cross-validated by tile;
- ΔAUC for transfer from 2017–20 to 2020–23.

Every factor is dated at or before t0. The samples are the 120,000-cell HMDA samples already in git:
12,314 changes under the strict rule and 54,598 under the persistence rule.

## Results

| candidate | source, dating | strict: coef (t) | persistence: coef (t) | Δ AUC cv (strict / persist) | verdict |
|---|---|---|---|---|---|
| **network time to old CBD** (ln min) | OSM roads as mapped at end of t0 (Geofabrik 2018-01-01 / 2021-01-01), free-flow speeds | −1.42 (−5.7) | −1.52 (−8.9) | +0.0013 / +0.0004 | **keep**: same sign in both rules and both periods, improves transfer |
| network time to nearest ORR interchange | same | −0.35 (−2.5) | −0.61 (−7.9) | +0.0004 / +0.0006 | keep as a swap for straight-line ORR distance (below) |
| network time to HITEC / FD | same | ns | −0.18 (−2.9) | 0 / 0 | drop (as straight-line HITEC was) |
| **swap**: network times in place of straight-line CBD and ORR distances | same | ρ² 0.2360 → 0.2375, AIC −118 | ρ² 0.2922 → 0.2947, AIC −408 | +0.0009 / +0.0006 | **better on every measure with the same number of parameters** |
| **lagged momentum**: % of 1 km window changed in 2017–20 (2020–23 only) | own maps, previous period | +0.199 (+6.2) | +0.020 (+2.7) | +0.0045 / +0.0002 | **keep for 2020–23**; the strongest single addition under the strict rule |
| **distance to village core**: nearest govt / local-body school est. before t0 | UDISE+ (year of establishment) | **+0.25 (+5.0)** | **−0.46 (−13.0)** | +0.0007 / +0.0018 | **sign flips between rules** (see below) |
| distance to nearest polling station (2017) | ECI polling stations, April 2017 | **+0.41 (+8.6)** | **−0.25 (−8.2)** | +0.0024 / 0.0000 | same flip; a second, independent village-core proxy |
| polling stations within 1 km (2017) | same | −0.026 (−7.3) | −0.017 (−5.8) | +0.0012 / +0.0007 | keep: denser settled land gets less new building on its open land |
| OSM amenities / shops / offices within 1 km | OSM at t0 | −0.27 (−4.6) | −0.18 (−3.9) | +0.0010 / +0.0001 | weak; OSM mapping completeness is uneven, so not recommended |
| OSM distance to school / clinic | OSM at t0 | ns | ns | 0 | drop |
| UDISE schools / private schools within 2 km, new private schools | UDISE+, est. before t0 | ns | ns | 0 | drop |
| inside the ORR | ORR interchanges (fixed) | ns | −0.13 (−1.9) | 0 | drop |

**All the kept factors together** (network CBD and ORR time, village-core distance, polling-station density),
in both periods:
- strict: Wald χ² 113 on 4 df, Δρ² +0.006, ΔAUC cv +0.003, ΔAUC transfer +0.003;
- persistence: χ² 251, Δρ² +0.010, ΔAUC +0.003.

Adding lagged momentum (2020–23 only): strict Δρ² +0.011, ΔAUC +0.007.

## What it means

1. **Network accessibility should replace straight-line distances.** It is the one clear, rule-independent
   improvement.
2. **The gains are small**, like every factor group so far (report §8). "Next to existing development" still
   carries most of the prediction, so new factors matter for *explanation*, not for AUC.
3. **The village-core flip is evidence for the change-rule question.**
   - Changes confirmed by Open Buildings (strict rule) lie *away* from village cores: greenfield layouts.
   - Map-only changes (persistence rule) lie *near* village cores.
   - That pattern fits either (a) real village extension that Open Buildings misses, because small rural
     houses are hard to see, or (b) classifier noise around villages.
   - The eyeball check can tell these apart: look at whether map-only cells near villages are B / C or N.

## Earth Engine factors (subsample)

All from the year before the period (2016 / 2019) or fixed geography. Random subsample: 25,000 cells
(2017–20) and 10,000 cells (2020–23) drawn over both samples; about 17,600 cells per rule. Extraction was
cut short by the Earth Engine non-commercial quota, so the intervals are wider than in the tests above.

**One by one**, cropland probability (strict ΔAUC +0.006, persistence +0.023) and NDVI amplitude (+0.007 /
+0.005) looked like the biggest gains so far.

**But most of that is "Dynamic World already sees this cell as built".** Dynamic World's *built*
probability in t0−1 is not an explanatory factor. It means development or a map error had already started
before the period. Added alone to the base model it gives:

| | strict | persistence |
|---|---|---|
| coefficient (t) | +3.6 (t 13.8) | +9.0 (t 32) |
| ΔAUC | +0.023 | +0.067 |

The cells that drive the persistence rule are largely cells Dynamic World already called partly built a
year before the period. That points to start-state map errors or construction already under way, and is
more evidence for the change-rule question.

**With Dynamic World built and trees probability as controls** (`ee_control.py`, `ee_control.csv`):

| factor | strict: coef (t), 17–20 \| 20–23 | persistence: coef (t) | ΔAUC cv / transfer (strict) | verdict |
|---|---|---|---|---|
| bare-ground probability | **+5.2 (+5.6)**, +5.1 \| +4.4 | **+4.2 (+5.5)** | +0.002 / +0.003 | **keep**: barren land converts more, in both rules and both periods |
| NDVI amplitude (cropping intensity) | **−2.0 (−5.9)**, −1.5 \| −2.7 | −0.6 (−2.3) | +0.002 / +0.004 | **keep**: actively cropped land converts less |
| height above drainage (ln) | +0.09 (+2.1) | **+0.24 (+7.3)** | +0.001 / +0.001 | keep (weak): low-lying, flood-prone land is built less (Florida flood-zone analogue) |
| cropland probability | −1.6 (−3.6), −2.0 \| −0.8 | −1.6 (−4.9) | +0.001 / 0 | weak once controlled; largely overlaps NDVI amplitude |
| scrub probability | +2.1 (+4.8), unstable by period | +1.6 (+5.2) | +0.001 / −0.003 | drop (fails transfer) |
| grass, dry-season NDVI, water history 250 m | small or unstable | | ≈ 0 | drop |

**Reading.** What kind of open land a cell is matters: barren land is built, cropped land isn't. Our map
lumps these together as "other open". The useful, defensible additions are **bare-ground probability**,
**NDVI amplitude** and **height above drainage**. Each adds about 0.001–0.004 AUC, like the other factor
groups.

## Not tested yet

**Open-patch size**, the analogue of Florida's ln parcel area and the strongest factor in every Florida
table. It needs the full maps.

## Reproduce

```
python experiments/feature_tests/build_local.py      # polling stations, OSM POIs, lagged momentum, inside ORR
python experiments/feature_tests/build_udise.py      # needs data/raw/udise/telangana_schools.csv (India Data Portal API)
python experiments/feature_tests/build_network.py    # needs data/raw/osm_snapshots/india-180101 and -210101 .osm.pbf; pip install osmium
python experiments/feature_tests/harness.py experiments/feature_tests/feat_<x>.parquet [columns]
python experiments/feature_tests/combined.py
EE_PROJECT=<your project> python experiments/feature_tests/build_ee.py        # N_SUB cells per period; quota-limited
python experiments/feature_tests/build_ee_built.py && python experiments/feature_tests/ee_control.py
```
