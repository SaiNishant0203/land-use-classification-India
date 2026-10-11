"""Coarse cells (LU_CELL = 20/50/100 m) vs the 10 m model, with confidence intervals.

Usage (set LU_CELL first; build_grid.py must have run):
    python run_experiment.py cv      # spatial CV + full models + whole-map timing (caches to work/r<CELL>/)
    python run_experiment.py eval    # all scoring tables -> results/r<CELL>/
"""
import sys, time, json, pickle
import numpy as np, pandas as pd, lightgbm as lgb
from pyproj import Transformer
from sklearn.model_selection import GroupKFold
from common import *
import features_coarse as FC

CL = [1, 2, 3, 4, 5]
RNG_B = 1000                  # bootstrap replicates
MIN_LFRAC, PURE = 0.5, 0.8    # cell must be >=50% OSM-labelled; "pure" subset >=80% one class
CAP_PER_CLASS_TILE = 100      # 10 m used <=200 px/class/tile of 160,000; coarse grids use 100 cells/class/tile
EXCL_M = 400                  # drop training cells within 400 m of a hand-label point


# ----------------------------------------------------------------------------- scoring helpers
def macro_f1(C):
    """C[ref, pred] confusion counts (5x5) -> (macro F1, per-class F1)."""
    tp = np.diag(C).astype(float); fp = C.sum(0) - tp; fn = C.sum(1) - tp
    f = np.where(2 * tp + fp + fn > 0, 2 * tp / np.maximum(2 * tp + fp + fn, 1), 0.0)
    return f.mean(), f


def group_conf(gid, ref, pred, n_groups):
    k = gid * 25 + (ref - 1) * 5 + (pred - 1)
    return np.bincount(k, minlength=n_groups * 25).reshape(n_groups, 5, 5)


def boot_groups(Cs, B=RNG_B, seed=0):
    """Cs: name -> (G,5,5) per-group confusion. Resample groups; every model sees the same draws (paired)."""
    rng = np.random.default_rng(seed); G = next(iter(Cs.values())).shape[0]
    out = {k: [] for k in Cs}
    for _ in range(B):
        ii = rng.integers(0, G, G)
        for k, C in Cs.items():
            out[k].append(macro_f1(C[ii].sum(0))[0])
    return {k: np.array(v) for k, v in out.items()}


def ci(a):
    return float(np.percentile(a, 2.5)), float(np.percentile(a, 97.5))


def weighted_metrics(ref, pred, strata, W):
    """Olofsson area-weighted estimator, identical to 07_eval_handlabels.weighted. Returns macro-F1, per-class F1."""
    P = np.zeros((5, 5))                                   # [map, ref]
    for h, w in W.items():
        m = strata == h
        if m.sum() == 0:
            continue
        P += w * np.bincount((pred[m] - 1) * 5 + (ref[m] - 1), minlength=25).reshape(5, 5) / m.sum()
    f1 = []
    for c in range(5):
        ua = P[c, c] / P[c].sum() if P[c].sum() > 0 else 0
        pa = P[c, c] / P[:, c].sum() if P[:, c].sum() > 0 else 0
        f1.append(2 * ua * pa / (ua + pa) if ua + pa > 0 else 0.0)
    return float(np.mean(f1)), np.array(f1)


def boot_strata(ref, preds, strata, W, B=RNG_B, seed=0):
    rng = np.random.default_rng(seed)
    idx = [np.nonzero(strata == h)[0] for h in np.unique(strata)]
    out = {k: [] for k in preds}
    for _ in range(B):
        ii = np.concatenate([rng.choice(ix, len(ix)) for ix in idx if len(ix)])
        for k, p in preds.items():
            out[k].append(weighted_metrics(ref[ii], p[ii], strata[ii], W)[0])
    return {k: np.array(v) for k, v in out.items()}


# ----------------------------------------------------------------------------- geometry / groups
def group_table():
    """12 km blocks (3 x 3 tiles) of every HMDA tile; identical to the 10 m CV's grouping."""
    T = json.loads((DATA / "feat_2023" / "tiles.json").read_text())
    keys = sorted({(int(k[1:].split("_y")[0]) // 12) * 1000 + int(k.split("_y")[1]) // 12 for k in T})
    return np.array(keys)


def gid_of(x, y, keys):
    gx = (np.floor(np.asarray(x) / 4000).astype(int) * 4) // 12
    gy = (np.floor(np.asarray(y) / 4000).astype(int) * 4) // 12
    k = gx * 1000 + gy
    pos = np.searchsorted(keys, k); assert (keys[np.minimum(pos, len(keys) - 1)] == k).all()
    return pos


def cell_of(x, y, meta):
    r = np.floor((meta["maxy"] - np.asarray(y)) / CELL).astype(int); c = np.floor((np.asarray(x) - meta["minx"]) / CELL).astype(int)
    return r * meta["nx"] + c


def load_val(meta):
    V = pd.read_parquet(LUP / "validation_features.parquet")
    K_ = pd.read_csv(LUP / "validation_key.csv")
    V = V.merge(K_[["pid", "lon", "lat"]], on="pid")
    W = pd.read_csv(LUP / "validation_strata.csv", index_col=0)["weight"].to_dict()
    ux, uy = Transformer.from_crs(4326, 32644, always_xy=True).transform(V.lon.values, V.lat.values)
    V["x"], V["y"] = ux, uy
    V["flat"] = cell_of(ux, uy, meta)
    V = V[V.true_class.notna()].copy(); V["true_class"] = V.true_class.astype(int)
    return V, W


def fit(X, y):
    t = time.time(); m = lgb.LGBMClassifier(**LGB).fit(X, y); return m, time.time() - t


# ----------------------------------------------------------------------------- stage 1: CV
def stage_cv():
    grid = FC.open_grid(); meta = grid["meta"]; ny, nx = meta["ny"], meta["nx"]
    V, W = load_val(meta)
    valid = np.array(grid["valid"]); labc = grid["labc"]
    nlab = np.zeros((ny, nx), np.int16)
    for c in range(1, 6):
        nlab += np.array(labc[c]).astype(np.int16)
    cand = valid & (nlab / (K * K) >= MIN_LFRAC)
    rad = int(np.ceil(EXCL_M / CELL))
    for r0, c0 in zip((meta["maxy"] - V.y.values) // CELL, (V.x.values - meta["minx"]) // CELL):     # drop cells near test points
        r0, c0 = int(r0), int(c0)
        rs, cs = slice(max(0, r0 - rad), r0 + rad + 1), slice(max(0, c0 - rad), c0 + rad + 1)
        yy, xx = np.mgrid[rs, cs]
        near = np.hypot((yy - r0) * CELL, (xx - c0) * CELL) < EXCL_M
        cand[rs, cs] &= ~near
    rr, cc = np.nonzero(cand)
    cnt = np.stack([np.array(labc[c])[rr, cc] for c in range(1, 6)])
    pool = pd.DataFrame({"flat": rr * nx + cc, "maj": cnt.argmax(0) + 1,
                         "tile": (rr // NT) * 10000 + cc // NT})
    log(f"{CELL} m: {int(valid.sum()):,} valid cells, {len(pool):,} candidate cells (>= {MIN_LFRAC:.0%} OSM-labelled, not near a test point)")
    pool["r"] = np.random.default_rng(7).random(len(pool))
    rows = pool.sort_values("r").groupby(["tile", "maj"]).head(CAP_PER_CLASS_TILE).sort_values("flat")
    log(f"training rows: {len(rows):,}; classes {rows.maj.value_counts().sort_index().to_dict()}")
    del cnt, pool

    # cells whose features we need: training rows, cells holding the 10 m sample pixels, hand-label cells
    oofp = pd.read_parquet(LUP / "oof_predictions.parquet", columns=["x", "y"])
    pix_flat = cell_of(oofp.x.values, oofp.y.values, meta)
    U = np.unique(np.concatenate([rows.flat.values, pix_flat, V.flat.values]))
    log(f"{len(U):,} cells to featurise")
    t = time.time(); names, X = FC.extract(grid, U); t_feat = time.time() - t
    ur, uc = U // nx, U % nx
    cnt = np.stack([np.array(labc[c][ur, uc]) for c in range(1, 6)]).astype(int)
    maj_U = cnt.argmax(0) + 1; pur_U = cnt.max(0) / np.maximum(cnt.sum(0), 1)
    keys = group_table(); gid_U = gid_of(meta["minx"] + (uc + .5) * CELL, meta["maxy"] - (ur + .5) * CELL, keys)
    in_rows = np.isin(U, rows.flat.values)
    pos_rows = np.nonzero(in_rows)[0]

    folds = list(GroupKFold(n_splits=5).split(pos_rows, maj_U[pos_rows], gid_U[pos_rows]))
    fold_of_group = {int(g): f for f, (tr, te) in enumerate(folds) for g in np.unique(gid_U[pos_rows][te])}
    fold_U = np.array([fold_of_group.get(int(g), 0) for g in gid_U])
    sets = {"ALL": list(range(len(names))), "PHYS": [i for i, n in enumerate(names) if not FC.is_aef(n)]}
    timing, oof = [], {}
    for sname, cols in sets.items():
        o = np.zeros(len(U), int); Xs = X[:, cols]
        for f, (tr, te) in enumerate(folds):
            m, dt = fit(Xs[pos_rows[tr]], maj_U[pos_rows[tr]])
            sel = fold_U == f
            t = time.time(); o[sel] = m.predict(Xs[sel]); dp = time.time() - t
            timing.append({"set": sname, "fold": f, "n_train": len(tr), "n_features": len(cols), "fit_s": dt,
                           "predict_cells": int(sel.sum()), "predict_s": dp})
            log(f"{sname} fold {f}: fit {dt:.0f}s on {len(tr):,} rows")
        oof[sname] = o
        m, dt = fit(Xs[pos_rows], maj_U[pos_rows])
        timing.append({"set": sname, "fold": "full", "n_train": len(pos_rows), "n_features": len(cols), "fit_s": dt,
                       "predict_cells": 0, "predict_s": 0})
        pickle.dump((m, [names[i] for i in cols]), open(WORK / f"model_{sname}.pkl", "wb"))
        log(f"{sname} full model: fit {dt:.0f}s")
        if sname == "ALL":                                         # honest whole-map cost: features + predict, strip by strip
            tf = tp = 0.0; ncell = 0
            for r0, r1 in FC.strips(ny):
                t = time.time(); gs, off = FC.load_strip(grid, r0, r1); nm, F = FC.compute(gs)
                v = gs["valid"][off:off + (r1 - r0)]
                Xm = np.stack([F[n][off:off + (r1 - r0)][v] for n in nm], 1); tf += time.time() - t
                t = time.time(); m.predict(Xm); tp += time.time() - t; ncell += len(Xm)
            timing.append({"set": "ALL", "fold": "map", "n_train": 0, "n_features": len(names), "fit_s": 0,
                           "predict_cells": ncell, "predict_s": tp, "features_s": tf})
            log(f"whole map: {ncell:,} cells, features {tf:.0f}s + predict {tp:.0f}s")
    np.save(WORK / "X_U.npy", X)
    np.savez(WORK / "cv.npz", U=U, in_rows=in_rows, maj=maj_U, purity=pur_U, gid=gid_U, oof_ALL=oof["ALL"],
             oof_PHYS=oof["PHYS"], names=np.array(names), n_groups=len(keys), t_feat_subset=t_feat)
    pd.DataFrame(timing).to_csv(OUT / "timing.csv", index=False)
    log("cv stage done")


# ----------------------------------------------------------------------------- stage 2: scoring
def stage_eval():
    meta = json.loads((WORK / "meta.json").read_text())
    V, W = load_val(meta)
    z = np.load(WORK / "cv.npz", allow_pickle=True)
    U, in_rows, maj, pur, gid, G = z["U"], z["in_rows"], z["maj"], z["purity"], z["gid"], int(z["n_groups"])
    names = list(z["names"]); X = np.load(WORK / "X_U.npy", mmap_mode="r")
    R = f"{CELL} m"; res = []
    keys = group_table()

    # ---- (1) OSM, cell level: coarse model scored on coarse cells (majority OSM label)
    for sname in ("ALL", "PHYS"):
        o = z[f"oof_{sname}"]
        for sub, sel in (("all labelled cells", in_rows), (f"pure cells (>={PURE:.0%} one class)", in_rows & (pur >= PURE))):
            C = group_conf(gid[sel], maj[sel], o[sel], G)
            m, f = macro_f1(C.sum(0)); d = boot_groups({"x": C})["x"]
            res.append({"experiment": f"OSM, {R} cells vs OSM majority label", "model": f"{R} {sname}", "subset": sub,
                        "n": int(sel.sum()), "macro_F1": m, "lo": ci(d)[0], "hi": ci(d)[1], **{f"F1_{c}": f[c - 1] for c in CL}})

    # ---- (2) OSM, pixel level: both models scored on the SAME 393k 10 m sample pixels, 10 m labels
    oofp = pd.read_parquet(LUP / "oof_predictions.parquet")
    pix_flat = cell_of(oofp.x.values, oofp.y.values, meta)
    pp = np.searchsorted(U, pix_flat); assert (U[pp] == pix_flat).all()
    pg = gid_of(oofp.x.values, oofp.y.values, keys)
    ref = oofp.label.values.astype(int)
    pix = {"10 m ALL": oofp["oof_ALL"].values.astype(int), "10 m PHYS (S2+BLD)": oofp["oof_S2+BLD"].values.astype(int),
           f"{R} ALL": z["oof_ALL"][pp], f"{R} PHYS": z["oof_PHYS"][pp]}
    Cs = {k: group_conf(pg, ref, v, G) for k, v in pix.items()}
    d = boot_groups(Cs)
    for k in pix:
        m, f = macro_f1(Cs[k].sum(0))
        res.append({"experiment": "OSM, same 393k 10 m pixels, 10 m labels", "model": k, "subset": "all sampled pixels",
                    "n": len(ref), "macro_F1": m, "lo": ci(d[k])[0], "hi": ci(d[k])[1], **{f"F1_{c}": f[c - 1] for c in CL}})
    pairs = [(f"{R} ALL", "10 m ALL"), (f"{R} PHYS", "10 m PHYS (S2+BLD)")]
    diffs = []
    for a, b in pairs:
        dd = d[a] - d[b]
        diffs.append({"experiment": "OSM pixels (paired, 12 km-block bootstrap)", "comparison": f"{a} minus {b}",
                      "diff_macro_F1": macro_f1(Cs[a].sum(0))[0] - macro_f1(Cs[b].sum(0))[0], "lo": ci(dd)[0], "hi": ci(dd)[1]})

    # ---- (3) hand labels, conf<=2 (headline) and conf<=2 without road pixels
    sys.path.insert(0, str(REPO / "scripts" / "lu"))
    import lu_features as LF                                       # the repo's own 10 m features, for timing only
    m10, cols10 = pickle.load(open(LUP / "model_all_2023.pkl", "rb"))
    S = pd.concat([pd.read_parquet(p) for p in sorted((LUP / "samples_parts").glob("samples_part*.parquet"))], ignore_index=True)
    phys10 = [c for c in cols10 if not FC.is_aef(c)]
    m10p, t10p = fit(S[phys10], S.label.values)
    log(f"10 m PHYS refit {t10p:.0f}s on {len(S):,} rows, {len(phys10)} features")
    vpos = np.searchsorted(U, V.flat.values); assert (U[vpos] == V.flat.values).all()
    vt = V.true_class.values; strata = V.stratum.values
    vp = {"10 m ALL": m10.predict(V[cols10]).astype(int), "10 m PHYS (S2+BLD)": m10p.predict(V[phys10]).astype(int)}
    for s in ("ALL", "PHYS"):
        m, cols = pickle.load(open(WORK / f"model_{s}.pkl", "rb"))
        vp[f"{R} {s}"] = m.predict(np.asarray(X[vpos])[:, [names.index(c) for c in cols]]).astype(int)
    for sub, sel in (("confidence<=2 (headline)", (V.confidence.fillna(3) <= 2).values),
                     ("confidence<=2, no road pixels", ((V.confidence.fillna(3) <= 2) & (V.is_road.fillna(0) == 0)).values)):
        r_, s_ = vt[sel], strata[sel]; P = {k: v[sel] for k, v in vp.items()}
        d = boot_strata(r_, P, s_, W)
        for k, p in P.items():
            m, f = weighted_metrics(r_, p, s_, W)
            res.append({"experiment": "hand labels (325-pixel test set)", "model": k, "subset": sub, "n": int(sel.sum()),
                        "macro_F1": m, "lo": ci(d[k])[0], "hi": ci(d[k])[1], **{f"F1_{c}": f[c - 1] for c in CL}})
        for a, b in pairs:
            dd = d[a] - d[b]
            diffs.append({"experiment": f"hand labels, {sub} (paired, stratified bootstrap)", "comparison": f"{a} minus {b}",
                          "diff_macro_F1": weighted_metrics(r_, P[a], s_, W)[0] - weighted_metrics(r_, P[b], s_, W)[0],
                          "lo": ci(dd)[0], "hi": ci(dd)[1]})

    # ---- (4) compute cost
    t = pd.read_csv(OUT / "timing.csv")
    LF.LURAW = DATA; tiles = LF.tiles(); k = "x228_y1920"
    t0 = time.time(); nm, arr = LF.compute(k); tf = time.time() - t0
    t0 = time.time(); m10.predict(pd.DataFrame(arr.reshape(len(nm), -1).T, columns=nm)[cols10]); tp = time.time() - t0
    _, t10a = fit(S[cols10], S.label.values)
    full = t[t.fold == "full"].set_index("set"); mp = t[t.fold == "map"].iloc[0]
    cost = pd.DataFrame([
        {"model": "10 m ALL", "train_rows": len(S), "features": len(cols10), "fit_s": t10a,
         "map_s_estimate": (tf + tp) * len(tiles), "note": f"features {tf:.1f}s + predict {tp:.1f}s per 4 km tile x {len(tiles)} tiles"},
        {"model": "10 m PHYS", "train_rows": len(S), "features": len(phys10), "fit_s": t10p, "map_s_estimate": np.nan, "note": ""},
        {"model": f"{R} ALL", "train_rows": int(full.loc["ALL", "n_train"]), "features": int(full.loc["ALL", "n_features"]),
         "fit_s": full.loc["ALL", "fit_s"], "map_s_estimate": mp.features_s + mp.predict_s,
         "note": f"{int(mp.predict_cells):,} cells: features {mp.features_s:.0f}s + predict {mp.predict_s:.0f}s"},
        {"model": f"{R} PHYS", "train_rows": int(full.loc["PHYS", "n_train"]), "features": int(full.loc["PHYS", "n_features"]),
         "fit_s": full.loc["PHYS", "fit_s"], "map_s_estimate": np.nan, "note": ""}])
    pd.DataFrame(res).to_csv(OUT / "scores.csv", index=False)
    pd.DataFrame(diffs).to_csv(OUT / "paired_differences.csv", index=False)
    cost.to_csv(OUT / "cost.csv", index=False)
    pd.set_option("display.width", 250); pd.set_option("display.max_columns", 30)
    log("\n" + pd.DataFrame(res)[["experiment", "model", "subset", "n", "macro_F1", "lo", "hi"]].round(3).to_string(index=False))
    log("\n" + pd.DataFrame(diffs).round(3).to_string(index=False))
    log("\n" + cost.round(1).to_string(index=False))


if __name__ == "__main__":
    {"cv": stage_cv, "eval": stage_eval}[sys.argv[1]]()
