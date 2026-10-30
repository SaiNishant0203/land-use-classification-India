"""
Training cells, models and spatial cross-validation at 20 m.

Sampling (as experiments/res100): a cell is a candidate if it is valid and >= 50% of its 10 m
pixels carry a label; its label is the majority class; cells within 400 m of a hand-label point are
dropped; at most 100 cells per class per 4 km tile (rng seed 7).

Models, all with the same LightGBM settings and the same 12 km-block folds, so comparisons are paired:
  year_<y>      trained on year y's cells (labels from OSM as of 31 Dec y)
  pooled        all years' cells together: one model for every year, so year-to-year differences in
                the maps come from the inputs, not from three different models
  osm2026_2023  2023 cells labelled from the old, undated OSM (downloaded Sept 2026): the control
Each model: 5-fold GroupKFold over 12 km blocks (out-of-fold predictions) + a full fit.

Usage: python 04_train.py
Output: outputs/lu20/samples_<set>.parquet, oof_<model>.parquet, models/<model>.pkl,
        cv_scores.csv, cv_paired.csv
"""
import time, pickle
import numpy as np, pandas as pd, lightgbm as lgb
from pyproj import Transformer
from sklearn.model_selection import GroupKFold
from common20 import *
import features20 as FX

B = 1000


def block_id(x, y):
    """12 km block (3 x 3 tiles), same grouping as the 10 m CV."""
    return ((np.floor(np.asarray(x) / 4000).astype(int) * 4) // 12) * 1000 + (np.floor(np.asarray(y) / 4000).astype(int) * 4) // 12


def hand_xy():
    v = pd.read_csv(LUP / "validation_key.csv")
    return Transformer.from_crs(4326, 32644, always_xy=True).transform(v.lon.values, v.lat.values)


def sample(grid, labname, vx, vy):
    meta = grid["meta"]; ny, nx = meta["ny"], meta["nx"]
    valid = np.array(grid["valid"]); labc = grid[labname]
    nlab = np.zeros((ny, nx), np.int16)
    for c in CL:
        nlab += np.array(labc[c]).astype(np.int16)
    cand = valid & (nlab / (K * K) >= MIN_LFRAC)
    rad = int(np.ceil(EXCL_M / CELL))
    for r0, c0 in zip((meta["maxy"] - vy) // CELL, (vx - meta["minx"]) // CELL):
        r0, c0 = int(r0), int(c0)
        if not (-rad <= r0 < ny + rad and -rad <= c0 < nx + rad):
            continue
        rs, cs = slice(max(0, r0 - rad), max(0, r0 + rad + 1)), slice(max(0, c0 - rad), max(0, c0 + rad + 1))
        yy, xx = np.mgrid[rs, cs]
        cand[rs, cs] &= ~(np.hypot((yy - r0) * CELL, (xx - c0) * CELL) < EXCL_M)
    rr, cc = np.nonzero(cand)
    cnt = np.stack([np.array(labc[c])[rr, cc] for c in CL])
    pool = pd.DataFrame({"flat": rr * nx + cc, "label": cnt.argmax(0) + 1, "tile": (rr // NT) * 10000 + cc // NT})
    pool["r"] = np.random.default_rng(SEED).random(len(pool))
    rows = pool.sort_values("r").groupby(["tile", "label"]).head(CAP).sort_values("flat").reset_index(drop=True)
    r, c = rows.flat.values // nx, rows.flat.values % nx
    rows["x"] = meta["minx"] + (c + 0.5) * CELL
    rows["y"] = meta["maxy"] - (r + 0.5) * CELL
    rows["gid"] = block_id(rows.x, rows.y)
    log(f"  {labname}: {len(pool):,} candidate cells -> {len(rows):,} rows {rows.label.value_counts().sort_index().to_dict()}")
    return rows.drop(columns=["r", "tile"])


def macro_f1(C):
    tp = np.diag(C).astype(float); fp = C.sum(0) - tp; fn = C.sum(1) - tp
    f = np.where(2 * tp + fp + fn > 0, 2 * tp / np.maximum(2 * tp + fp + fn, 1), 0.0)
    return f.mean(), f


def group_conf(g, ref, pred, G):
    return np.bincount(g * 25 + (ref - 1) * 5 + (pred - 1), minlength=G * 25).reshape(G, 5, 5)


def boot(Cs, seed=0):
    rng = np.random.default_rng(seed); G = next(iter(Cs.values())).shape[0]
    out = {k: [] for k in Cs}
    for _ in range(B):
        ii = rng.integers(0, G, G)
        for k, C in Cs.items():
            out[k].append(macro_f1(C[ii].sum(0))[0])
    return {k: np.array(v) for k, v in out.items()}


def main():
    years = years_done("grid")
    assert years, "no grid built; run 03_build_grid.py"
    vx, vy = hand_xy()
    S = {}
    for y in years:
        p = OUT / f"samples_{y}.parquet"
        if not p.exists():
            grid = FX.open_grid(y)
            sets = {str(y): "labc"} if y != 2023 else {"2023": "labc", "2023_osm2026": "labc_osm2026"}
            for sname, lab in sets.items():
                rows = sample(grid, lab, vx, vy)
                t = time.time(); names, X = FX.extract(grid, rows.flat.values)
                log(f"  features for {len(rows):,} cells: {time.time() - t:.0f}s")
                d = pd.concat([rows, pd.DataFrame(X, columns=names)], axis=1); d["year"] = y
                d.to_parquet(OUT / f"samples_{sname}.parquet", index=False)
        S[str(y)] = pd.read_parquet(p)
        if y == 2023:
            S["2023_osm2026"] = pd.read_parquet(OUT / "samples_2023_osm2026.parquet")
    feats = [c for c in S[str(years[0])].columns if c not in ("flat", "label", "x", "y", "gid", "year")]

    allg = np.unique(np.concatenate([s.gid.values for s in S.values()]))   # one fold per block, shared by all models
    NF = min(5, len(allg))                                                  # 74 blocks in HMDA; fewer in test mode
    fold_of = {g: f for f, (_, te) in enumerate(GroupKFold(n_splits=NF).split(allg, groups=allg)) for g in allg[te]}
    gidx = {g: i for i, g in enumerate(allg)}

    models = {f"year_{y}": S[str(y)] for y in years}
    if len(years) > 1:
        models["pooled"] = pd.concat([S[str(y)] for y in years], ignore_index=True)
    if "2023_osm2026" in S:
        models["osm2026_2023"] = S["2023_osm2026"]
    (OUT / "models").mkdir(exist_ok=True)
    rows, oofs = [], {}
    for name, d in models.items():
        fold = d.gid.map(fold_of).values
        oof = np.zeros(len(d), int)
        for f in range(NF):
            tr, te = fold != f, fold == f
            if te.sum() == 0:
                continue
            t = time.time(); m = lgb.LGBMClassifier(**LGB).fit(d.loc[tr, feats], d.label.values[tr])
            oof[te] = m.predict(d.loc[te, feats])
            log(f"{name} fold {f}: fit {time.time() - t:.0f}s on {tr.sum():,} rows")
        t = time.time(); m = lgb.LGBMClassifier(**LGB).fit(d[feats], d.label.values)
        log(f"{name} full fit {time.time() - t:.0f}s on {len(d):,} rows")
        pickle.dump((m, feats), open(OUT / "models" / f"{name}.pkl", "wb"))
        o = d[["flat", "year", "gid", "label"]].copy(); o["oof"] = oof
        o.to_parquet(OUT / f"oof_{name}.parquet", index=False); oofs[name] = o

    # OSM-label CV scores, per model and year (block bootstrap); pooled vs year model on the same rows
    G = len(allg); paired = []
    for name, o in oofs.items():
        for y in sorted(o.year.unique()):
            s = o[o.year == y]
            C = group_conf(s.gid.map(gidx).values, s.label.values, s.oof.values, G)
            mf, f1 = macro_f1(C.sum(0)); d = boot({"x": C})["x"]
            rows.append({"model": name, "year": y, "labels": "OSM 2026 (undated)" if name == "osm2026_2023" else f"OSM {y}",
                         "n": len(s), "macro_F1": mf, "lo": np.percentile(d, 2.5), "hi": np.percentile(d, 97.5),
                         **{f"F1_{c}": f1[c - 1] for c in CL}})
    if "pooled" in oofs:
        for y in years:
            a = oofs["pooled"][oofs["pooled"].year == y]; b = oofs[f"year_{y}"]
            assert (a.flat.values == b.flat.values).all()
            g = a.gid.map(gidx).values
            Cs = {"pooled": group_conf(g, a.label.values, a.oof.values, G), "year": group_conf(g, b.label.values, b.oof.values, G)}
            d = boot(Cs)
            paired.append({"year": y, "comparison": f"pooled minus year_{y} (same rows, OSM {y} labels)",
                           "diff_macro_F1": macro_f1(Cs["pooled"].sum(0))[0] - macro_f1(Cs["year"].sum(0))[0],
                           "lo": np.percentile(d["pooled"] - d["year"], 2.5), "hi": np.percentile(d["pooled"] - d["year"], 97.5)})
    pd.DataFrame(rows).to_csv(OUT / "cv_scores.csv", index=False)
    pd.DataFrame(paired).to_csv(OUT / "cv_paired.csv", index=False)
    pd.set_option("display.width", 220)
    log("\n" + pd.DataFrame(rows).round(3).to_string(index=False))
    if paired:
        log("\n" + pd.DataFrame(paired).round(3).to_string(index=False))
    (W20 / "train.done").write_text(str(years))


if __name__ == "__main__":
    main()
