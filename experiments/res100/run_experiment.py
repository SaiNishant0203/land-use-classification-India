"""10 m vs 100 m land-use classification, with confidence intervals.

Usage: python run_experiment.py cv      # 100 m spatial CV (fits, caches OOF + timings)
       python run_experiment.py eval    # all scoring tables (needs cv)
"""
import sys, time, json, pickle
import numpy as np, pandas as pd, lightgbm as lgb
from pyproj import Transformer
from sklearn.model_selection import GroupKFold
from common import *
import features100 as F100

CL = [1, 2, 3, 4, 5]
RNG_B = 1000                  # bootstrap replicates
MIN_LFRAC, PURE = 0.5, 0.8    # block must be >=50% OSM-labelled; "pure" subset >=80% one class
CAP_PER_CLASS_TILE = 100      # 10 m used <=200 px/class/tile of 160,000; 100 m has 1,600 cells/tile
EXCL_M = 400                 # drop training cells within 400 m of a hand-label point (window radius 350 m)


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
    """Cs: dict name -> (G,5,5) per-group confusion. Resample groups, return per-name macro-F1 draws
    (paired: every model sees the same resampled groups)."""
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


# ----------------------------------------------------------------------------- data
def load_all():
    g = F100.load()
    minx, maxy = g["origin"]
    valid = g["valid"]; ny, nx = valid.shape
    names, arr = F100.compute(g)
    rr, cc = np.nonzero(valid)
    X = arr[:, rr, cc].T.copy()
    x = minx + (cc + 0.5) * CELL; y = maxy - (rr + 0.5) * CELL
    labc = g["labc"][:, rr, cc].astype(int)                       # (6, N)
    nlab = labc[1:].sum(0)
    maj = labc[1:].argmax(0) + 1
    cell = pd.DataFrame({"x": x, "y": y, "row": rr, "col": cc, "maj": maj,
                         "lfrac": nlab / 100.0, "purity": labc[1:].max(0) / np.maximum(nlab, 1)})
    kx = (np.floor(x / 4000) * 4).astype(int); ky = (np.floor(y / 4000) * 4).astype(int)
    cell["group"] = (kx // 12).astype(str) + "_" + (ky // 12).astype(str)      # same 12 km blocks as the 10 m CV
    idx = -np.ones((ny, nx), int); idx[rr, cc] = np.arange(len(rr))
    return names, X, cell, idx, (minx, maxy)


def load_val(origin, idx):
    V = pd.read_parquet(LUP / "validation_features.parquet")
    K = pd.read_csv(LUP / "validation_key.csv")
    V = V.merge(K[["pid", "lon", "lat"]], on="pid")
    W = pd.read_csv(LUP / "validation_strata.csv", index_col=0)["weight"].to_dict()
    ux, uy = Transformer.from_crs(4326, 32644, always_xy=True).transform(V.lon.values, V.lat.values)
    V["x"], V["y"] = ux, uy
    c = np.floor((ux - origin[0]) / CELL).astype(int); r = np.floor((origin[1] - uy) / CELL).astype(int)
    V["cell"] = idx[r, c]
    V = V[V.true_class.notna()].copy(); V["true_class"] = V.true_class.astype(int)
    return V, W


def near_test(cell, V):
    near = np.zeros(len(cell), bool); cx, cy = cell.x.values, cell.y.values
    for px, py in zip(V.x.values, V.y.values):
        near |= (np.abs(cx - px) < EXCL_M) & (np.abs(cy - py) < EXCL_M) & (np.hypot(cx - px, cy - py) < EXCL_M)
    return near


def fit(X, y):
    t = time.time(); m = lgb.LGBMClassifier(**LGB).fit(X, y); return m, time.time() - t


# ----------------------------------------------------------------------------- stage 1: 100 m CV
def stage_cv():
    names, X, cell, idx, origin = load_all()
    V, W = load_val(origin, idx)
    log(f"{len(cell):,} valid cells; {len(names)} features")
    rows = (cell.lfrac >= MIN_LFRAC).values & ~near_test(cell, V)
    # mimic the 10 m design (<=200 random pixels per class per tile): cap cells per class per tile
    tkey = (np.floor(cell.x / 4000)).astype(int).astype(str) + "_" + (np.floor(cell.y / 4000)).astype(int).astype(str)
    rng = np.random.default_rng(7)
    cand = pd.DataFrame({"i": np.nonzero(rows)[0], "t": tkey[rows].values, "c": cell.maj[rows].values})
    cand["r"] = rng.random(len(cand))
    keep = cand.sort_values("r").groupby(["t", "c"]).head(CAP_PER_CLASS_TILE)["i"].values
    rows = np.zeros(len(cell), bool); rows[keep] = True
    log(f"training rows: {rows.sum():,} cells (>= {MIN_LFRAC:.0%} OSM-labelled, not near a test point); "
        f"classes {cell.maj[rows].value_counts().sort_index().to_dict()}")
    gnames = sorted(cell.group.unique()); gmap = {g: i for i, g in enumerate(gnames)}
    gid = cell.group.map(gmap).values
    ridx = np.nonzero(rows)[0]
    folds = list(GroupKFold(n_splits=5).split(ridx, cell.maj.values[ridx], gid[ridx]))
    fold_of_group = {}
    for f, (tr, te) in enumerate(folds):
        for g in np.unique(gid[ridx][te]):
            fold_of_group[g] = f
    cell_fold = np.array([fold_of_group.get(g, 0) for g in gid])
    sets = {"ALL": list(range(len(names))), "PHYS": [i for i, n in enumerate(names) if not F100.is_aef(n)]}
    timing = []
    oof = {}
    for sname, cols in sets.items():
        o = np.zeros(len(cell), int); Xs = X[:, cols]
        for f, (tr, te) in enumerate(folds):
            m, dt = fit(Xs[ridx[tr]], cell.maj.values[ridx[tr]])
            sel = cell_fold == f
            t = time.time(); o[sel] = m.predict(Xs[sel]); dp = time.time() - t
            timing.append({"set": sname, "fold": f, "n_train": len(tr), "n_features": len(cols),
                           "fit_s": dt, "predict_cells": int(sel.sum()), "predict_s": dp})
            log(f"{sname} fold {f}: fit {dt:.0f}s on {len(tr):,} rows, predicted {sel.sum():,} cells in {dp:.0f}s")
        oof[sname] = o
        # full-data model for the hand-label test
        m, dt = fit(Xs[ridx], cell.maj.values[ridx])
        t = time.time(); full_pred = m.predict(Xs); dp = time.time() - t
        timing.append({"set": sname, "fold": "full", "n_train": len(ridx), "n_features": len(cols),
                       "fit_s": dt, "predict_cells": len(cell), "predict_s": dp})
        pickle.dump((m, [names[i] for i in cols]), open(WORK / f"model100_{sname}.pkl", "wb"))
        np.save(WORK / f"full_pred100_{sname}.npy", full_pred)
        log(f"{sname} full model: fit {dt:.0f}s, whole-map predict {dp:.0f}s")
    np.savez(WORK / "cv100.npz", ALL=oof["ALL"], PHYS=oof["PHYS"], rows=rows, gid=gid, gnames=np.array(gnames))
    pd.DataFrame(timing).to_csv(OUT / "timing_100m.csv", index=False)
    cell.to_parquet(WORK / "cell.parquet")
    log("cv stage done")


# ----------------------------------------------------------------------------- stage 2: scoring
def stage_eval():
    names, X, cell, idx, origin = load_all()
    V, W = load_val(origin, idx)
    z = np.load(WORK / "cv100.npz", allow_pickle=True)
    rows, gid, gnames = z["rows"], z["gid"], list(z["gnames"]); G = len(gnames)
    res = []

    # ---- (1) OSM, block level: 100 m model scored on 100 m cells (majority OSM label)
    for sname in ("ALL", "PHYS"):
        o = z[sname]
        for sub, sel in (("all labelled cells", rows), (f"pure cells (>={PURE:.0%} one class)", rows & (cell.purity.values >= PURE))):
            C = group_conf(gid[sel], cell.maj.values[sel], o[sel], G)
            m, f = macro_f1(C.sum(0)); d = boot_groups({"x": C})["x"]
            res.append({"experiment": "OSM, 100 m cells vs OSM majority label", "model": f"100 m {sname}", "subset": sub,
                        "n": int(sel.sum()), "macro_F1": m, "lo": ci(d)[0], "hi": ci(d)[1],
                        **{f"F1_{c}": f[c - 1] for c in CL}})

    # ---- (2) OSM, pixel level: both models scored on the SAME 393k 10 m sample pixels, 10 m labels
    oofp = pd.read_parquet(LUP / "oof_predictions.parquet")
    cx = np.floor((oofp.x.values - origin[0]) / CELL).astype(int); cr = np.floor((origin[1] - oofp.y.values) / CELL).astype(int)
    ci_ = idx[cr, cx]; assert (ci_ >= 0).all()
    pg = gid[ci_]
    ref = oofp.label.values.astype(int)
    pix = {"10 m ALL": oofp["oof_ALL"].values.astype(int), "10 m PHYS (S2+BLD)": oofp["oof_S2+BLD"].values.astype(int),
           "100 m ALL": z["ALL"][ci_], "100 m PHYS": z["PHYS"][ci_]}
    Cs = {k: group_conf(pg, ref, v, G) for k, v in pix.items()}
    d = boot_groups(Cs)
    for k in pix:
        m, f = macro_f1(Cs[k].sum(0))
        res.append({"experiment": "OSM, same 393k 10 m pixels, 10 m labels", "model": k, "subset": "all sampled pixels",
                    "n": len(ref), "macro_F1": m, "lo": ci(d[k])[0], "hi": ci(d[k])[1], **{f"F1_{c}": f[c - 1] for c in CL}})
    pairs = [("100 m ALL", "10 m ALL"), ("100 m PHYS", "10 m PHYS (S2+BLD)")]
    diffs = []
    for a, b in pairs:
        dd = d[a] - d[b]; diffs.append({"experiment": "OSM pixels (paired, 12 km-block bootstrap)",
                                        "comparison": f"{a} minus {b}", "diff_macro_F1": macro_f1(Cs[a].sum(0))[0] - macro_f1(Cs[b].sum(0))[0],
                                        "lo": ci(dd)[0], "hi": ci(dd)[1]})

    # ---- (3) hand labels, conf<=2 (headline) and conf<=2 without road pixels
    sys.path.insert(0, str(REPO / "scripts" / "lu"))
    import lu_features as LF                                       # the repo's own 10 m features, for timing only
    m10, cols10 = pickle.load(open(LUP / "model_all_2023.pkl", "rb"))
    S = pd.concat([pd.read_parquet(p) for p in sorted((LUP / "samples_parts").glob("samples_part*.parquet"))], ignore_index=True)
    phys10 = [c for c in cols10 if not F100.is_aef(c)]
    m10p, t10p = fit(S[phys10], S.label.values)
    log(f"10 m PHYS refit {t10p:.0f}s on {len(S):,} rows, {len(phys10)} features")
    m100 = {s: pickle.load(open(WORK / f"model100_{s}.pkl", "rb")) for s in ("ALL", "PHYS")}
    vt = V.true_class.values; strata = V.stratum.values
    vp = {"10 m ALL": m10.predict(V[cols10]).astype(int), "10 m PHYS (S2+BLD)": m10p.predict(V[phys10]).astype(int)}
    for s, (m, cols) in m100.items():
        vp[f"100 m {s}"] = m.predict(X[V.cell.values][:, [names.index(c) for c in cols]]).astype(int)
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
    t100 = pd.read_csv(OUT / "timing_100m.csv")
    LF.LURAW = DATA; tiles = LF.tiles(); k = "x228_y1920"
    t = time.time(); nm, arr = LF.compute(k); tf = time.time() - t
    t = time.time(); m10.predict(pd.DataFrame(arr.reshape(len(nm), -1).T, columns=nm)[cols10]); tp = time.time() - t
    S_all = S[cols10]
    m10b, t10a = fit(S_all, S.label.values)
    t = time.time(); g = F100.load(); F100.compute(g); tf100 = time.time() - t
    full = t100[t100.fold == "full"].set_index("set")
    cost = pd.DataFrame([
        {"model": "10 m ALL", "train_rows": len(S), "features": len(cols10), "fit_s": t10a,
         "map_s_estimate": (tf + tp) * len(tiles), "note": f"features {tf:.1f}s + predict {tp:.1f}s per 4 km tile x {len(tiles)} tiles"},
        {"model": "10 m PHYS", "train_rows": len(S), "features": len(phys10), "fit_s": t10p, "map_s_estimate": np.nan, "note": ""},
        {"model": "100 m ALL", "train_rows": int(full.loc["ALL", "n_train"]), "features": int(full.loc["ALL", "n_features"]),
         "fit_s": full.loc["ALL", "fit_s"], "map_s_estimate": tf100 + full.loc["ALL", "predict_s"],
         "note": f"whole-map features {tf100:.1f}s + predict {full.loc['ALL', 'predict_s']:.1f}s"},
        {"model": "100 m PHYS", "train_rows": int(full.loc["PHYS", "n_train"]), "features": int(full.loc["PHYS", "n_features"]),
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
