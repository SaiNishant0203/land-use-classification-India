"""
Headline evaluation: every model/product against the HAND-LABELLED validation pixels, with
stratum weights so accuracy reflects natural prevalence over HMDA (Olofsson et al. 2014).

Estimators (stratified random sampling): cell proportions
  p_ij = sum_h W_h * n_hij / n_h
where W_h = stratum area share, n_h = labelled pixels in stratum h, n_hij = pixels in stratum
h with map class i and reference class j. User's / producer's accuracy, F1 and overall
accuracy follow from p_ij. 95% intervals for macro-F1 by bootstrap resampling within strata.

Only pixels with confidence 1 or 2 are used in the headline; confidence-3 guesses are
reported separately. Road pixels (is_road = 1) are reported with and without.

Output: outputs/lu/handlabel_eval.csv, handlabel_confusion_<model>.csv
"""
import numpy as np, pandas as pd, geopandas as gpd, rasterio
from pyproj import Transformer
from lu_common import LU, LURAW, LUOUT, UTM, log
import importlib.util as iu

_s = iu.spec_from_file_location("te", LU.parents[2] / "scripts/lu/06_train_eval.py")
te = iu.module_from_spec(_s); _s.loader.exec_module(te)
CLASSES = [1, 2, 3, 4, 5]


def read_at(folder, band, x, y):
    """Value of tile raster band at UTM points (0 where missing)."""
    import json
    T = json.loads((LURAW / "feat_2023" / "tiles.json").read_text())
    out = np.zeros(len(x), int)
    for i, (a, b) in enumerate(zip(x, y)):
        k = f"x{int(a // 4000 * 4)}_y{int(b // 4000 * 4)}"
        fp = LURAW / folder / f"{k}.tif"
        if k in T and fp.exists():
            with rasterio.open(fp) as s:
                out[i] = next(s.sample([(a, b)], indexes=band))[0]
    return out


def weighted(ref, mp, strata, W):
    """Olofsson estimator -> dict of metrics. mp may contain 0 (no prediction) and 9 (built, use unknown)."""
    labels = sorted(set(CLASSES) | set(np.unique(mp)))
    P = pd.DataFrame(0.0, index=labels, columns=CLASSES)           # rows map, cols reference
    for h, w in W.items():
        m = strata == h
        if m.sum() == 0:
            continue
        ct = pd.crosstab(mp[m], ref[m]).reindex(index=labels, columns=CLASSES, fill_value=0)
        P += w * ct / m.sum()
    out = {"overall_acc": float(sum(P.loc[c, c] for c in CLASSES))}
    f1s = []
    for c in CLASSES:
        ua = P.loc[c, c] / P.loc[c].sum() if P.loc[c].sum() > 0 else np.nan
        pa = P.loc[c, c] / P[c].sum() if P[c].sum() > 0 else np.nan
        f1 = 2 * ua * pa / (ua + pa) if ua and pa and ua + pa > 0 else 0.0
        out[f"UA_{c}"], out[f"PA_{c}"], out[f"F1_{c}"] = ua, pa, f1
        f1s.append(f1)
    out["macro_F1"] = float(np.nanmean(f1s))
    out["ref_share_" + "_".join(map(str, CLASSES))] = "/".join(f"{P[c].sum():.3f}" for c in CLASSES)
    return out, P


def bootstrap(ref, mp, strata, W, B=500, seed=0):
    """95% interval of the weighted macro-F1, resampling pixels within each stratum."""
    rng = np.random.default_rng(seed)
    idx_by = {h: np.nonzero(strata == h)[0] for h in np.unique(strata)}
    vals = []
    for _ in range(B):
        ii = np.concatenate([rng.choice(ix, len(ix)) for ix in idx_by.values() if len(ix)])
        vals.append(weighted(ref[ii], mp[ii], strata[ii], W)[0]["macro_F1"])
    return tuple(np.percentile(vals, [2.5, 97.5]))


def main():
    import sys
    # optional path: score a copy while QGIS still holds the live file (edits sit in its -wal)
    src = sys.argv[1] if len(sys.argv) > 1 else LU / "validation_points.gpkg"
    v = gpd.read_file(src, layer="validation_pixels").to_crs(UTM)
    key = pd.read_csv(LU / "validation_key.csv")
    v = v.merge(key[["pid", "stratum", "stratum_weight"]], on="pid")
    v = v[v.true_class.notna()].copy()
    log(f"{len(v)} labelled pixels")
    if len(v) == 0:
        return
    W = pd.read_csv(LU / "validation_strata.csv", index_col=0)["weight"].to_dict()
    c = v.geometry.centroid; x, y = c.x.values, c.y.values
    preds = {"ours [ALL]": read_at("pred_2023", 1, x, y), "ours U-Net": read_at("unet_2023", 1, x, y)}
    for p in te.TILE_PRODUCTS:
        preds[te.PRODUCT_NAMES[p]] = read_at(p, 1, x, y)
    P = {n: read_at("prod", i + 1, x, y) for i, n in enumerate(["dw", "wc", "jrc", "ghsc", "wri", "ind"])}
    mx, my = Transformer.from_crs(UTM, 3857, always_xy=True).transform(x, y)
    with rasterio.open(LURAW / "gulu" / "IND.tif") as s:
        P["gulu"] = np.array([a[0] for a in s.sample(zip(mx, my))])
    for p, mp in te.PRODUCT_MAPS.items():
        if p in P and p not in te.TILE_PRODUCTS:
            preds[te.PRODUCT_NAMES[p]] = pd.Series(P[p]).map(mp).fillna(0).astype(int).values
    ref = v.true_class.astype(int).values; st = v.stratum.values
    subsets = {"conf<=2": v.confidence.fillna(3).values <= 2, "all": np.ones(len(v), bool),
               "conf<=2, no roads": (v.confidence.fillna(3).values <= 2) & (v.is_road.fillna(0).values != 1)}
    rows = []
    for sname, msk in subsets.items():
        for n, p in preds.items():
            cov = msk & (p != 0)
            r, M = weighted(ref[cov], p[cov], st[cov], W)
            r["macro_F1_lo"], r["macro_F1_hi"] = bootstrap(ref[cov], p[cov], st[cov], W)
            rows.append({"subset": sname, "model": n, "n": int(cov.sum()), "coverage": cov.sum() / msk.sum(), **r})
            if sname == "conf<=2":
                slug = "".join(ch if ch.isalnum() else "_" for ch in n.lower()).strip("_")
                M.to_csv(LUOUT / f"handlabel_confusion_{slug}.csv")
    out = pd.DataFrame(rows)
    out.to_csv(LUOUT / "handlabel_eval.csv", index=False)
    log("\n" + out[out.subset == "conf<=2"][["model", "n", "coverage", "overall_acc", "macro_F1", "macro_F1_lo", "macro_F1_hi",
                                              "F1_1", "F1_2", "F1_3", "F1_4", "F1_5"]].round(3).to_string(index=False))


if __name__ == "__main__":
    main()
