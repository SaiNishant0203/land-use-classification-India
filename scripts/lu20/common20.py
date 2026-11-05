"""Shared settings for the 20 m production pipeline with year-dated OSM labels.

Grid, neighbourhood windows and feature code follow experiments/res100 (Ethan's 20/50/100 m
experiment, branch exp/res100-10m-vs-100m), restricted to the 12 physical bands (53 features),
which exist for every year (phys_2017, phys_2020, and the first 12 bands of feat_2023).

LU20_TEST=1 runs everything on the tiles around Gachibowli only, into separate *_test folders.
"""
from pathlib import Path
import os, json, time

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw" / "lu"
PROC = ROOT / "data" / "processed"
LUP = PROC / "lu"

TEST = os.environ.get("LU20_TEST") == "1"
SFX = "_test" if TEST else ""
OSM = PROC / f"lu20{SFX}"                  # osm_<year>/<i>_<j>.gpkg
W20 = RAW / f"lu20{SFX}"                   # lab_<year>/<tile>.tif, grid_<year>/*.npy
OUT = ROOT / "outputs" / f"lu20{SFX}"      # models, scores, maps, RESULTS.md
for d in (OSM, W20, OUT):
    d.mkdir(parents=True, exist_ok=True)

YEARS = [2017, 2020, 2023]                 # the model-comparison years (04-11 scripts)
ALL_YEARS = list(range(2017, 2024))        # final maps (12_final_maps.py); Open Buildings temporal ends in 2023
FEAT = {2023: "feat_2023", **{y: f"phys_{y}" for y in ALL_YEARS if y != 2023}}   # first 12 bands are the same in all
OSM_DATE = {y: f"{y}-12-31T23:59:59Z" for y in ALL_YEARS}            # OSM as mapped at the end of the year

CELL = 20
K = CELL // 10                   # 10 m pixels per cell edge
TS = 400                         # 10 m pixels per 4 km tile edge
NT = TS // K                     # cells per tile edge

BANDS = ["B2", "B3", "B4", "B5", "B8", "B11", "B12", "ob_cov", "ob_h", "ob_hmax", "ob_cnt", "viirs"]
SCALE = {**{b: 1e4 for b in BANDS[:7]}, "ob_cov": 1e3, "ob_h": 10, "ob_hmax": 10, "ob_cnt": 1e4, "viirs": 100}

# windows in cells, about the same ground distances as the 10 m model (60/140/300/620 m)
CFG = dict(win=[3, 7, 15, 31], hmax=[7, 15], b8sd=[3, 7], small=7, strip=250)
HALO = max(CFG["win"] + CFG["hmax"] + CFG["b8sd"] + [CFG["small"]]) // 2 + 2

LGB = dict(n_estimators=400, learning_rate=0.05, num_leaves=63, subsample=0.8, subsample_freq=1,
           colsample_bytree=0.6, class_weight="balanced", n_jobs=14, verbose=-1)
if TEST:
    LGB["n_estimators"] = 50     # dry runs only test the code path

MIN_LFRAC = 0.5          # a training cell must be >= 50% OSM-labelled; its label is the majority class
CAP = 100                # cells per class per tile
EXCL_M = 400             # no training cell within 400 m of a hand-label point
SEED = 7
CL = [1, 2, 3, 4, 5]
WINDOWS = {"Lingampally": (17.4930, 78.3170), "Gachibowli_FinancialDistrict": (17.4180, 78.3410)}   # as 13_change.py


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def tiles():
    """4 km tile key -> (minx, miny, maxx, maxy) in UTM 44N; test mode keeps tiles within 7 km of Gachibowli."""
    T = json.loads((RAW / "feat_2023" / "tiles.json").read_text())
    if TEST:
        from pyproj import Transformer
        gx, gy = Transformer.from_crs(4326, 32644, always_xy=True).transform(78.3410, 17.4180)
        T = {k: b for k, b in T.items() if abs((b[0] + b[2]) / 2 - gx) < 7000 and abs((b[1] + b[3]) / 2 - gy) < 7000}
    return T


def years_done(stage):
    """Years whose output of a stage exists (status files written by each script)."""
    return [y for y in YEARS if (W20 / f"{stage}_{y}.done").exists()]
