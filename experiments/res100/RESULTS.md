# Experiment: classifying 20, 50 and 100 m cells instead of 10 m pixels

**Question.** What happens to the land-use classifier if the unit is a coarser cell?

## Result

- **20 m: no detectable loss.** Paired difference in macro-F1 is −0.001 [−0.004, +0.001]. A full map
  is about 5× cheaper.
- **50 m: small, clear loss (−0.020).** About 33× cheaper.
- **100 m: −0.070.** About 126× cheaper. Forest, open and non-residential lose most.

All intervals are 95% bootstrap intervals. Scores are macro-F1. The 10 m reference is the existing model.

## 1. OSM labels: same 393k pixels, 10 m labels

Every model is scored on the same sampled 10 m pixels. A coarse model's prediction for a pixel is
the class of the cell containing it. Intervals bootstrap the 12 km blocks; differences are paired.

| cell | all features | difference vs 10 m | non-AlphaEarth features | difference vs 10 m |
|---|---|---|---|---|
| 10 m | 0.898 [0.885, 0.912] | – | 0.875 [0.860, 0.890] | – |
| 20 m | 0.896 [0.884, 0.911] | −0.001 [−0.004, +0.001] | 0.874 [0.859, 0.889] | −0.001 [−0.003, +0.002] |
| 50 m | 0.878 [0.864, 0.894] | **−0.020 [−0.022, −0.016]** | 0.855 [0.840, 0.871] | **−0.020 [−0.023, −0.016]** |
| 100 m | 0.827 [0.813, 0.845] | **−0.070 [−0.077, −0.064]** | 0.805 [0.790, 0.823] | **−0.070 [−0.076, −0.063]** |

Per-class F1, all features:

| cell | residential | non-residential | water | forest | open |
|---|---|---|---|---|---|
| 10 m | 0.92 | 0.72 | 1.00 | 0.94 | 0.92 |
| 20 m | 0.92 | 0.72 | 1.00 | 0.93 | 0.92 |
| 50 m | 0.91 | 0.70 | 0.99 | 0.91 | 0.89 |
| 100 m | 0.88 | 0.65 | 0.96 | 0.82 | 0.82 |

Part of the loss is built in: a coarse cell predicts one class, so it cannot be right for every pixel of a mixed cell.

## 2. Cost

Speed-up of a coarse model over the 10 m model, measured in the same session (machine speed
varied between sessions, so absolute seconds are not comparable across rows).

| cell | training cells | one fit | full HMDA map (features + predict) |
|---|---|---|---|
| 10 m | 393,098 | 1× | 1× (about 44 min at normal machine speed) |
| 20 m | 191,273 | 1.4× faster | **4.9× faster** (22.2 M cells) |
| 50 m | 150,155 | 2.9× faster | **33× faster** (3.6 M cells) |
| 100 m | 102,668 | 2.9× faster | **126× faster** (0.9 M cells) |

The 10 m map time is one 4 km tile times 556.

## 3. Method

- Every 10 m tile is block-averaged to one mosaic per cell size. Building height is
  cover-weighted; maximum height is the block maximum; indices come from the averaged bands.
- Same feature families and LightGBM settings as the 10 m model: 173 features at 50 and 100 m (45
  without AlphaEarth), 181 at 20 m (53 without).
- Neighbourhood windows span about the same ground distances as the 10 m model, where a window is
  at least ~1.5 cells wide: 20 m uses 60/140/300/620 m, 50 m uses 150/350/650 m, 100 m uses
  300/500/700 m. The 10 m model's 70 m window has no counterpart at 50 or 100 m.
- A cell is a training row if at least 50% of its pixels carry an OSM-derived label; its label is
  the majority class. Cells within 400 m of a hand-label point are dropped.
- **Training cap: at most 100 cells per class per 4 km tile** (`CAP_PER_CLASS_TILE` in
  `run_experiment.py`), drawn at random with a fixed seed. The main pipeline instead uses up to
  200 pixels per class per tile (`N_PER_CLASS` in `scripts/lu/05_sample_pixels.py`). The same cap
  of 100 is used at 20, 50 and 100 m. It was not tuned: neither 200 nor any other value was tested.
- Same spatial CV (5-fold GroupKFold over 12 km blocks).
- The 10 m numbers come from the repo's stored out-of-fold predictions and saved model.

## 4. Caveats

- **Training rows differ** across sizes (393k, 191k, 150k, 103k), because fewer coarse cells meet
  the 50% label rule. Some of the coarse-cell loss could be from less training data.
- **No hand-label comparison.** The hand labels are single 10 m pixels; scoring a 20–100 m cell
  against one pixel is not a fair test of a coarse model, so those scores are not reported.
- Inputs are plain block means. Within-cell variation is discarded, which is the realistic case
  for genuinely coarse inputs.

## 5. Reproduce

Needs the raster zip (`feat_2023/`, `lab/`) under `data/raw/lu/`, or set `LU_RAW` to the folder
that holds them. `LU_REPO` overrides the repo root. Packages as in the main README plus `pyarrow`.

```
cd experiments/res100
for CELL in 20 50 100; do
  LU_CELL=$CELL python build_grid.py            # 556 tiles -> work/r$CELL/ (2-6 min)
  LU_CELL=$CELL python run_experiment.py cv     # spatial CV, full models, whole-map timing
  LU_CELL=$CELL python run_experiment.py eval   # scoring -> results/r$CELL/
done
python summarize.py                             # merge -> results/*.csv
```

`retime.py` re-measures cost for one cell size next to the 10 m reference.
The 20 m map pass takes about 40 min and the grid needs about 9 GB of disk.

| file | content |
|---|---|
| `common.py` | paths, cell size, windows, LightGBM settings |
| `build_grid.py`, `features_coarse.py` | block-averaging and the coarse feature set |
| `run_experiment.py` | CV, scoring and bootstraps, timing |
| `results/scores.csv` | macro-F1 and per-class F1 with intervals, every model |
| `results/paired_differences.csv` | coarse minus 10 m differences with intervals |
| `results/cost.csv` | timings and speed-ups |
