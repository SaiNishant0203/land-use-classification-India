"""20 m model, 10 seeds: how stable are the predicted classes, and what does a majority vote give?

A seed controls every random choice in training: which training cells are drawn (<=100 per class
per tile) and LightGBM's row / column sampling. Each seed gives one model. The models predict seven
4 x 4 km areas of Hyderabad, the hand-labelled test cells and a 1% random sample of HMDA. The combined
prediction is the majority vote over the 10 runs (ties broken by the mean class probability), and
every cell also gets its vote share per class (e.g. 80% non-residential, 20% residential) and the
mean of the 10 runs' class probabilities.

Reuses the 20 m grid and feature code of ../res100 (run `LU_CELL=20 python build_grid.py` there
first). Everything this experiment makes goes to ./work (cache, ~16 GB) and ./results.

Usage:
    python seed_ensemble.py features   # all cell features -> work/feat_all.npy (~16 GB, once, ~5 min)
    python seed_ensemble.py train      # 10 models (~15 min)
    python seed_ensemble.py predict    # areas + hand-label cells + HMDA sample, 10 runs
    python seed_ensemble.py report     # rasters, tables, figures -> results/
    python seed_ensemble.py osmcv      # OSM labels: 5-fold spatial CV over 12 km blocks, 50 fits (~45 min)
    python seed_ensemble.py osmreport  # OSM scores, single run vs combined -> results/osm/
    python seed_ensemble.py fullmap    # all of HMDA, 5-seed ensemble (LU_MAP_SEEDS=1,2,3,4,5), resumable
    python seed_ensemble.py fullreport # full-map GeoTIFFs, area table, figure -> results/full_map/
"""
import os, sys, json, time, pickle
from pathlib import Path

EXP = Path(__file__).resolve().parent
RES100 = EXP.parent / "res100"
os.environ.setdefault("LU_CELL", "20")
if "LU_REPO" not in os.environ:          # repo root holding data/processed: this checkout, or the sibling clone
    root = EXP.parents[1]
    os.environ["LU_REPO"] = str(root if (root / "data" / "processed").exists() else root / "land-use-classification-India-git")
sys.path.insert(0, str(RES100))

import numpy as np, pandas as pd, lightgbm as lgb
INK = "#1f1f1f"
from common import *                    # WORK = res100/work/r20 (the grid), LGB settings, CFG, log
import features_coarse as FC
import run_experiment as RE

assert CELL == 20, "run with LU_CELL=20"
SEEDS = [int(s) for s in os.environ.get("LU_SEEDS", ",".join(map(str, range(1, 11)))).split(",")]
CL = [1, 2, 3, 4, 5]
NAMES = {1: "residential", 2: "non-residential", 3: "water", 4: "forest", 5: "open"}
COLORS = {1: "#e8a33d", 2: "#c0392b", 3: "#2e86c1", 4: "#1e8449", 5: "#e5e1c9"}   # as 09_predict_map.py
SW = EXP / "work"; SW.mkdir(exist_ok=True)
SO = EXP / "results"; SO.mkdir(exist_ok=True)
CFG["strip"] = 125                     # smaller strips than the original run: this machine has 16 GB RAM


def vflat():
    """Flat indices (row * nx + col) of all valid cells, row-major; row i of feat_all.npy is cell vflat[i]."""
    p = SW / "vflat.npy"
    if not p.exists():
        np.save(p, np.flatnonzero(np.load(WORK / "valid.npy")))
    return np.load(p)


def pos_of(flat, vf):
    p = np.searchsorted(vf, flat); assert (vf[np.minimum(p, len(vf) - 1)] == flat).all(); return p


# ----------------------------------------------------------------------------- stage 1: features
def stage_features():
    grid = FC.open_grid(); ny = grid["meta"]["ny"]; vf = vflat()
    from numpy.lib.format import open_memmap
    X = None; i = 0; t0 = time.time()
    for r0, r1 in FC.strips(ny):
        gs, off = FC.load_strip(grid, r0, r1); names, F = FC.compute(gs)
        v = gs["valid"][off:off + (r1 - r0)]
        if X is None:
            X = open_memmap(SW / "feat_all.tmp.npy", mode="w+", dtype=np.float32, shape=(len(vf), len(names)))
        n = int(v.sum())
        for j, nm in enumerate(names):
            X[i:i + n, j] = F[nm][off:off + (r1 - r0)][v]
        i += n; del F, gs
        log(f"features rows {r0}-{r1}: {i:,}/{len(vf):,} cells ({time.time() - t0:.0f}s)")
    assert i == len(vf)
    X.flush(); del X
    (SW / "feat_all.tmp.npy").replace(SW / "feat_all.npy")
    (SW / "names.json").write_text(json.dumps(names))
    log("features done")


def feats():
    return np.load(SW / "feat_all.npy", mmap_mode="r"), json.loads((SW / "names.json").read_text())


# ----------------------------------------------------------------------------- stage 2: train
def candidate_pool():
    """Same candidate cells as run_experiment.stage_cv: >=50% OSM-labelled, not within 400 m of a test point."""
    meta = json.loads((WORK / "meta.json").read_text()); ny, nx = meta["ny"], meta["nx"]
    V, _ = RE.load_val(meta)
    valid = np.load(WORK / "valid.npy"); labc = np.load(WORK / "labc.npy", mmap_mode="r")
    nlab = sum(np.array(labc[c]).astype(np.int16) for c in range(1, 6))
    cand = valid & (nlab / (K * K) >= RE.MIN_LFRAC)
    rad = int(np.ceil(RE.EXCL_M / CELL))
    for r0, c0 in zip((meta["maxy"] - V.y.values) // CELL, (V.x.values - meta["minx"]) // CELL):
        r0, c0 = int(r0), int(c0)
        rs, cs = slice(max(0, r0 - rad), r0 + rad + 1), slice(max(0, c0 - rad), c0 + rad + 1)
        yy, xx = np.mgrid[rs, cs]
        cand[rs, cs] &= ~(np.hypot((yy - r0) * CELL, (xx - c0) * CELL) < RE.EXCL_M)
    rr, cc = np.nonzero(cand)
    cnt = np.stack([np.array(labc[c])[rr, cc] for c in range(1, 6)])
    return pd.DataFrame({"flat": rr * nx + cc, "maj": cnt.argmax(0) + 1, "tile": (rr // NT) * 10000 + cc // NT})


def stage_train():
    pool = candidate_pool(); vf = vflat(); X, names = feats()
    log(f"{len(pool):,} candidate training cells")
    rows_log = []
    for s in SEEDS:
        if (SW / f"model_s{s}.pkl").exists():
            continue
        pool["r"] = np.random.default_rng(s).random(len(pool))
        rows = pool.sort_values("r").groupby(["tile", "maj"]).head(RE.CAP_PER_CLASS_TILE).sort_values("flat")
        Xt = np.asarray(X[pos_of(rows.flat.values, vf)])
        t = time.time()
        m = lgb.LGBMClassifier(**{**LGB, "random_state": s}).fit(Xt, rows.maj.values)
        pickle.dump((m, names), open(SW / f"model_s{s}.pkl", "wb"))
        np.save(SW / f"train_flat_s{s}.npy", rows.flat.values)
        log(f"seed {s}: {len(rows):,} training cells {rows.maj.value_counts().sort_index().to_dict()}, fit {time.time() - t:.0f}s")


# ----------------------------------------------------------------------------- stage 3: predict (areas)
# 4 x 4 km windows (200 x 200 cells), centred on these points (EPSG:32644, from lat/lon)
AREAS = {
    "old_city_charminar":    (231648, 1921323),   # dense old housing and bazaars
    "secunderabad":          (234612, 1929268),   # mixed: cantonment, railway, housing, commerce
    "hitec_city":            (221883, 1931288),   # IT offices and high-rise housing
    "financial_district":    (217519, 1927760),   # IT campuses, construction boom (change-test site)
    "lingampally":           (215084, 1936101),   # suburban housing (change-test site)
    "jeedimetla_industrial": (229886, 1938334),   # industrial estate
    "shamshabad_fringe":     (223344, 1910404),   # peri-urban fringe near the airport
}
AREA_KM = 4
SAMPLE_FRAC = 0.01                       # random HMDA-wide sample, for HMDA-level composition and stability


def selection():
    """Cells to predict: area windows, hand-label cells, a 1% sample of HMDA. Returns (meta, groups dict)."""
    meta = json.loads((WORK / "meta.json").read_text()); ny, nx = meta["ny"], meta["nx"]
    vf = vflat(); valid = np.load(WORK / "valid.npy"); n = AREA_KM * 1000 // CELL
    groups = {}
    for a, (x, y) in AREAS.items():
        r0 = int(round((meta["maxy"] - y) / CELL)) - n // 2; c0 = int(round((x - meta["minx"]) / CELL)) - n // 2
        assert valid[r0:r0 + n, c0:c0 + n].all(), f"{a}: window leaves the grid"
        rr, cc = np.mgrid[r0:r0 + n, c0:c0 + n]
        groups[a] = dict(flat=(rr * nx + cc).ravel(), r0=r0, c0=c0, n=n)
    V, _ = RE.load_val(meta)
    groups["handlabel"] = dict(flat=V.flat.values)
    inside, _ = hmda_mask(meta)
    cand = np.flatnonzero((inside & valid).ravel())
    groups["hmda_sample"] = dict(flat=np.sort(np.random.default_rng(0).choice(cand, int(len(cand) * SAMPLE_FRAC), replace=False)))
    for g in groups.values():
        g["pos"] = pos_of(g["flat"], vf)
    return meta, groups


def stage_predict():
    meta, groups = selection()
    U = np.unique(np.concatenate([g["pos"] for g in groups.values()]))
    X, _ = feats(); XU = np.asarray(X[U])
    log(f"{len(U):,} cells to predict: " + ", ".join(f"{k} {len(g['pos']):,}" for k, g in groups.items()))
    P = np.zeros((len(SEEDS), len(U), 5), np.float32)
    for i, s in enumerate(SEEDS):
        m, _ = pickle.load(open(SW / f"model_s{s}.pkl", "rb"))
        t = time.time(); P[i] = m.predict_proba(XU)
        log(f"seed {s}: predicted in {time.time() - t:.0f}s")
    np.savez(SW / "pred_areas.npz", U=U, P=P, seeds=np.array(SEEDS))
    log("predict done")


# ----------------------------------------------------------------------------- stage 4: report
def hmda_mask(meta):
    import geopandas as gpd
    from rasterio.features import geometry_mask
    from rasterio.transform import from_origin
    aoi = gpd.read_file(REPO / "data" / "processed" / "aoi_utm44n.gpkg").to_crs(32644)
    tr = from_origin(meta["minx"], meta["maxy"], CELL, CELL)
    return ~geometry_mask(aoi.geometry, (meta["ny"], meta["nx"]), tr), tr


def write_tif(path, bands, tr, desc, colormap=False):
    import rasterio
    bands = np.asarray(bands, np.uint8); bands = bands[None] if bands.ndim == 2 else bands
    with rasterio.open(path, "w", driver="GTiff", height=bands.shape[1], width=bands.shape[2], count=len(bands),
                       dtype="uint8", crs="EPSG:32644", transform=tr, compress="deflate") as d:
        d.write(bands)
        for i, t in enumerate(desc, 1):
            d.set_band_description(i, t)
        if colormap:
            d.write_colormap(1, {0: (255, 255, 255, 0), **{k: tuple(int(v[i:i + 2], 16) for i in (1, 3, 5)) + (255,)
                                                            for k, v in COLORS.items()}})


def combine(P):
    """P (runs, cells, 5) -> per-run class, votes (5, cells), mean prob (5, cells), majority, top votes."""
    R = len(P)
    cls = P.argmax(2).astype(np.uint8) + 1
    votes = np.stack([(cls == c).sum(0) for c in CL]).astype(np.int16)        # int: votes * 100 must not overflow
    pmean = P.mean(0).T
    maj = (votes * 10.0 + pmean).argmax(0).astype(np.uint8) + 1          # ties -> higher mean probability
    return cls, votes, pmean, maj, votes.max(0)


def stability(cls, votes, pmean, maj, top, R):
    """Composition per run and combined, and how often cells change class."""
    comp = [{"run": f"seed {s}", **{NAMES[c]: (cls[i] == c).mean() * 100 for c in CL}} for i, s in enumerate(SEEDS)]
    runs = pd.DataFrame(comp)[list(NAMES.values())]
    comp += [{"run": "runs: min", **runs.min()}, {"run": "runs: max", **runs.max()}, {"run": "runs: sd", **runs.std()},
             {"run": "combined: majority vote", **{NAMES[c]: (maj == c).mean() * 100 for c in CL}},
             {"run": "combined: mean vote share", **{NAMES[c]: votes[c - 1].mean() / R * 100 for c in CL}},
             {"run": "combined: mean probability", **{NAMES[c]: pmean[c - 1].mean() * 100 for c in CL}}]
    unstable = top < R
    o = np.argsort(-(votes[:, unstable] * 10.0 + pmean[:, unstable]), axis=0)[:2]
    pairs = pd.Series([" / ".join(NAMES[c + 1] for c in sorted(p)) for p in o.T]).value_counts()
    summ = {"cells": len(maj), "pct_unanimous": (~unstable).mean() * 100, "pct_change_in_some_run": unstable.mean() * 100,
            "pct_agreement_le_70": (top <= 0.7 * R).mean() * 100, "mean_agreement_pct": top.mean() / R * 100,
            "mean_pct_cells_run_differs_from_majority": np.mean([(cls[i] != maj).mean() * 100 for i in range(R)]),
            **{f"pct_unanimous_where_majority_{NAMES[c]}": (top[maj == c] == R).mean() * 100 if (maj == c).any() else np.nan
               for c in CL},
            **{f"swing_{k}": v / max(unstable.sum(), 1) * 100 for k, v in pairs.head(4).items()}}
    return pd.DataFrame(comp), summ


def stage_report():
    meta, groups = selection(); R = len(SEEDS)
    z = np.load(SW / "pred_areas.npz"); U, P = z["U"], z["P"]; assert list(z["seeds"]) == SEEDS
    from rasterio.transform import from_origin
    MD = SO / "maps"; MD.mkdir(exist_ok=True)
    comps, summs, cells = [], [], []
    for name, g in groups.items():
        if name == "handlabel":
            continue
        cls, votes, pmean, maj, top = combine(P[:, np.searchsorted(U, g["pos"])])
        comp, summ = stability(cls, votes, pmean, maj, top, R)
        comps.append(comp.assign(area=name)); summs.append({"area": name, **summ})
        if name == "hmda_sample":
            continue
        n = g["n"]; sq = lambda v: np.asarray(v).reshape(n, n)
        tr = from_origin(meta["minx"] + g["c0"] * CELL, meta["maxy"] - g["r0"] * CELL, CELL, CELL)
        write_tif(MD / f"{name}_runs.tif", [sq(c) for c in cls], tr, [f"class, seed {s}" for s in SEEDS], colormap=True)
        write_tif(MD / f"{name}_combined.tif",
                  [sq(maj), sq(top * 100 // R)] + [sq(votes[c - 1] * 100 // R) for c in CL] +
                  [sq(np.round(pmean[c - 1] * 100)) for c in CL], tr,
                  ["majority-vote class", "agreement: % of runs voting the majority class"] +
                  [f"% of runs voting {NAMES[c]}" for c in CL] + [f"mean probability x100, {NAMES[c]}" for c in CL])
        f = g["flat"]; t = pd.DataFrame({"area": name, "x": meta["minx"] + (f % meta["nx"] + .5) * CELL,
                                         "y": meta["maxy"] - (f // meta["nx"] + .5) * CELL,
                                         "majority_class": maj, "majority_name": [NAMES[c] for c in maj],
                                         "agreement_pct": top * 100 // R})
        for c in CL:
            t[f"vote_pct_{NAMES[c]}"] = votes[c - 1] * 100 // R
        for c in CL:
            t[f"mean_prob_{NAMES[c]}"] = np.round(pmean[c - 1], 3)
        for i, s in enumerate(SEEDS):
            t[f"class_seed{s:02d}"] = cls[i]
        cells.append(t)
        figure_area(name, cls, maj, top, votes, n)
    comps = pd.concat(comps, ignore_index=True)[["area", "run"] + list(NAMES.values())]
    comps.to_csv(SO / "composition_by_area_and_run_pct.csv", index=False)
    summs = pd.DataFrame(summs); summs.to_csv(SO / "stability_by_area.csv", index=False)
    cells = pd.concat(cells, ignore_index=True)
    cells.to_csv(SO / "area_cells_vote_shares.csv", index=False)
    log(f"{len(cells):,} area cells written")

    # hand labels (conf <= 2): every run, the majority vote, the mean-probability argmax
    V, W = RE.load_val(meta)
    cls, votes, pmean, maj, top = combine(P[:, np.searchsorted(U, groups["handlabel"]["pos"])])
    preds = {f"seed {s}": cls[i].astype(int) for i, s in enumerate(SEEDS)}
    preds["combined: majority vote"] = maj.astype(int); preds["combined: mean probability"] = pmean.argmax(0) + 1
    hl = []
    for sub, sel in (("confidence<=2 (headline)", (V.confidence.fillna(3) <= 2).values),
                     ("confidence<=2, no road pixels", ((V.confidence.fillna(3) <= 2) & (V.is_road.fillna(0) == 0)).values)):
        r_, s_ = V.true_class.values[sel], V.stratum.values[sel]
        Ps = {k: v[sel] for k, v in preds.items()}
        d = RE.boot_strata(r_, Ps, s_, W)
        rows = []
        for k, p in Ps.items():
            mf, f1 = RE.weighted_metrics(r_, p, s_, W)
            rows.append({"subset": sub, "model": k, "n": int(sel.sum()), "macro_F1": mf, "lo": RE.ci(d[k])[0],
                         "hi": RE.ci(d[k])[1], **{f"F1_{NAMES[c]}": f1[c - 1] for c in CL}})
        runs = pd.DataFrame(rows[:R]).drop(columns=["subset", "model", "n"])
        rows += [{"subset": sub, "model": "runs: mean", "n": int(sel.sum()), **runs.mean()},
                 {"subset": sub, "model": "runs: sd", "n": int(sel.sum()), **runs.std()},
                 {"subset": sub, "model": "runs: min", "n": int(sel.sum()), **runs.min()},
                 {"subset": sub, "model": "runs: max", "n": int(sel.sum()), **runs.max()}]
        hl += rows
    hl = pd.DataFrame(hl); hl.to_csv(SO / "handlabel_scores.csv", index=False)
    conf = (V.confidence.fillna(3) <= 2).values
    hl_unstable = pd.DataFrame({"pid": V.pid.values, "true": V.true_class.values, "majority": maj, "agreement_pct": top * 100 // R,
                                **{f"vote_pct_{NAMES[c]}": votes[c - 1] * 100 // R for c in CL}})[conf & (top < R)]
    hl_unstable.to_csv(SO / "handlabel_points_that_change.csv", index=False)

    figure_overview(meta, groups)
    pd.set_option("display.width", 250); pd.set_option("display.max_columns", 40)
    log("\n" + summs.round(2).T.to_string())
    log("\n" + comps.round(2).to_string(index=False))
    log("\n" + hl.round(3).to_string(index=False))
    log(f"hand-label points (conf<=2) whose class changes between runs: {len(hl_unstable)} of {int(conf.sum())}")


# ----------------------------------------------------------------------------- OSM labels: spatial 5-fold CV
# The 12 km blocks are split into 5 folds (GroupKFold). For each fold, every seed trains on its own draw of
# cells from the other 4 folds and predicts the fold's cells. All seeds use the SAME folds and are scored on
# the SAME cells, so single runs, the majority vote and the mean probability are compared on identical data.
#   osm cells : a fixed draw (seed 0, <=100 cells per class per tile), scored against the cell's OSM majority label
#   osm pixels: the cells holding the repo's 393k 10 m sample pixels, scored against the 10 m labels
# One file per seed and fold (work/osmcv_s<seed>_f<fold>.npy), so an interrupted run resumes.
OSM_EVAL_SEED = 0
N_FOLDS = 5


def block_of(flat, meta):
    """12 km block (3 x 3 tiles) of each cell, as in the 10 m CV: key = (tile_x_km // 12) * 1000 + tile_y_km // 12."""
    nx = meta["nx"]
    x = meta["minx"] + (flat % nx + .5) * CELL; y = meta["maxy"] - (flat // nx + .5) * CELL
    return ((np.floor(x / 4000).astype(int) * 4) // 12) * 1000 + (np.floor(y / 4000).astype(int) * 4) // 12


def draw(pool, seed):
    pool = pool.assign(r=np.random.default_rng(seed).random(len(pool)))
    return pool.sort_values("r").groupby(["tile", "maj"]).head(RE.CAP_PER_CLASS_TILE).sort_values("flat")


def stage_osmcv():
    from sklearn.model_selection import GroupKFold
    meta = json.loads((WORK / "meta.json").read_text()); vf = vflat()
    pool = candidate_pool(); pool["block"] = block_of(pool.flat.values, meta)
    E = draw(pool, OSM_EVAL_SEED)
    fold_of = {}
    for f, (_, te) in enumerate(GroupKFold(n_splits=5).split(E, E.maj, E.block)):
        fold_of.update({int(b): f for b in np.unique(E.block.values[te])})
    fold = lambda blocks: np.array([fold_of.get(int(b), int(b) % 5) for b in blocks])
    pool["fold"] = fold(pool.block.values)
    pix = pd.read_parquet(LUP / "oof_predictions.parquet", columns=["x", "y", "label", "oof_ALL"])
    pflat = RE.cell_of(pix.x.values, pix.y.values, meta)
    EU = np.unique(np.concatenate([E.flat.values, pflat])); efold = fold(block_of(EU, meta))
    log(f"OSM eval: {len(E):,} cells + cells of {len(pix):,} pixels = {len(EU):,} cells; "
        f"blocks without an eval cell (fold by key): {sum(int(b) not in fold_of for b in np.unique(pool.block))}")
    np.savez(SW / "osm_eval.npz", EU=EU, efold=efold, e_flat=E.flat.values, e_maj=E.maj.values,
             p_flat=pflat, p_label=pix.label.values, p_oof10=pix.oof_ALL.values)
    X, _ = feats(); XE = np.asarray(X[pos_of(EU, vf)])
    for s in SEEDS:
        todo = [f for f in range(N_FOLDS) if not (SW / f"osmcv_s{s}_f{f}.npy").exists()]
        if not todo:
            continue
        rows = draw(pool, s); Xr = np.asarray(X[pos_of(rows.flat.values, vf)]); y = rows.maj.values
        for f in todo:
            t0 = time.time(); tr = rows.fold.values != f
            m = lgb.LGBMClassifier(**{**LGB, "random_state": s}).fit(Xr[tr], y[tr])
            np.save(SW / f"osmcv_s{s}_f{f}.npy", m.predict_proba(XE[efold == f]).astype(np.float32))
            log(f"seed {s} fold {f}: trained on {int(tr.sum()):,} cells, scored {int((efold == f).sum()):,} cells, "
                f"{time.time() - t0:.0f}s")


def stage_osmreport():
    meta = json.loads((WORK / "meta.json").read_text()); R = len(SEEDS)
    z = np.load(SW / "osm_eval.npz"); EU = z["EU"]
    P = np.zeros((len(SEEDS), len(EU), 5), np.float32)                  # out-of-fold probabilities
    for i, s in enumerate(SEEDS):
        for f in range(N_FOLDS):
            P[i, z["efold"] == f] = np.load(SW / f"osmcv_s{s}_f{f}.npy")
    OD = SO / "osm"; OD.mkdir(exist_ok=True)
    keys = np.unique(block_of(EU, meta)); G = len(keys)
    tests = {"OSM cells (20 m, majority OSM label)": (z["e_flat"], z["e_maj"], None),
             "OSM pixels (393k 10 m sample pixels, 10 m label)": (z["p_flat"], z["p_label"], z["p_oof10"])}
    log(f"5-fold CV: {G} blocks of 12 km, {len(z['e_flat']):,} OSM cells, {len(z['p_flat']):,} OSM pixels")
    rng = np.random.default_rng(1)
    rows, diffs, ksub, stab = [], [], [], []
    for tname, (flat, ref, oof10) in tests.items():
        ix = np.searchsorted(EU, flat); assert (EU[ix] == flat).all()
        gid = np.searchsorted(keys, block_of(flat, meta)); ref = ref.astype(int)
        cls, votes, pmean, maj, top = combine(P[:, ix])
        preds = {f"seed {s}": cls[i].astype(int) for i, s in enumerate(SEEDS)}
        preds["combined: majority vote"] = maj.astype(int); preds["combined: mean probability"] = pmean.argmax(0) + 1
        if oof10 is not None:
            preds["reference: 10 m model (repo 5-fold CV, one run)"] = oof10.astype(int)
        Cs = {k: RE.group_conf(gid, ref, p, G) for k, p in preds.items()}
        d = RE.boot_groups(Cs)
        res = []
        for k in preds:
            mf, f1 = RE.macro_f1(Cs[k].sum(0))
            res.append({"test": tname, "model": k, "n": len(ref), "macro_F1": mf, "lo": RE.ci(d[k])[0], "hi": RE.ci(d[k])[1],
                        **{f"F1_{NAMES[c]}": f1[c - 1] for c in CL}})
        runs = pd.DataFrame(res[:R]).drop(columns=["test", "model", "n"])
        for st, lab in (("mean", "mean"), ("std", "sd"), ("min", "min"), ("max", "max")):
            res.append({"test": tname, "model": f"runs: {lab}", "n": len(ref), **getattr(runs, st)()})
        rows += res
        single = np.mean([d[f"seed {s}"] for s in SEEDS], 0)                 # per bootstrap replicate: average single run
        f_run = {s: RE.macro_f1(Cs[f"seed {s}"].sum(0))[0] for s in SEEDS}
        for k in ("combined: majority vote", "combined: mean probability"):
            fk = RE.macro_f1(Cs[k].sum(0))[0]; dd = d[k] - single
            diffs.append({"test": tname, "comparison": f"{k} minus average single run",
                          "diff_macro_F1": fk - np.mean(list(f_run.values())), "lo": RE.ci(dd)[0], "hi": RE.ci(dd)[1]})
            diffs.append({"test": tname, "comparison": f"{k} minus best single run",
                          "diff_macro_F1": fk - max(f_run.values()), "lo": np.nan, "hi": np.nan})
            diffs.append({"test": tname, "comparison": f"{k} minus worst single run",
                          "diff_macro_F1": fk - min(f_run.values()), "lo": np.nan, "hi": np.nan})
        for k in sorted({min(k, R) for k in (1, 3, 5, 10)}):
            mf = []
            for _ in range(30 if k < R else 1):
                ii = rng.choice(R, k, replace=False)
                mf.append(RE.macro_f1(np.bincount((ref - 1) * 5 + combine(P[ii][:, ix])[3] - 1, minlength=25).reshape(5, 5))[0])
            ksub.append({"test": tname, "seeds_in_ensemble": k, "macro_F1_mean": np.mean(mf), "macro_F1_min": np.min(mf),
                         "macro_F1_max": np.max(mf)})
        stab.append({"test": tname, "cells": len(ref), "pct_change_in_some_run": (top < R).mean() * 100,
                     "pct_agreement_le_70": (top <= .7 * R).mean() * 100,
                     **{f"pct_change_where_osm_{NAMES[c]}": (top[ref == c] < R).mean() * 100 for c in CL}})
    rows, diffs, ksub, stab = map(pd.DataFrame, (rows, diffs, ksub, stab))
    diffs = pd.concat([diffs, handlabel_paired_diffs()], ignore_index=True)
    rows.to_csv(OD / "osm_scores.csv", index=False); diffs.to_csv(OD / "osm_single_vs_combined.csv", index=False)
    ksub.to_csv(OD / "osm_ensemble_size.csv", index=False); stab.to_csv(OD / "osm_stability.csv", index=False)
    figure_single_vs_multi(rows, diffs)
    pd.set_option("display.width", 250); pd.set_option("display.max_columns", 40)
    for t in (rows, diffs, ksub, stab):
        log("\n" + t.round(4).to_string(index=False))


def handlabel_paired_diffs():
    """Hand labels (conf <= 2): combined minus average single run, with a paired stratified bootstrap."""
    meta, groups = selection(); R = len(SEEDS)
    z = np.load(SW / "pred_areas.npz"); U, P = z["U"], z["P"]
    V, W = RE.load_val(meta)
    cls, votes, pmean, maj, top = combine(P[:, np.searchsorted(U, groups["handlabel"]["pos"])])
    sel = (V.confidence.fillna(3) <= 2).values
    r_, s_ = V.true_class.values[sel], V.stratum.values[sel]
    Ps = {f"seed {s}": cls[i][sel].astype(int) for i, s in enumerate(SEEDS)}
    Ps["combined: majority vote"] = maj[sel].astype(int); Ps["combined: mean probability"] = pmean.argmax(0)[sel] + 1
    d = RE.boot_strata(r_, Ps, s_, W)
    single = np.mean([d[f"seed {s}"] for s in SEEDS], 0)
    f_run = [RE.weighted_metrics(r_, Ps[f"seed {s}"], s_, W)[0] for s in SEEDS]
    out = []
    for k in ("combined: majority vote", "combined: mean probability"):
        fk = RE.weighted_metrics(r_, Ps[k], s_, W)[0]; dd = d[k] - single
        out += [{"test": "hand labels (313 points)", "comparison": f"{k} minus average single run",
                 "diff_macro_F1": fk - np.mean(f_run), "lo": RE.ci(dd)[0], "hi": RE.ci(dd)[1]},
                {"test": "hand labels (313 points)", "comparison": f"{k} minus best single run",
                 "diff_macro_F1": fk - max(f_run), "lo": np.nan, "hi": np.nan},
                {"test": "hand labels (313 points)", "comparison": f"{k} minus worst single run",
                 "diff_macro_F1": fk - min(f_run), "lo": np.nan, "hi": np.nan}]
    return pd.DataFrame(out)


def figure_single_vs_multi(osm, diffs):
    """Gain of the 10-seed combination over single runs, paired (same test cells), on each test set."""
    import matplotlib; matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    hl = pd.read_csv(SO / "handlabel_scores.csv")
    hl = hl[hl.subset == "confidence<=2 (headline)"].assign(test="hand labels (313 points)")
    tabs = [osm[osm.test == t] for t in osm.test.unique() if t.startswith("OSM cells")] + [hl]
    fig, axs = plt.subplots(1, 2, figsize=(11, 4.4))
    run_c, comb_c, muted = "#8a8a8a", "#1f5fa8", "#6b6b6b"
    for ax, t in zip(axs, tabs):
        name = t.test.iloc[0]
        runs = t[t.model.str.startswith("seed ")].macro_F1.values
        maj = t[t.model == "combined: majority vote"].macro_F1.iloc[0]
        ax.axvline(0, color="#bdbdbd", lw=1)
        ax.scatter(maj - runs, np.full(len(runs), 2), s=46, color=run_c, alpha=.85, zorder=3, edgecolor="white", linewidth=1)
        ax.text(0, 2.35, "majority vote minus each single run", fontsize=9, color=muted, ha="center")
        for yy, k, lab in ((1, "combined: majority vote", "majority vote"), (0, "combined: mean probability", "mean probability")):
            r = diffs[(diffs.test == name) & (diffs.comparison == f"{k} minus average single run")].iloc[0]
            ax.errorbar(r.diff_macro_F1, yy, xerr=[[r.diff_macro_F1 - r.lo], [r.hi - r.diff_macro_F1]], fmt="D", ms=8,
                        color=comb_c, ecolor="#9bb7dd", elinewidth=2, capsize=0, zorder=3)
            ax.text(r.diff_macro_F1, yy + .18, f"{lab} vs average run:\n{r.diff_macro_F1:+.4f} [{r.lo:+.4f}, {r.hi:+.4f}]",
                    fontsize=8.5, color=INK, ha="center", va="bottom")
        vals = np.r_[maj - runs, diffs[diffs.test == name][["lo", "hi"]].values.ravel()]
        vals = vals[np.isfinite(vals)]; span = max(abs(vals).max(), 1e-3) * 1.15
        ax.set_xlim(-span, span); ax.set_ylim(-.6, 2.8); ax.set_yticks([])
        ax.set_title(f"{name}\nsingle runs: {runs.min():.3f}-{runs.max():.3f}, majority vote: {maj:.3f}", fontsize=10, color=INK)
        ax.set_xlabel("macro-F1 difference (> 0: combination better)\nbar = paired 95% CI", fontsize=8.5, color=muted)
        ax.xaxis.set_major_locator(plt.MaxNLocator(5, symmetric=True)); ax.tick_params(axis="x", labelsize=8.5)
        ax.grid(axis="x", color="#eeeeee", lw=.8); ax.set_axisbelow(True)
        for sp in ("top", "right", "left"):
            ax.spines[sp].set_visible(False)
    fig.suptitle("does combining 10 seeds beat a single run? (20 m model, same test cells for every run)", fontsize=12.5, color=INK)
    fig.tight_layout(); fig.savefig(SO / "single_vs_combined_accuracy.png", dpi=110); plt.close(fig)


# ----------------------------------------------------------------------------- full HMDA map (5-seed ensemble)
# Every valid 20 m cell inside HMDA (19.1 M) is predicted by the seed models in LU_MAP_SEEDS (default 1-5, the
# recommended ensemble). The final class is the argmax of the mean probability; the majority vote, vote shares
# and per-run classes are kept too. Predictions are written per chunk (work/full/), so an interrupted run resumes.
MAP_SEEDS = [int(s) for s in os.environ.get("LU_MAP_SEEDS", "1,2,3,4,5").split(",")]
CHUNK = 1_000_000
FD = SW / "full"


def full_cells():
    meta = json.loads((WORK / "meta.json").read_text())
    inside, tr = hmda_mask(meta)
    return meta, tr, np.flatnonzero((inside & np.load(WORK / "valid.npy")).ravel())


def chunk_path(k):
    return FD / f"s{'-'.join(map(str, MAP_SEEDS))}_c{k:03d}.npy"


def stage_fullmap():
    meta, tr, flat = full_cells(); pos = pos_of(flat, vflat()); FD.mkdir(exist_ok=True)
    models = [pickle.load(open(SW / f"model_s{s}.pkl", "rb"))[0] for s in MAP_SEEDS]
    X, _ = feats(); n = len(pos); nch = -(-n // CHUNK)
    todo = [k for k in range(nch) if not chunk_path(k).exists()]
    log(f"{n:,} HMDA cells, seeds {MAP_SEEDS}, {nch} chunks, {len(todo)} to do")
    t0 = time.time()
    for j, k in enumerate(todo, 1):
        a, b = k * CHUNK, min(n, (k + 1) * CHUNK)
        Xc = np.asarray(X[pos[a:b]])
        P = np.stack([m.predict_proba(Xc) for m in models]).astype(np.float16)
        np.save(FD / "tmp.npy", P); (FD / "tmp.npy").replace(chunk_path(k))
        el = time.time() - t0
        log(f"chunk {k + 1}/{nch} done ({j}/{len(todo)} this run), {el / 60:.1f} min, ~{el / j * (len(todo) - j) / 60:.0f} min left")
    log("fullmap done")


def stage_fullreport():
    meta, tr, flat = full_cells(); ny, nx = meta["ny"], meta["nx"]; R = len(MAP_SEEDS); n = len(flat)
    runs = np.zeros((R, ny * nx), np.uint8); comb = np.zeros((13, ny * nx), np.uint8)
    unan = 0; mp_ne_maj = 0
    for k in range(-(-n // CHUNK)):
        f = flat[k * CHUNK:(k + 1) * CHUNK]
        P = np.load(chunk_path(k)).astype(np.float32); assert P.shape[:2] == (R, len(f))
        cls, votes, pmean, maj, top = combine(P)
        final = pmean.argmax(0).astype(np.uint8) + 1
        runs[:, f] = cls
        comb[0, f] = final; comb[1, f] = maj; comb[2, f] = top * 100 // R
        comb[3:8, f] = votes * 100 // R; comb[8:13, f] = np.round(pmean * 100)
        unan += int((top == R).sum()); mp_ne_maj += int((final != maj).sum())
    FM = SO / "full_map"; FM.mkdir(exist_ok=True)
    sh = lambda a: a.reshape(-1, ny, nx)
    write_tif(FM / "hmda_final_class.tif", sh(comb[0]), tr, [f"class: argmax of mean probability, seeds {MAP_SEEDS}"], colormap=True)
    write_tif(FM / "hmda_combined.tif", sh(comb), tr,
              ["final class (argmax of mean probability)", "majority-vote class", "agreement: % of runs voting the majority class"] +
              [f"% of runs voting {NAMES[c]}" for c in CL] + [f"mean probability x100, {NAMES[c]}" for c in CL])
    write_tif(FM / "hmda_runs.tif", sh(runs), tr, [f"class, seed {s}" for s in MAP_SEEDS], colormap=True)

    km2 = CELL * CELL / 1e6
    cnt = lambda a: np.bincount(a[flat], minlength=6)[1:]
    comp = [{"map": f"seed {s}", **dict(zip(NAMES.values(), cnt(runs[i]) * km2))} for i, s in enumerate(MAP_SEEDS)]
    comp += [{"map": "combined: majority vote", **dict(zip(NAMES.values(), cnt(comb[1]) * km2))},
             {"map": "combined: mean probability (final)", **dict(zip(NAMES.values(), cnt(comb[0]) * km2))}]
    comp = pd.DataFrame(comp); comp["total"] = comp[list(NAMES.values())].sum(axis=1)
    pct = comp.copy(); pct[list(NAMES.values())] = pct[list(NAMES.values())].div(pct.total, axis=0) * 100
    comp.round(1).to_csv(FM / "hmda_composition_km2.csv", index=False)
    pct.drop(columns="total").round(2).to_csv(FM / "hmda_composition_pct.csv", index=False)
    summ = {"cells": n, "area_km2": n * km2, "seeds": " ".join(map(str, MAP_SEEDS)),
            "pct_unanimous": unan / n * 100, "pct_change_in_some_run": 100 - unan / n * 100,
            "pct_final_differs_from_majority_vote": mp_ne_maj / n * 100,
            **{f"pct_seed{s}_differs_from_final": (runs[i, flat] != comb[0, flat]).mean() * 100 for i, s in enumerate(MAP_SEEDS)}}
    pd.Series(summ).to_csv(FM / "hmda_stability.csv", header=["value"])
    figure_fullmap(sh(comb[0])[0], sh(comb[2])[0], R)
    pd.set_option("display.width", 250); pd.set_option("display.max_columns", 40)
    log("\n" + comp.round(1).to_string(index=False)); log("\n" + pct.round(2).to_string(index=False))
    log("\n" + pd.Series(summ).to_string())


def figure_fullmap(final, agree, R, step=4):
    import matplotlib; matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import ListedColormap
    from matplotlib.patches import Patch
    cm = ListedColormap(["#ffffff"] + [COLORS[c] for c in CL])
    fig, axs = plt.subplots(1, 2, figsize=(18, 9.2))
    axs[0].imshow(final[::step, ::step], cmap=cm, vmin=0, vmax=5, interpolation="nearest")
    axs[0].set_title(f"final map: mean probability of {R} seeds", fontsize=12, color=INK)
    axs[0].legend(handles=[Patch(color=COLORS[c], label=NAMES[c]) for c in CL], loc="lower left", fontsize=10, frameon=False)
    a = np.where(final > 0, agree, np.nan)[::step, ::step]
    im = axs[1].imshow(a, cmap=ListedColormap(plt.get_cmap("Greys_r")(np.linspace(0, .85, 256))), vmin=20, vmax=100,
                       interpolation="nearest")
    axs[1].set_title(f"agreement: % of the {R} runs voting the majority class (dark = unstable)", fontsize=12, color=INK)
    fig.colorbar(im, ax=axs[1], shrink=.7)
    for ax in axs:
        _clean(ax)
    fig.suptitle(f"HMDA land use at 20 m (shown at {CELL * step} m)", fontsize=14, color=INK)
    fig.tight_layout(); fig.savefig(SO / "full_map" / "hmda_full_map.png", dpi=110); plt.close(fig)


# ----------------------------------------------------------------------------- figures


def _clean(ax):
    ax.set_xticks([]); ax.set_yticks([])
    for sp in ax.spines.values():
        sp.set_visible(False)


def figure_area(name, cls, maj, top, votes, n):
    import matplotlib; matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import ListedColormap
    from matplotlib.patches import Patch
    R = len(cls); cm = ListedColormap(["#ffffff"] + [COLORS[c] for c in CL])
    grey = ListedColormap(plt.get_cmap("Greys_r")(np.linspace(0, .85, 256)))
    fig, axs = plt.subplots(2, 7, figsize=(21, 7))
    for i in range(R):
        ax = axs.flat[i if i < 5 else i + 2]
        ax.imshow(cls[i].reshape(n, n), cmap=cm, vmin=0, vmax=5, interpolation="nearest")
        ax.set_title(f"run {i + 1} (seed {SEEDS[i]})", fontsize=10, color=INK)
    axs[0, 5].imshow(maj.reshape(n, n), cmap=cm, vmin=0, vmax=5, interpolation="nearest")
    axs[0, 5].set_title("combined: majority vote", fontsize=10, color=INK, fontweight="bold")
    im = axs[0, 6].imshow((top * 100 / R).reshape(n, n), cmap=grey, vmin=20, vmax=100, interpolation="nearest")
    axs[0, 6].set_title("agreement, % of runs\n(dark = unstable)", fontsize=10, color=INK)
    fig.colorbar(im, ax=axs[0, 6], shrink=.75)
    im = axs[1, 5].imshow((votes[1] * 100 / R).reshape(n, n), cmap="Reds", vmin=0, vmax=100, interpolation="nearest")
    axs[1, 5].set_title("% of runs voting\nnon-residential", fontsize=10, color=INK)
    fig.colorbar(im, ax=axs[1, 5], shrink=.75)
    axs[1, 6].axis("off")
    axs[1, 6].legend(handles=[Patch(color=COLORS[c], label=NAMES[c]) for c in CL], loc="center", fontsize=11, frameon=False)
    for ax in axs.flat:
        _clean(ax)
    fig.suptitle(f"{name.replace('_', ' ')}: 4 x 4 km at 20 m, ten seeds", fontsize=14, color=INK)
    fig.tight_layout(); fig.savefig(SO / f"area_{name}.png", dpi=100); plt.close(fig)


def figure_overview(meta, groups):
    """Where the areas are: boxes on the HMDA boundary."""
    import matplotlib; matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import geopandas as gpd
    aoi = gpd.read_file(REPO / "data" / "processed" / "aoi_utm44n.gpkg").to_crs(32644)
    fig, ax = plt.subplots(figsize=(8, 8))
    aoi.boundary.plot(ax=ax, color="#6b6b6b", linewidth=.8)
    h = AREA_KM * 500
    for name, (x, y) in AREAS.items():
        ax.add_patch(plt.Rectangle((x - h, y - h), 2 * h, 2 * h, fill=False, edgecolor="#c0392b", linewidth=1.5))
        ax.annotate(name.replace("_", " "), (x + h, y + h), xytext=(4, 2), textcoords="offset points", fontsize=8, color=INK)
    ax.set_aspect("equal"); _clean(ax)
    ax.set_title("the seven 4 x 4 km test areas (HMDA boundary in grey)", fontsize=11, color=INK)
    fig.tight_layout(); fig.savefig(SO / "areas_location.png", dpi=110); plt.close(fig)


if __name__ == "__main__":
    {"features": stage_features, "train": stage_train, "predict": stage_predict, "report": stage_report,
     "osmcv": stage_osmcv, "osmreport": stage_osmreport,
     "fullmap": stage_fullmap, "fullreport": stage_fullreport}[sys.argv[1]]()
