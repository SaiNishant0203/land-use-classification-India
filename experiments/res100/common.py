"""Shared paths/constants for the 10 m vs 100 m experiment."""
from pathlib import Path
import os, sys, time

HERE = Path(__file__).resolve().parent
# Inside the repo this file sits at <repo>/experiments/res100/. Override with LU_REPO / LU_RAW if elsewhere.
REPO = Path(os.environ.get("LU_REPO", HERE.parents[1]))
DATA = Path(os.environ.get("LU_RAW", REPO / "data" / "raw" / "lu"))       # folder holding feat_2023/, lab/
LUP = REPO / "data" / "processed" / "lu"
WORK = HERE / "work"; WORK.mkdir(exist_ok=True)
OUT = HERE / "results"; OUT.mkdir(exist_ok=True)

CELL = 100            # metres
K = 10                # 10 m pixels per 100 m cell edge
TS = 400
BANDS = ["B2", "B3", "B4", "B5", "B8", "B11", "B12", "ob_cov", "ob_h", "ob_hmax", "ob_cnt", "viirs"] + \
        [f"A{i:02d}" for i in range(64)]
SCALE = {**{b: 1e4 for b in BANDS[:7]}, "ob_cov": 1e3, "ob_h": 10, "ob_hmax": 10, "ob_cnt": 1e4,
         "viirs": 100, **{f"A{i:02d}": 1e3 for i in range(64)}}

# the repo's lightgbm settings (06_train_eval.py), n_jobs raised for this machine
LGB = dict(n_estimators=400, learning_rate=0.05, num_leaves=63, subsample=0.8, subsample_freq=1,
           colsample_bytree=0.6, class_weight="balanced", n_jobs=16, verbose=-1)


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)
