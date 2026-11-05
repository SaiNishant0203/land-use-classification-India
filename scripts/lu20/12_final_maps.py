"""
Final 20 m land-use maps for every year 2017-2023 (default 2017, 2020, 2023): `cw_prior` from 11_retrain_variants.py
(production labels, class weights towards the mapped class shares), 5 seeds per year, class from
the mean probability over the seeds.

Training cells are the cached draws of 11_retrain_variants.py (rows_<year>.pkl, label rule `base`,
seeds 1-5) with their cached features, so each seed is the same model that was scored there.
Scoring on the hand labels is done afterwards from the maps (no hand-label files needed here).

Years without a retrain cache (2018, 2019, 2021, 2022) get one from `--prep`, drawn the same way
(04_train.sample with seeds 1-5, label rule `base`). It needs the hand-label files, so it runs where
those are (the laptop); the mapping itself can then run elsewhere.

Usage: python 12_final_maps.py [years...] [--dry]      default years 2017 2020 2023
       python 12_final_maps.py --prep <years...>       training cells + features into the cache, no maps
       N_JOBS=<threads> overrides LightGBM's n_jobs
       --dry: 2023 only, 1 seed, 50 trees, a few strips, into maps_final_dry/
Inputs: data/raw/lu/lu20/grid_<year>/{meta.json,mean,hw,hmax,valid}.npy,
        outputs/lu20/retrain/cache/{rows_<year>.pkl,feat_<year>.npz,feat_<year>_names.json},
        data/processed/aoi_utm44n.gpkg
Output: outputs/lu20/maps_final/landuse_<year>_20m.tif (band 1 class 1-5, 0 outside HMDA;
        bands 2-6 mean P(class) x 100), models/cw_prior_<seed>_<year>.pkl, done.txt
"""
import sys, os, json, time, pickle
import numpy as np, pandas as pd, geopandas as gpd, rasterio, lightgbm as lgb
from rasterio.features import rasterize
from rasterio.transform import from_origin
from common20 import *
import features20 as FX

DRY, PREP = "--dry" in sys.argv, "--prep" in sys.argv
SEEDS = [1] if DRY else [1, 2, 3, 4, 5]
YRS = [2023] if DRY else ([int(a) for a in sys.argv[1:] if a.isdigit()] or YEARS)
NB = 50 if DRY else LGB["n_estimators"]
NJ = int(os.environ.get("N_JOBS", LGB["n_jobs"]))
MAP_SHARE = {1: 0.098, 2: 0.091, 3: 0.030, 4: 0.152, 5: 0.629}      # as 11_retrain_variants.py
CA = OUT / "retrain" / "cache"
M = OUT / ("maps_final_dry" if DRY else "maps_final"); (M / "models").mkdir(parents=True, exist_ok=True)


def prior_weight(y):
    """cw_prior: weights that turn the training class mix into the mapped class shares."""
    n = np.bincount(y, minlength=6)[1:].astype(float); have = n / n.sum()
    want = np.array([MAP_SHARE[c] for c in CL])
    w = (want / want.sum()) / have
    return {c: float(w[c - 1]) for c in CL}


def open_grid(year):
    G = W20 / f"grid_{year}"
    g = {k: np.load(G / f"{k}.npy", mmap_mode="r") for k in ["mean", "hw", "hmax", "valid"]}
    g["meta"] = json.loads((G / "meta.json").read_text())
    return g


def prep(y):
    """Training cells for seeds 1-5 and their features, in the cache format of 11_retrain_variants.py."""
    import importlib
    T = importlib.import_module("04_train")
    grid = FX.open_grid(y)
    g = {**grid, "labv": np.stack([np.array(grid["labc"][i]) for i in range(6)]).astype(np.int16)}
    vx, vy = T.hand_xy()
    rows = {}
    for s in [1, 2, 3, 4, 5]:
        T.SEED = s
        rows[("base", s)] = T.sample(g, "labv", vx, vy)[["flat", "label"]]
    flats = np.unique(np.concatenate([d.flat.values for d in rows.values()]))
    t = time.time(); names, X = FX.extract(grid, flats)
    np.savez(CA / f"feat_{y}.npz", flat=flats, X=X); (CA / f"feat_{y}_names.json").write_text(json.dumps(names))
    pickle.dump(rows, open(CA / f"rows_{y}.pkl", "wb"))
    log(f"{y}: cache with {len(flats):,} cells ({time.time() - t:.0f}s for features)")


def train(y):
    rows = pickle.load(open(CA / f"rows_{y}.pkl", "rb"))
    z = np.load(CA / f"feat_{y}.npz"); F, X = z["flat"], z["X"]
    names = json.loads((CA / f"feat_{y}_names.json").read_text())
    mods = []
    for s in SEEDS:
        fp = M / "models" / f"cw_prior_{s}_{y}.pkl"
        if fp.exists():
            mods.append(pickle.load(open(fp, "rb"))); continue
        d = rows[("base", s)]
        i = np.searchsorted(F, d.flat.values); assert (F[i] == d.flat.values).all()
        lab = d.label.values
        p = {**LGB, "n_estimators": NB, "n_jobs": NJ, "class_weight": prior_weight(lab), "random_state": s}
        t = time.time(); m = lgb.LGBMClassifier(**p).fit(X[i], lab)
        pickle.dump(m, open(fp, "wb")); mods.append(m)
        log(f"{y} seed {s}: {len(lab):,} rows, {time.time() - t:.0f}s")
    return names, mods


def main():
    if PREP:
        for y in YRS:
            prep(y)
        return
    log(f"years {YRS}, seeds {SEEDS}, {NB} trees, n_jobs {NJ}")
    for y in YRS:
        names, mods = train(y)
        grid = open_grid(y); meta = grid["meta"]; ny, nx = meta["ny"], meta["nx"]
        tr = from_origin(meta["minx"], meta["maxy"], CELL, CELL)
        aoi = gpd.read_file(PROC / "aoi_utm44n.gpkg").to_crs(32644)
        inside = rasterize(((g, 1) for g in aoi.geometry), (ny, nx), transform=tr, dtype="uint8").astype(bool)
        cls = np.zeros((ny, nx), np.uint8); prob = np.zeros((5, ny, nx), np.uint8)
        st = FX.strips(ny)
        if DRY:
            st = st[len(st) // 2:len(st) // 2 + 2]
        t = time.time()
        for r0, r1 in st:
            gs, off = FX.load_strip(grid, r0, r1)
            v = gs["valid"][off:off + (r1 - r0)] & inside[r0:r1]
            if not v.any():
                continue
            nm, Fs = FX.compute(gs)
            assert nm == names, "feature order differs from the training cache"
            Xs = np.stack([Fs[n][off:off + (r1 - r0)][v] for n in nm], 1)
            p = np.mean([m.predict_proba(Xs) for m in mods], 0)
            assert all((m.classes_ == np.array(CL)).all() for m in mods)
            blk = cls[r0:r1]; blk[v] = p.argmax(1) + 1
            for c in range(5):
                pb = prob[c, r0:r1]; pb[v] = np.round(p[:, c] * 100)
        log(f"{y}: mapped {int((cls > 0).sum()):,} cells in {time.time() - t:.0f}s; class shares "
            + ", ".join(f"{c} {(cls[inside] == c).mean():.3f}" for c in CL))
        prof = dict(driver="GTiff", width=nx, height=ny, crs="EPSG:32644", transform=tr, dtype="uint8",
                    compress="deflate", tiled=True, nodata=0)
        with rasterio.open(M / f"landuse_{y}_20m.tif", "w", count=6, **prof) as d:
            d.write(cls, 1); d.write(prob, list(range(2, 7)))
            d.set_band_description(1, "class 1 res, 2 non-res, 3 water, 4 trees, 5 open")
            for c, n in enumerate(["res", "nonres", "water", "trees", "open"]):
                d.set_band_description(c + 2, f"P({n}) x 100, mean of {len(SEEDS)} seeds")
    (M / "done.txt").write_text(time.strftime("%Y-%m-%d %H:%M"))
    log("ALL DONE")


if __name__ == "__main__":
    main()
