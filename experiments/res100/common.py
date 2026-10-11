"""Shared paths/constants for the coarse-resolution experiment (cell size set by env LU_CELL, default 100)."""
from pathlib import Path
import os, sys, time

HERE = Path(__file__).resolve().parent
# Inside the repo this file sits at <repo>/experiments/res100/. Override with LU_REPO / LU_RAW if elsewhere.
REPO = Path(os.environ.get("LU_REPO", HERE.parents[1]))
DATA = Path(os.environ.get("LU_RAW", REPO / "data" / "raw" / "lu"))       # folder holding feat_2023/, lab/
LUP = REPO / "data" / "processed" / "lu"

CELL = int(os.environ.get("LU_CELL", "100"))     # cell edge in metres: 20, 50 or 100
K = CELL // 10                                   # 10 m pixels per cell edge
TS = 400
NT = TS // K                                     # cells per 4 km tile edge
assert CELL % 10 == 0 and TS % K == 0
WORK = HERE / "work" / f"r{CELL}"; WORK.mkdir(parents=True, exist_ok=True)
OUT = HERE / "results" / f"r{CELL}"; OUT.mkdir(parents=True, exist_ok=True)

BANDS = ["B2", "B3", "B4", "B5", "B8", "B11", "B12", "ob_cov", "ob_h", "ob_hmax", "ob_cnt", "viirs"] + \
        [f"A{i:02d}" for i in range(64)]
SCALE = {**{b: 1e4 for b in BANDS[:7]}, "ob_cov": 1e3, "ob_h": 10, "ob_hmax": 10, "ob_cnt": 1e4,
         "viirs": 100, **{f"A{i:02d}": 1e3 for i in range(64)}}

# Neighbourhood windows in CELLS, chosen to span roughly the same ground distances as the 10 m
# model (70/150/310/610 m windows) where a window is at least ~1.5 cells wide.
#   win   : window means (cov, cnt, bldg_area, bldg_h, ndvi, ndbi, mndwi, viirs)
#   hmax  : max-filter windows (10 m: 150 m, 310 m)
#   b8sd  : B8 texture windows (10 m: 70 m, 150 m)
#   small : window for height SD and the smoothed AlphaEarth (10 m: 150 m)
CFG = {
    20:  dict(win=[3, 7, 15, 31], hmax=[7, 15], b8sd=[3, 7], small=7, strip=250),
    50:  dict(win=[3, 7, 13], hmax=[3, 7], b8sd=[3, 5], small=3, strip=600),
    100: dict(win=[3, 5, 7], hmax=[3, 5], b8sd=[3, 5], small=3, strip=1200),
}[CELL]
HALO = max(CFG["win"] + CFG["hmax"] + CFG["b8sd"] + [CFG["small"]]) // 2 + 2

# the repo's lightgbm settings (06_train_eval.py), n_jobs raised for this machine
LGB = dict(n_estimators=400, learning_rate=0.05, num_leaves=63, subsample=0.8, subsample_freq=1,
           colsample_bytree=0.6, class_weight="balanced", n_jobs=16, verbose=-1)


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)
