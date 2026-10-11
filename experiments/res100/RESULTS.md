# Experiment: 10 m vs 100 m pixels

**Question:** how much does the land-use classifier change if the unit of analysis is a
100 m × 100 m cell instead of a 10 m pixel?

**Answer in one paragraph.** On OSM-derived labels, going to 100 m costs about **0.07 macro-F1**
(0.898 → 0.829, paired 95% interval −0.075 to −0.062). On the 325-point hand-label test it costs
about 0.02–0.03, and that difference is **not distinguishable from zero** (intervals include 0),
because the test is small. On the hand labels the loss comes almost entirely from **water**;
residential and non-residential F1 do not drop. A full-map prediction is about **130× faster**
(about 20 s vs about 44 min on a 16-thread laptop).

All intervals are 95% bootstrap intervals. Code is in this folder; tables are in `results/`.

---

## 1. What was compared

| | 10 m model (existing) | 100 m model (this experiment) |
|---|---|---|
| unit | 10 m pixel | 100 m cell (10 × 10 pixels) |
| inputs | 76 bands at 10 m | the same 76 bands, block-averaged to 100 m |
| features | 181 (53 non-AlphaEarth) | 173 (45 non-AlphaEarth) |
| neighbourhood windows | 70, 150, 310, 610 m | 300, 500, 700 m (3, 5, 7 cells) |
| training labels | OSM + product agreement, 10 m | the same label tiles, majority class per cell |
| training rows | 393,098 (≤200 px/class/tile) | 102,575 (≤100 cells/class/tile) |
| model | LightGBM, 400 trees, lr 0.05, 63 leaves, 80% rows, 60% columns, balanced | identical |
| spatial CV | 5-fold GroupKFold over 12 km blocks | identical blocks |

Details of the 100 m construction:
- Block means of S2 reflectance, building cover, building count, night lights and the 64 AlphaEarth
  bands over valid pixels. Building height is cover-weighted (`mean(h·cov) / mean(cov)`); maximum
  height is the block maximum.
- Spectral indices (NDVI, NDBI, MNDWI, BSI) are computed from the block-averaged bands.
- Neighbourhood features use mask-aware window means on the 100 m mosaic of all 556 tiles, so there
  are no tile-edge artefacts. The 10 m windows of 70 and 150 m have no 100 m counterpart.
- A cell is a training row if at least 50% of its pixels carry an OSM-derived label. Its label is
  the majority class. Cells within 400 m of a hand-label point are dropped.
- The per-tile cap (100 cells per class) mirrors the 10 m sampling design. Using every labelled cell
  gives 610k rows, 87% "other open"; this was tried first and abandoned.

## 2. OSM labels: both models on the same 393k pixels

Both models are scored on the same sampled 10 m pixels against their 10 m labels. The 100 m
prediction for a pixel is the class of the cell containing it. The 10 m predictions are the
stored out-of-fold predictions in `oof_predictions.parquet`. Intervals bootstrap the 12 km blocks
(1,000 resamples); the difference is paired (same resampled blocks).

| features | 10 m | 100 m | difference (100 m − 10 m) |
|---|---|---|---|
| all | 0.898 [0.885, 0.912] | 0.829 [0.815, 0.847] | **−0.068 [−0.075, −0.062]** |
| non-AlphaEarth | 0.875 [0.860, 0.890] | 0.806 [0.791, 0.824] | **−0.069 [−0.076, −0.062]** |

Per-class F1, all features (10 m → 100 m):

| residential | non-residential | water | forest | open |
|---|---|---|---|---|
| 0.92 → 0.89 | 0.72 → 0.66 | 1.00 → 0.96 | 0.94 → 0.82 | 0.92 → 0.82 |

Part of this loss is built in: a 100 m cell predicts one class, so it cannot be right for every
pixel of a mixed cell.

Scored the 100 m way (100 m model against each cell's majority OSM label) the 100 m model reaches
0.882 [0.868, 0.899], or 0.896 [0.882, 0.913] on cells at least 80% one class. These are **not**
comparable with the 10 m numbers: the population differs and a majority label is easier to predict.

## 3. Hand labels (325-point test set, confidence ≤ 2, 313 points)

Stratum-weighted (Olofsson et al. 2014), stratified bootstrap with 1,000 resamples. Each 100 m
prediction is the cell containing the test pixel, scored against that pixel's 10 m label.

| features | 10 m | 100 m | difference (100 m − 10 m) |
|---|---|---|---|
| all | 0.617 [0.547, 0.685] | 0.594 [0.525, 0.675] | −0.022 [−0.061, +0.019] |
| non-AlphaEarth | 0.627 [0.556, 0.698] | 0.596 [0.524, 0.673] | −0.031 [−0.074, +0.011] |

Excluding road pixels (294 points): differences −0.026 and −0.031, intervals again include 0.

Per-class F1, all features (10 m → 100 m):

| residential | non-residential | water | forest | open |
|---|---|---|---|---|
| 0.67 → 0.70 | 0.41 → 0.43 | 0.71 → 0.57 | 0.46 → 0.43 | 0.83 → 0.84 |

Our 10 m baseline reproduces the stored values (0.617 vs 0.6165; 0.627 vs 0.626), which checks the
scoring code.

## 4. Cost (16 threads, one laptop)

| | 10 m, all | 100 m, all |
|---|---|---|
| training rows | 393,098 | 102,575 |
| one fit | 58 s | 17 s |
| one fit, non-AlphaEarth | 25 s | 7 s |
| full HMDA map (features + predict) | about 2,640 s (one 4 km tile × 556) | about 20 s |

## 5. How far to trust it

- The hand-label test has only 39 usable non-residential points. A macro-F1 difference below about
  0.04 cannot be resolved there. "No detectable loss" is not "no loss".
- Hand labels were not relabelled at 100 m. A 100 m model is scored against a 10 m point label,
  which penalises mixed cells. Relabelling the 325 cells at 100 m would be a cleaner test.
- Inputs are plain block means. Within-block variation (for example B8 standard deviation inside the
  cell) is discarded, which is the realistic case for genuinely coarse inputs.
- Training-set design (cap per class per tile) is a judgement call; it is `CAP_PER_CLASS_TILE` in
  `run_experiment.py`.
- 10 m and 100 m CV use different random fold assignments over the same 12 km blocks. Both are
  spatially held out.

## 6. Reproduce

Needs the raster zip (`feat_2023/`, `lab/`) under `data/raw/lu/`, or set `LU_RAW` to the folder that
holds them. `LU_REPO` overrides the repo root. Python packages as in the main README, plus `pyarrow`.

```
cd experiments/res100
python build_grid.py            # 556 tiles -> work/grid100.npz (about 2 min)
python run_experiment.py cv     # 100 m spatial CV, about 4 min
python run_experiment.py eval   # all scoring, about 3 min -> results/*.csv
```

| file | content |
|---|---|
| `common.py` | paths, constants, LightGBM settings |
| `build_grid.py` | block-aggregates every tile to one 100 m mosaic |
| `features100.py` | the 100 m feature set |
| `run_experiment.py` | CV, scoring and bootstraps, timing |
| `results/scores.csv` | every model's macro-F1 and per-class F1 with intervals |
| `results/paired_differences.csv` | the 100 m minus 10 m differences with intervals |
| `results/cost.csv`, `timing_100m.csv` | timings |
