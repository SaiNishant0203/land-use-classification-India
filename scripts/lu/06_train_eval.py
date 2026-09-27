"""
Train our pixel classifier with spatial cross-validation and audit existing products on the
SAME held-out pixels.

Spatial CV: GroupKFold over 12 km blocks (3x3 tiles) so neighbouring pixels never sit in
both train and test.

Feature-set ablation (what each data source buys):
  S2      Sentinel-2 bands, indices, texture, neighbourhood spectral means
  S2+BLD  + Open Buildings 2.5D temporal morphology (cover, height, count, size) + night lights
  AEF     AlphaEarth embeddings (pixel + 150 m mean) only
  ALL     everything

CAVEAT written into every output: these are OSM-derived labels in OSM-mapped places, with a
class mix that is NOT natural prevalence. Water/forest/open labels partly come from DW,
WorldCover, JRC and GHS, so those products are advantaged on classes 3-5; the fair audit
comparison for the products is residential vs non-residential (labels purely from OSM).
The headline numbers must come from the hand-labelled validation set (07_eval_handlabels.py).

Outputs: outputs/lu/cv_ablation.csv, audit_products.csv, confusion_*.csv, oof_predictions.parquet
"""
import json
import numpy as np, pandas as pd, lightgbm as lgb
from sklearn.model_selection import GroupKFold
from sklearn.metrics import f1_score, confusion_matrix, precision_recall_fscore_support
from lu_common import LU, LUOUT, log

CLASSES = [1, 2, 3, 4, 5]
NAMES = {1: "residential", 2: "non-residential", 3: "water", 4: "forest/trees", 5: "other open"}
BUILT_UNKNOWN = 9

PRODUCT_MAPS = {
    # value -> our class (0 = no prediction: outside product extent / road / nodata; 9 = built, use unknown)
    "dw": {0: 3, 1: 4, 2: 5, 3: 5, 4: 5, 5: 5, 6: 9, 7: 5, 8: 5},
    "wc": {10: 4, 20: 5, 30: 5, 40: 5, 50: 9, 60: 5, 70: 5, 80: 3, 90: 5, 95: 5, 100: 5},
    "ghsc": {0: 5, 1: 5, 2: 5, 3: 4, 4: 3, 5: 0, **{v: 1 for v in range(11, 16)}, **{v: 2 for v in range(21, 26)}},
    "wri": {0: 5, 1: 2, 2: 1, 3: 1, 4: 1, 5: 1, 6: 0},
    "ind": {0: 5, 1: 2, 2: 9},
    "gulu": {1: 3, 2: 4, 3: 5, 4: 5, 5: 1, 6: 2, 7: 2, 8: 2, 9: 0},
    "ben": {1: 1, 2: 2, 3: 3, 4: 4, 5: 5},
    "senclip": {1: 1, 2: 2, 3: 3, 4: 4, 5: 5},
    "euluc": {1: 1, 2: 2, 3: 3, 4: 4, 5: 5},
}
PRODUCT_NAMES = {"dw": "Dynamic World 2023 (land cover)", "wc": "ESA WorldCover 2021 (land cover)",
                 "ghsc": "GHS-BUILT-C 2018", "wri": "WRI Intra-urban Land Use (2020)",
                 "ind": "Global Industrial Land 2023", "gulu": "GULU / PPUL-Net (2020)",
                 "ben": "BigEarthNet v2 ResNet-50 (Europe-trained)",
                 "senclip": "SenCLIP ViT-B/32 zero-shot (WACV 2025)", "euluc": "EULUC-Globe 2024 (parcel)"}


def feature_sets(cols):
    aef = [c for c in cols if c.startswith("A") and c[1:3].isdigit()]
    bld = [c for c in cols if c.startswith(("ob_", "cov_", "cnt_", "bldg_", "hmax_", "h_sd", "viirs"))]
    s2 = [c for c in cols if c not in aef and c not in bld]
    return {"S2": s2, "S2+BLD": s2 + bld, "AEF": aef, "ALL": s2 + bld + aef}


def metrics(y, p):
    out = {"n": len(y), "macro_f1": f1_score(y, p, labels=CLASSES, average="macro", zero_division=0)}
    pr, rc, f1, _ = precision_recall_fscore_support(y, p, labels=CLASSES, zero_division=0)
    for c, a, b, d in zip(CLASSES, pr, rc, f1):
        out[f"f1_{c}"], out[f"prec_{c}"], out[f"rec_{c}"] = d, a, b
    b = np.isin(y, [1, 2]) & np.isin(p, [1, 2])          # built pixels the model also calls built
    out["resnonres_n"] = int(b.sum())
    out["resnonres_macro_f1"] = f1_score(y[b], p[b], labels=[1, 2], average="macro", zero_division=0) if b.any() else np.nan
    out["nonres_f1_among_built"] = f1_score(y[b], p[b], labels=[2], average="macro", zero_division=0) if b.any() else np.nan
    yb, pb = np.isin(y, [1, 2]), np.isin(p, [1, 2, BUILT_UNKNOWN])
    out["built_f1"] = f1_score(yb, pb, zero_division=0)
    return out


TILE_PRODUCTS = ["ben", "senclip", "euluc"]      # per-tile rasters already in our 5 classes


def attach_tile_products(s):
    """Value of each per-tile model map at every sample pixel (0 where the tile was not run)."""
    import rasterio
    from lu_common import LURAW
    for p in TILE_PRODUCTS:
        s[f"p_{p}"] = 0
        for k, idx in s.groupby("tile").groups.items():
            fp = LURAW / p / f"{k}.tif"
            if fp.exists():
                with rasterio.open(fp) as r:
                    a = r.read(1)
                s.loc[idx, f"p_{p}"] = a[s.loc[idx, "row"].values, s.loc[idx, "col"].values]
    return s


def main():
    s = attach_tile_products(pd.read_parquet(LU / "samples.parquet"))
    tx = s.tile.str.extract(r"x(\d+)_y(\d+)").astype(int)
    s["block"] = (tx[0] // 12).astype(str) + "_" + (tx[1] // 12).astype(str)
    meta = {"label", "tile", "x", "y", "row", "col", "block"} | {c for c in s if c.startswith("p_")}
    fs = feature_sets([c for c in s.columns if c not in meta])
    y = s.label.values
    gkf = GroupKFold(n_splits=min(5, s.block.nunique()))
    folds = list(gkf.split(s, y, s.block))
    log(f"{len(s)} pixels, {s.tile.nunique()} tiles, {s.block.nunique()} blocks; "
        f"classes {s.label.value_counts().sort_index().to_dict()}")

    rows, oof_all = [], {}
    for name, cols in fs.items():
        oof = np.zeros(len(s), int)
        for tr, te in folds:
            m = lgb.LGBMClassifier(n_estimators=400, learning_rate=0.05, num_leaves=63,
                                   subsample=0.8, subsample_freq=1, colsample_bytree=0.6,
                                   class_weight="balanced", n_jobs=12, verbose=-1)
            m.fit(s.iloc[tr][cols], y[tr])
            oof[te] = m.predict(s.iloc[te][cols])
        oof_all[name] = oof
        r = {"model": f"ours [{name}]", "n_features": len(cols), **metrics(y, oof)}
        rows.append(r)
        log(f"  {name:7s} macro-F1 {r['macro_f1']:.3f}  res/nonres macro-F1 {r['resnonres_macro_f1']:.3f}")
        pd.DataFrame(confusion_matrix(y, oof, labels=CLASSES), index=CLASSES, columns=CLASSES) \
            .to_csv(LUOUT / f"confusion_ours_{name.replace('+', '_')}.csv")
    pd.DataFrame(rows).to_csv(LUOUT / "cv_ablation.csv", index=False)

    # audit existing products on the same pixels
    arow = [dict(rows[-1], product="ours [ALL]")]
    for p, mp in PRODUCT_MAPS.items():
        col = f"p_{p}"
        if col not in s:
            continue
        pred = s[col].map(mp).fillna(0).astype(int).values
        cov = pred != 0
        r = {"product": PRODUCT_NAMES[p], "coverage": cov.mean(), **metrics(y[cov], pred[cov])}
        ours = metrics(y[cov], oof_all["ALL"][cov])           # ours on exactly the same pixels
        r["ours_same_px_macro_f1"] = ours["macro_f1"]
        r["ours_same_px_resnonres_macro_f1"] = ours["resnonres_macro_f1"]
        arow.append(r)
        pd.DataFrame(confusion_matrix(y[cov], pred[cov], labels=CLASSES + [BUILT_UNKNOWN]),
                     index=CLASSES + [BUILT_UNKNOWN], columns=CLASSES + [BUILT_UNKNOWN]) \
            .to_csv(LUOUT / f"confusion_{p}.csv")
    au = pd.DataFrame(arow)
    au.to_csv(LUOUT / "audit_products.csv", index=False)
    keep = ["product", "coverage", "n", "macro_f1", "built_f1", "resnonres_macro_f1", "nonres_f1_among_built",
            "f1_1", "f1_2", "f1_3", "f1_4", "f1_5", "ours_same_px_macro_f1", "ours_same_px_resnonres_macro_f1"]
    log("\n" + au.reindex(columns=keep).round(3).to_string(index=False))
    o = s[["tile", "x", "y", "label", "block"]].copy()
    for k, v in oof_all.items():
        o[f"oof_{k}"] = v
    o.to_parquet(LU / "oof_predictions.parquet")


if __name__ == "__main__":
    main()
