"""
Retrain with candidate fixes and compare them across seeds (HANDOFF step 3).

Each seed changes the training cells drawn and LightGBM's row and column sampling, as
experiments/seedsensitivity. Every variant gets the same seeds, and each seed trains one model per
year, so differences are paired. The 313 hand labels are the common yardstick; they are now a
development set, because variants are chosen on them, so the final score must come from a new sample.

Variants (keys of VARIANTS):
  base        production settings (class_weight balanced, labels as 02_labels.py)
  cw_none     no class weights: the training mix as sampled
  cw_sqrt     weights towards the square root of the mapped class shares
  cw_prior    weights towards the mapped class shares
  nr_drop     OSM non-res cells with no building and no paving are removed from training
  nr_lc       the same cells take the land-cover label (open or trees) where the products agree
  built_drop  nr_drop, also for OSM residential cells
  ethan1      Ethan's 281 cells added to the 2023 training set, weight 1 (his class wins on overlap)
  ethan20     the same, weight 20
  water       2017 and 2020 water labels from JRC yearly water instead of the 80% occurrence rule
              (no effect on 2023, so not on the hand labels). Includes seasonal water.
  water2      the same, but at least 2 of the cell's 4 pixels must also be regular water: JRC
              occurrence >= 50, WorldCover 2021 water or Dynamic World 2023 water
  combo       cw_sqrt + nr_lc + water2, fixed before the full run
  combo_none, combo_prior   the same with cw_none or cw_prior, added after seeing the first results
"Building or paving": Open Buildings cover >= 0.05 in the cell (that year) or at least 2 of its 4
10 m pixels built in Dynamic World 2023 or WorldCover 2021.

Trees <-> open flipping is treated afterwards, on the probabilities: cells whose class is trees or
open in a year are assigned between the two by the mean of P(trees) / (P(trees) + P(open)) over the
three years. Scored as `<variant>+smooth`. It assumes no real trees <-> open change, by construction.

Stability is measured on a fixed 1% random sample of HMDA, predicted in all three years.

Usage: python 11_retrain_variants.py [--dry]     (finished fits are skipped, so reruns resume)
Output: outputs/lu20/retrain/{scores,paired,stability}.csv, RESULTS.md; cache/ and prob/ are working files
"""
import sys, json, time, pickle, importlib
import numpy as np, pandas as pd, geopandas as gpd, rasterio, lightgbm as lgb
from rasterio.features import rasterize
from rasterio.transform import from_origin
from common20 import *
import features20 as FX

T = importlib.import_module("04_train")
E = importlib.import_module("05_eval")

DRY = "--dry" in sys.argv
SEEDS = [1] if DRY else [1, 2, 3, 4, 5]
VARIANTS = {
    "base": {},
    "cw_none": {"cw": "none"},
    "cw_sqrt": {"cw": "sqrt"},
    "cw_prior": {"cw": "prior"},
    "nr_drop": {"labels": "nr_drop"},
    "nr_lc": {"labels": "nr_lc"},
    "built_drop": {"labels": "built_drop"},
    "ethan1": {"ethan": 1},
    "ethan20": {"ethan": 20},
    "water": {"labels": "water"},
    "water2": {"labels": "water2"},
    "combo": {"cw": "sqrt", "labels": "combo"},
    "combo_none": {"cw": "none", "labels": "combo"},
    "combo_prior": {"cw": "prior", "labels": "combo"},
}
if DRY:
    VARIANTS = {k: VARIANTS[k] for k in ["base", "cw_sqrt", "nr_lc", "ethan20", "water"]}
R = OUT / ("retrain_dry" if DRY else "retrain")
CA, PR = R / "cache", R / "prob"
for d in (R, CA, PR):
    d.mkdir(exist_ok=True)
NB = 50 if DRY else LGB["n_estimators"]
MAP_SHARE = {1: 0.098, 2: 0.091, 3: 0.030, 4: 0.152, 5: 0.629}      # year_2023 map (RESULTS.md), not the hand labels
BOOT = 1000


def aux_grid():
    """20 m counts from the 10 m products: paved pixels, and pixels the land-cover rule calls trees or open."""
    fp = CA / "aux.npz"
    if fp.exists():
        return dict(np.load(fp))
    T_ = tiles(); meta = json.loads((W20 / "grid_2023" / "meta.json").read_text())
    ny, nx = meta["ny"], meta["nx"]
    a = {k: np.zeros((ny, nx), np.uint8) for k in ("paved", "lc4", "lc5", "wat_ok")}
    for k, (x0, y0, x1, y1) in T_.items():
        with rasterio.open(RAW / "prod" / f"{k}.tif") as s:
            dw, wc, jrc, ghsc = (s.read(i) for i in (1, 2, 3, 4))
        ghs_built = (ghsc >= 11) & (ghsc <= 25)
        m = {"paved": (dw == 6) | (wc == 50), "lc4": (wc == 10) & (dw == 1),
             "lc5": np.isin(wc, [20, 30, 40, 60]) & np.isin(dw, [2, 4, 5, 7]) & ~ghs_built,
             "wat_ok": ((jrc >= 50) & (jrc <= 100)) | (wc == 80) | (dw == 0)}
        r0, c0 = int((meta["maxy"] - y1) / CELL), int((x0 - meta["minx"]) / CELL)
        for n, b in m.items():
            a[n][r0:r0 + NT, c0:c0 + NT] = b.reshape(NT, K, NT, K).sum((1, 3))
    np.savez_compressed(fp, **a)
    return a


def counts(year, grid, aux, key):
    """Per-class 10 m pixel counts of each cell (6, ny, nx) under the label rule `key`."""
    c = np.stack([np.array(grid["labc"][i]) for i in range(6)]).astype(np.int16)
    if key in ("nr_drop", "nr_lc", "built_drop", "combo"):
        bare = ~((np.nan_to_num(np.array(grid["mean"][BANDS.index("ob_cov")])) >= 0.05) | (aux["paved"] >= 2))
        m = bare & (c[2] > 0)
        log(f"  {year} {key}: {int(m.sum()):,} non-res cells without building or paving, of {int((c[2] > 0).sum()):,}")
        if key in ("nr_lc", "combo"):
            c[4][m] += aux["lc4"][m]; c[5][m] += aux["lc5"][m]
        c[2][m] = 0
        if key == "built_drop":
            c[1][bare] = 0
    if key in ("water", "water2", "combo") and year < 2023:
        w = np.load(W20 / "ext" / f"jrc_{year}.npz")["water"] >= 50
        assert w.shape == c.shape[1:]
        if key != "water":
            w &= aux["wat_ok"] >= 2
        free = np.maximum(K * K - c[1] - c[2], 0)
        c[3][:] = 0; c[3][w] = free[w]; c[4][w] = 0; c[5][w] = 0
    return c


def label_key(v, year):
    key = VARIANTS[v].get("labels", "base")
    return "base" if key in ("water", "water2") and year == 2023 else key


def same_as_base(v, year):
    s = VARIANTS[v]
    return not s.get("cw") and label_key(v, year) == "base" and not (s.get("ethan") and year == 2023)


def ethan_rows(grid):
    meta = grid["meta"]; e = pd.read_csv(LUP / "handlabelled_ethan.csv")
    r = ((meta["maxy"] - e.y) // CELL).astype(int); c = ((e.x - meta["minx"]) // CELL).astype(int)
    return pd.DataFrame({"flat": r * meta["nx"] + c, "label": e["class"].astype(int)})


def all_rows(years, vx, vy):
    """Training rows for every (year, label rule, seed), cached."""
    rows = {}
    aux = aux_grid()
    for y in years:
        fp = CA / f"rows_{y}.pkl"
        rows[y] = pickle.load(open(fp, "rb")) if fp.exists() else {}
        keys = sorted({label_key(v, y) for v in VARIANTS})
        if all((k, s) in rows[y] for k in keys for s in SEEDS):
            continue
        grid = FX.open_grid(y)
        for key in keys:
            if all((key, s) in rows[y] for s in SEEDS):
                continue
            c = counts(y, grid, aux, key)
            g = {**grid, "labv": c}
            for s in SEEDS:
                T.SEED = s
                rows[y][(key, s)] = T.sample(g, "labv", vx, vy)[["flat", "label"]]
            del c, g
        pickle.dump(rows[y], open(fp, "wb"))
    return rows


def features(y, flats):
    """Features at any set of cells, kept in one growing cache per year -> (names, sorted flats, X)."""
    fp, fn = CA / f"feat_{y}.npz", CA / f"feat_{y}_names.json"
    F, X, names = np.array([], np.int64), None, None
    if fp.exists():
        z = np.load(fp); F, X = z["flat"], z["X"]; names = json.loads(fn.read_text())
    miss = np.setdiff1d(flats, F)
    if len(miss):
        t = time.time(); names, Xn = FX.extract(FX.open_grid(y), miss)
        F2 = np.concatenate([F, miss]); X2 = Xn if X is None else np.vstack([X, Xn])
        o = np.argsort(F2); F, X = F2[o], X2[o]
        np.savez(fp, flat=F, X=X); fn.write_text(json.dumps(names))
        log(f"  {y}: features for {len(miss):,} more cells in {time.time() - t:.0f}s ({len(F):,} cached)")
    return names, F, X


def eval_cells(grid):
    """Hand-label cells (confidence <= 2) and the fixed 1% sample of HMDA -> (labels table, stability flats)."""
    v = E.hand_labels(grid)
    v = v[v.confidence.fillna(3) <= 2].reset_index(drop=True)
    fp = CA / "stab_flat.npy"
    if not fp.exists():
        meta = grid["meta"]; ny, nx = meta["ny"], meta["nx"]
        aoi = gpd.read_file(PROC / "aoi_utm44n.gpkg").to_crs(32644)
        ins = rasterize(((g, 1) for g in aoi.geometry), (ny, nx), dtype="uint8",
                        transform=from_origin(meta["minx"], meta["maxy"], CELL, CELL)).astype(bool)
        for y in YEARS:
            ins &= np.array(FX.open_grid(y)["valid"])
        f = np.nonzero(ins.ravel())[0]
        np.save(fp, np.sort(np.random.default_rng(1).choice(f, len(f) // 100, replace=False)))
    return v, np.load(fp)


def class_weight(s, y):
    cw = s.get("cw")
    if cw is None:
        return "balanced"
    if cw == "none":
        return None
    n = np.bincount(y, minlength=6)[1:].astype(float); have = n / n.sum()
    want = np.array([MAP_SHARE[c] for c in CL]); want = np.sqrt(want) if cw == "sqrt" else want
    w = (want / want.sum()) / have
    return {c: float(w[c - 1]) for c in CL}


def fit_all(rows, years, v, stab):
    done = 0
    for y in years:
        need = [(k, s) for k, s in rows[y]]
        flats = np.unique(np.concatenate([rows[y][k].flat.values for k in need] + [v.flat.values, stab]))
        if y == 2023:
            er = ethan_rows(FX.open_grid(2023))
            flats = np.union1d(flats, er.flat.values)
        names, F, X = features(y, flats)
        at = lambda fl: X[np.searchsorted(F, fl)]
        Xh, Xs = at(v.flat.values), at(stab)
        for name, s in VARIANTS.items():
            for seed in SEEDS:
                fp = PR / f"{name}_{seed}_{y}.npz"
                if fp.exists() or (name != "base" and same_as_base(name, y)):
                    continue
                d = rows[y][(label_key(name, y), seed)]
                flat, lab = d.flat.values, d.label.values
                wt = None
                if s.get("ethan") and y == 2023:
                    keep = ~np.isin(flat, er.flat.values)
                    flat = np.r_[flat[keep], er.flat.values]; lab = np.r_[lab[keep], er.label.values]
                    wt = np.r_[np.ones(keep.sum()), np.full(len(er), float(s["ethan"]))]
                p = {**LGB, "n_estimators": NB, "class_weight": class_weight(s, lab), "random_state": seed}
                t = time.time(); m = lgb.LGBMClassifier(**p).fit(at(flat), lab, sample_weight=wt)
                np.savez(fp, hand=m.predict_proba(Xh).astype(np.float32), stab=m.predict_proba(Xs).astype(np.float32))
                done += 1
                log(f"{name} seed {seed} {y}: {len(flat):,} rows, {time.time() - t:.0f}s")
    return done


def load(name, y):
    """Probabilities (seeds, cells, 5) on hand cells and the stability sample."""
    src = "base" if same_as_base(name, y) else name
    z = [np.load(PR / f"{src}_{s}_{y}.npz") for s in SEEDS]
    return np.stack([a["hand"] for a in z]), np.stack([a["stab"] for a in z])


def smooth(P):
    """P (years, ..., 5): class per year, trees vs open decided on the mean over years."""
    c = P.argmax(-1) + 1
    r = (P[..., 3] / np.maximum(P[..., 3] + P[..., 4], 1e-6)).mean(0)
    return np.where(np.isin(c, [4, 5]), np.where(r >= 0.5, 4, 5), c)


def built_pr(ref, pred, st, W):
    P = np.zeros((2, 2))
    a, b = np.isin(pred, [1, 2]).astype(int), np.isin(ref, [1, 2]).astype(int)
    for h, w in W.items():
        m = st == h
        if m.sum():
            P += w * np.bincount(a[m] * 2 + b[m], minlength=4).reshape(2, 2) / m.sum()
    return P[1, 1] / P[1].sum(), P[1, 1] / P[:, 1].sum(), P[1].sum()


def water_f1(pred, jrc):
    tp = (pred & jrc).sum()
    return 2 * tp / max(pred.sum() + jrc.sum(), 1)


def stable(c, J):
    """c (3, n) classes in 2017, 2020, 2023; J year -> JRC yearly water at the same cells."""
    a, b, d = c
    ch = np.mean([(a != b).mean(), (b != d).mean()])
    to = (np.isin(a, [4, 5]) & np.isin(b, [4, 5]) & (a != b)).sum() + (np.isin(b, [4, 5]) & np.isin(d, [4, 5]) & (b != d)).sum()
    nt = ~((a == 4) | (b == 4) | (d == 4))
    return {"changed_per_3yr": ch, "flip_flop": ((a == d) & (b != a)).mean(), "trees_open_share_of_changes": to / max((a != b).sum() + (b != d).sum(), 1),
            "changed_no_tree_cells": np.mean([(a[nt] != b[nt]).mean(), (b[nt] != d[nt]).mean()]),
            "built_to_open": np.mean([(np.isin(a, [1, 2]) & (b == 5)).mean(), (np.isin(b, [1, 2]) & (d == 5)).mean()]),
            "nonres_share_2023": (d == 2).mean(), "built_share_2023": np.isin(d, [1, 2]).mean(),
            "water_share_2017": (a == 3).mean(), "water_share_2020": (b == 3).mean(), "water_share_2023": (d == 3).mean(),
            "water_F1_jrc_2017": water_f1(a == 3, J[2017]), "water_F1_jrc_2020": water_f1(b == 3, J[2020])}


def report(v, years, stab):
    W = pd.read_csv(LUP / "validation_strata.csv", index_col=0)["weight"].to_dict()
    J = {y: np.load(W20 / "ext" / f"jrc_{y}.npz")["water"].ravel()[stab] >= 50 for y in (2017, 2020)}
    log("JRC yearly water share inside HMDA: " + ", ".join(f"{y} {a.mean():.4f}" for y, a in J.items()))
    ref, st = v.true_class.values, v.stratum.values
    idx = [np.nonzero(st == h)[0] for h in np.unique(st)]
    rng = np.random.default_rng(0)
    draws = [np.concatenate([rng.choice(ix, len(ix)) for ix in idx if len(ix)]) for _ in range(BOOT)]
    runs, ens, stabs = {}, {}, []
    for name in VARIANTS:
        Ph, Ps = zip(*[load(name, y) for y in YEARS])
        Ph, Ps = np.stack(Ph), np.stack(Ps)                  # years, seeds, cells, 5
        for lab, fn in ((name, lambda P: P.argmax(-1) + 1), (name + "+smooth", smooth)):
            runs[lab] = fn(Ph)[-1]                           # seeds, cells: 2023 class on the hand cells
            ens[lab] = fn(Ph.mean(1))[-1]
            per = [stable(fn(Ps)[:, i], J) for i in range(len(SEEDS))]
            stabs.append({"variant": lab, "kind": "single seed, mean", **pd.DataFrame(per).mean().to_dict()})
            stabs.append({"variant": lab, "kind": f"{len(SEEDS)}-seed mean probability", **stable(fn(Ps.mean(1)), J)})
    scores, paired = [], []
    for lab, c in runs.items():
        one = [E.weighted(ref, p, st, W) for p in c]
        mf = np.array([o[0] for o in one]); nf = np.array([o[1][1] for o in one])
        ee = E.weighted(ref, ens[lab], st, W); bp = [built_pr(ref, p, st, W) for p in c]
        scores.append({"variant": lab, "macro_F1": mf.mean(), "sd_seeds": mf.std(ddof=1) if len(mf) > 1 else 0, "min": mf.min(), "max": mf.max(),
                       "nonres_F1": nf.mean(), "nonres_sd": nf.std(ddof=1) if len(nf) > 1 else 0,
                       "nonres_UA": np.mean([o[2][1] for o in one]), "nonres_PA": np.mean([o[3][1] for o in one]),
                       "res_F1": np.mean([o[1][0] for o in one]), "trees_F1": np.mean([o[1][3] for o in one]), "open_F1": np.mean([o[1][4] for o in one]),
                       "built_UA": np.mean([b[0] for b in bp]), "built_PA": np.mean([b[1] for b in bp]), "built_share": np.mean([b[2] for b in bp]),
                       "ensemble_macro_F1": ee[0], "ensemble_nonres_F1": ee[1][1]})
    base = runs["base"]
    bb = np.array([[E.weighted(ref[ii], p[ii], st[ii], W) for p in base] for ii in draws], dtype=object)
    mb = np.array([[x[0] for x in r] for r in bb]); nb = np.array([[x[1][1] for x in r] for r in bb])
    for lab, c in runs.items():
        if lab == "base":
            continue
        rr = [[E.weighted(ref[ii], p[ii], st[ii], W) for p in c] for ii in draws]
        dm = (np.array([[x[0] for x in r] for r in rr]) - mb).mean(1)
        dn = (np.array([[x[1][1] for x in r] for r in rr]) - nb).mean(1)
        s = next(x for x in scores if x["variant"] == lab); s0 = scores[0]
        paired.append({"variant": lab, "diff_macro_F1": s["macro_F1"] - s0["macro_F1"], "lo": np.percentile(dm, 2.5), "hi": np.percentile(dm, 97.5),
                       "diff_nonres_F1": s["nonres_F1"] - s0["nonres_F1"], "nr_lo": np.percentile(dn, 2.5), "nr_hi": np.percentile(dn, 97.5)})
        log(f"paired {lab}")
    sc, pa, sb = pd.DataFrame(scores), pd.DataFrame(paired), pd.DataFrame(stabs)
    sc.to_csv(R / "scores.csv", index=False); pa.to_csv(R / "paired.csv", index=False); sb.to_csv(R / "stability.csv", index=False)
    pd.set_option("display.width", 250); pd.set_option("display.max_columns", 40)
    log("\n" + sc.round(3).to_string(index=False) + "\n\n" + pa.round(3).to_string(index=False) + "\n\n" + sb.round(4).to_string(index=False))


def main():
    grid = FX.open_grid(2023)
    assert all(FX.open_grid(y)["meta"]["nx"] == grid["meta"]["nx"] for y in YEARS)
    vx, vy = T.hand_xy()
    v, stab = eval_cells(grid)
    log(f"{len(v)} hand cells, {len(stab):,} stability cells, {len(VARIANTS)} variants, seeds {SEEDS}")
    rows = all_rows(YEARS, vx, vy)
    log(f"{fit_all(rows, YEARS, v, stab)} models fitted")
    report(v, YEARS, stab)
    (R / "done.txt").write_text(time.strftime("%Y-%m-%d %H:%M"))


if __name__ == "__main__":
    main()
