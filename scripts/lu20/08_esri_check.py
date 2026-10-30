"""
External check against Esri / Impact Observatory 10 m land cover, the product Prof. Eluru sent
(Esri India Living Atlas item 196281a3ee5b4296ad594d34db56e543, "India: Sentinel-2 10m Land
Use/Land Cover 2021"). The annual series 2017-2025 is in Earth Engine as
projects/sat-io/open-datasets/landcover/ESRI_Global-LULC_10m_TS; the India layer itself is read
point by point from its MapServer and compared with the EE 2021 image.

Esri has no residential / non-residential split, so everything is compared as land cover:
  built = ours 1+2 = Esri 7 | water = ours 3 = Esri 1 | trees = ours 4 = Esri 2 | open = ours 5 = Esri rest
  (Esri 10 clouds and 0 no data are dropped)

1. Hand labels (2023 imagery, confidence <= 2; Stehman weights, stratified bootstrap): land-cover
   scores of our year_2023 20 m map, Esri 2023 and Esri 2021, and how much of each hand-labelled
   class Esri calls built.
2. Map agreement per year (2017/2020/2023) on a random sample of 20 m cells inside HMDA; Esri is
   taken as the mode of its four 10 m pixels in each of our cells.
3. Change 2017 -> 2023 on the same cells: how often each map changes land-cover class.

Output: outputs/lu20/esri_check/*.csv and ESRI_CHECK.md
"""
import json, sys, urllib.request
from concurrent.futures import ThreadPoolExecutor
import numpy as np, pandas as pd, geopandas as gpd, rasterio
from pyproj import Transformer
from common20 import ROOT, LUP, OUT, YEARS, SEED, log

sys.path.insert(0, str(ROOT / "scripts" / "lu"))
from lu_common import ee_init

DST = OUT / "esri_check"; DST.mkdir(exist_ok=True)
MAPS = OUT / "maps"
ESRI_IC = "projects/sat-io/open-datasets/landcover/ESRI_Global-LULC_10m_TS"
INDIA = "https://livingatlas.esri.in/server/rest/services/Imagery/IN_S2_LULC_2021/MapServer/identify"
N_CELLS = 20000
B = 1000
LC = ["built", "water", "trees", "open"]
OURS_LC = {1: 1, 2: 1, 3: 2, 4: 3, 5: 4}
ESRI_LC = {7: 1, 1: 2, 2: 3, 4: 4, 5: 4, 8: 4, 9: 4, 11: 4}
TO_UTM = Transformer.from_crs(4326, 32644, always_xy=True)
TO_LL = Transformer.from_crs(32644, 4326, always_xy=True)


def lc(a, table):
    return pd.Series(a).map(table).fillna(0).astype(int).values


def esri_image(ee, years, cell=None):
    """One band per year; cell=20 gives the mode of the 10 m pixels on our 20 m grid."""
    ic = ee.ImageCollection(ESRI_IC)
    bands = []
    for y in years:
        im = ic.filterDate(f"{y}-01-01", f"{y}-12-31").mosaic().rename(f"y{y}")
        if cell:
            with rasterio.open(MAPS / "landuse_2023_20m_year.tif") as s:
                x0, y1 = s.bounds.left, s.bounds.top
            im = (im.reproject("EPSG:32644", [10, 0, x0, 0, -10, y1])
                  .reduceResolution(ee.Reducer.mode(), maxPixels=16)
                  .reproject("EPSG:32644", [cell, 0, x0, 0, -cell, y1]))
        bands.append(im)
    return ee.Image.cat(bands)


def ee_sample(ee, img, lon, lat, scale, chunk=2000):
    """Image values at points (0 where masked)."""
    names = img.bandNames().getInfo()
    out = np.zeros((len(lon), len(names)), int)
    for s in range(0, len(lon), chunk):
        fc = ee.FeatureCollection([ee.Feature(ee.Geometry.Point([float(a), float(b)]), {"i": s + k})
                                   for k, (a, b) in enumerate(zip(lon[s:s + chunk], lat[s:s + chunk]))])
        got = img.sampleRegions(fc, scale=scale, geometries=False).getInfo()["features"]
        for f in got:
            p = f["properties"]
            out[p["i"]] = [p.get(n, 0) or 0 for n in names]
        log(f"  EE sample {min(s + chunk, len(lon))}/{len(lon)}")
    return pd.DataFrame(out, columns=names)


def india_layer(lon, lat):
    """Pixel value of the Esri India 2021 layer at each point (0 where none)."""
    def one(p):
        q = (f"{INDIA}?geometry={p[0]},{p[1]}&geometryType=esriGeometryPoint&sr=4326&layers=all&tolerance=0"
             f"&mapExtent={p[0] - .01},{p[1] - .01},{p[0] + .01},{p[1] + .01}&imageDisplay=400,400,96"
             f"&returnGeometry=false&f=json")
        for _ in range(3):
            try:
                r = json.loads(urllib.request.urlopen(q, timeout=30).read())["results"]
                return int(r[0]["attributes"]["Raster.Value"]) if r else 0
            except Exception:
                pass
        return -1
    with ThreadPoolExecutor(8) as ex:
        return np.array(list(ex.map(one, zip(lon, lat))))


def weighted(ref, pred, strata, W, k=4):
    """Stehman/Olofsson cell proportions -> macro-F1, F1, UA, PA, P (rows map, cols reference)."""
    P = np.zeros((k, k))
    for h, w in W.items():
        m = strata == h
        if m.sum():
            P += w * np.bincount((pred[m] - 1) * k + (ref[m] - 1), minlength=k * k).reshape(k, k) / m.sum()
    ua = np.divide(np.diag(P), P.sum(1), out=np.zeros(k), where=P.sum(1) > 0)
    pa = np.divide(np.diag(P), P.sum(0), out=np.zeros(k), where=P.sum(0) > 0)
    f1 = np.divide(2 * ua * pa, ua + pa, out=np.zeros(k), where=(ua + pa) > 0)
    return f1.mean(), f1, ua, pa, P


def boot(ref, preds, strata, W, seed=0):
    rng = np.random.default_rng(seed)
    idx = [np.nonzero(strata == h)[0] for h in np.unique(strata)]
    out = {k: [] for k in preds}
    for _ in range(B):
        ii = np.concatenate([rng.choice(ix, len(ix)) for ix in idx if len(ix)])
        for k, p in preds.items():
            out[k].append(weighted(ref[ii], p[ii], strata[ii], W)[0])
    return {k: np.array(v) for k, v in out.items()}


def md(df, nd=3):
    df = df.copy()
    for c in df.columns:
        if df[c].dtype.kind == "f":
            df[c] = df[c].map(lambda v: "" if pd.isna(v) else f"{v:.{nd}f}")
    return "| " + " | ".join(map(str, df.columns)) + " |\n|" + "---|" * len(df.columns) + "\n" + \
        "\n".join("| " + " | ".join(map(str, r)) + " |" for r in df.values)


def at_map(year, x, y):
    with rasterio.open(MAPS / f"landuse_{year}_20m_year.tif") as s:
        return np.array([a[0] for a in s.sample(zip(x, y))]).astype(int)


def hand_label_check(ee, rep):
    v = gpd.read_file(LUP / "validation_points.gpkg", layer="validation_pixels")
    v = v.merge(pd.read_csv(LUP / "validation_key.csv")[["pid", "stratum", "lon", "lat"]], on="pid", suffixes=("_g", ""))
    v = v[v.true_class.notna() & (v.confidence.fillna(3) <= 2)].reset_index(drop=True)
    v["true_class"] = v.true_class.astype(int)
    x, y = TO_UTM.transform(v.lon.values, v.lat.values)
    v["ours_2023"] = at_map(2023, x, y)
    e = ee_sample(ee, esri_image(ee, [2021, 2023]), v.lon.values, v.lat.values, scale=10)
    v["esri_2021"], v["esri_2023"] = e.y2021.values, e.y2023.values
    log("India layer (MapServer) at hand-label points")
    v["esri_india_2021"] = india_layer(v.lon.values, v.lat.values)
    v.drop(columns="geometry").to_csv(DST / "handlabel_points.csv", index=False)

    ok = v.esri_india_2021 >= 0
    same = (v.esri_india_2021[ok] == v.esri_2021[ok]).mean()
    rep += ["## 0. The sir's India layer vs the Earth Engine copy\n",
            f"At the {ok.sum()} hand-label points the India 2021 layer (MapServer) and the EE 2021 image give the "
            f"same Esri class at **{same:.1%}** of points"
            + ("" if ok.all() else f" ({(~ok).sum()} points failed to download)") + ". "
            "The EE series is therefore used for every year below.\n"]

    W = pd.read_csv(LUP / "validation_strata.csv", index_col=0)["weight"].to_dict()
    ref = lc(v.true_class.values, OURS_LC)
    preds = {"ours year_2023 (20 m)": lc(v.ours_2023.values, OURS_LC),
             "Esri 2023": lc(v.esri_2023.values, ESRI_LC),
             "Esri 2021 (EE)": lc(v.esri_2021.values, ESRI_LC),
             "Esri India 2021 (sir's layer)": lc(v.esri_india_2021.values, ESRI_LC)}
    keep = (ref > 0) & np.all([p > 0 for p in preds.values()], axis=0)
    ref, st = ref[keep], v.stratum.values[keep]
    preds = {k: p[keep] for k, p in preds.items()}
    d = boot(ref, preds, st, W)
    rows = []
    for k, p in preds.items():
        mf, f1, ua, pa, P = weighted(ref, p, st, W)
        lo, hi = np.percentile(d[k], [2.5, 97.5])
        rows.append({"map": k, "n": len(ref), "macro_F1": mf, "lo": lo, "hi": hi, "overall_acc": np.trace(P),
                     **{f"F1_{c}": f1[i] for i, c in enumerate(LC)},
                     **{f"UA_{c}": ua[i] for i, c in enumerate(LC)}, **{f"PA_{c}": pa[i] for i, c in enumerate(LC)}})
        pd.DataFrame(P, index=[f"map_{c}" for c in LC], columns=[f"ref_{c}" for c in LC]).to_csv(
            DST / f"handlabel_confusion_{k.split(' (')[0].replace(' ', '_').lower()}.csv")
    hs = pd.DataFrame(rows); hs.to_csv(DST / "handlabel_landcover_scores.csv", index=False)
    diff = d["ours year_2023 (20 m)"] - d["Esri 2023"]
    dpt = weighted(ref, preds["ours year_2023 (20 m)"], st, W)[0] - weighted(ref, preds["Esri 2023"], st, W)[0]
    rep += ["## 1. Hand labels, land-cover level (4 classes)\n",
            f"Confidence <= 2 hand labels ({len(ref)} points, 2023 imagery), residential and non-residential merged "
            "into built. Stratum-weighted (Stehman 2014), 95% stratified bootstrap.\n",
            md(hs[["map", "n", "macro_F1", "lo", "hi", "overall_acc"] + [f"F1_{c}" for c in LC]]) + "\n",
            f"Ours minus Esri 2023, macro-F1: **{dpt:+.3f}** [{np.percentile(diff, 2.5):+.3f}, "
            f"{np.percentile(diff, 97.5):+.3f}] (paired bootstrap).\n",
            "User's (UA) and producer's (PA) accuracy:\n",
            md(hs[["map"] + [f"UA_{c}" for c in LC] + [f"PA_{c}" for c in LC]]) + "\n"]

    # how much of each hand-labelled use class each map calls built
    tc = v.true_class.values
    rows = []
    for name, col, table in [("ours year_2023", "ours_2023", OURS_LC), ("Esri 2023", "esri_2023", ESRI_LC),
                             ("Esri 2021", "esri_2021", ESRI_LC)]:
        b = lc(v[col].values, table) == 1
        r = {"map": name}
        for c, cname in zip([1, 2, 3, 4, 5], ["residential", "non-res", "water", "trees", "open"]):
            num = sum(w * ((st_ := v.stratum.values == h) & (tc == c) & b).sum() / max(st_.sum(), 1) for h, w in W.items())
            den = sum(w * ((st_ := v.stratum.values == h) & (tc == c)).sum() / max(st_.sum(), 1) for h, w in W.items())
            r[cname] = num / den if den else np.nan
            r[f"n_{cname}"] = int((tc == c).sum())
        rows.append(r)
    bt = pd.DataFrame(rows); bt.to_csv(DST / "handlabel_called_built.csv", index=False)
    rep += ["### Share of each hand-labelled class that the map calls built\n",
            md(bt[["map", "residential", "non-res", "water", "trees", "open"]]) + "\n",
            f"Hand-labelled points per class: " + ", ".join(f"{c} {bt[f'n_{c}'][0]}" for c in
                                                            ["residential", "non-res", "water", "trees", "open"]) + ".\n"]


def map_check(ee, rep):
    with rasterio.open(MAPS / "landuse_2023_20m_year.tif") as s:
        T = s.transform
        m = {y: rasterio.open(MAPS / f"landuse_{y}_20m_year.tif").read(1) for y in YEARS}
    ok = np.all([m[y] > 0 for y in YEARS], axis=0)
    r, c = np.nonzero(ok)
    pick = np.random.default_rng(SEED).choice(len(r), N_CELLS, replace=False)
    r, c = r[pick], c[pick]
    x, y = T.c + (c + 0.5) * T.a, T.f + (r + 0.5) * T.e
    lon, lat = TO_LL.transform(x, y)
    log(f"Esri at {N_CELLS} random 20 m cells")
    e = ee_sample(ee, esri_image(ee, YEARS, cell=20), lon, lat, scale=20)
    df = pd.DataFrame({"row": r, "col": c, "lon": lon, "lat": lat})
    for yy in YEARS:
        df[f"ours_{yy}"] = m[yy][r, c]
        df[f"esri_{yy}"] = e[f"y{yy}"].values
    df.to_csv(DST / "map_sample_cells.csv", index=False)

    rows, confs = [], []
    for yy in YEARS:
        o5 = df[f"ours_{yy}"].values
        o, es = lc(o5, OURS_LC), lc(df[f"esri_{yy}"].values, ESRI_LC)
        k = (o > 0) & (es > 0)
        o, es, o5 = o[k], es[k], o5[k]
        row = {"year": yy, "cells": int(k.sum()), "agreement": (o == es).mean()}
        for i, cn in enumerate(LC, 1):
            row[f"ours_{cn}"], row[f"esri_{cn}"] = (o == i).mean(), (es == i).mean()
        bo, be = o == 1, es == 1
        row["built_IoU"] = (bo & be).sum() / (bo | be).sum()
        rows.append(row)
        ct = pd.crosstab(pd.Series(o5, name="ours").map({1: "residential", 2: "non-res", 3: "water", 4: "trees", 5: "open"}),
                         pd.Series(es, name="esri").map(dict(enumerate(LC, 1))), normalize="index")
        ct.insert(0, "year", yy); confs.append(ct)
    ag = pd.DataFrame(rows); ag.to_csv(DST / "map_agreement.csv", index=False)
    cf = pd.concat(confs); cf.to_csv(DST / "map_ours_class_vs_esri.csv")
    rep += ["## 2. Map agreement, random 20 m cells in HMDA\n",
            f"{N_CELLS:,} cells drawn at random (seed {SEED}) from cells mapped in all three years; Esri is the "
            "mode of its 10 m pixels in each 20 m cell. Shares are of sampled cells.\n",
            md(ag[["year", "cells", "agreement", "built_IoU"] + [f"ours_{c}" for c in LC] + [f"esri_{c}" for c in LC]]) + "\n",
            "### What Esri calls each of our classes (row shares)\n",
            md(cf.reset_index().rename(columns={"ours": "our class"})) + "\n"]

    # change 2017 -> 2020 -> 2023
    rows = []
    for name, cols, table in [("ours (land cover)", "ours", OURS_LC), ("Esri", "esri", ESRI_LC)]:
        a, b, z = (lc(df[f"{cols}_{yy}"].values, table) for yy in YEARS)
        k = (a > 0) & (b > 0) & (z > 0)
        a, b, z = a[k], b[k], z[k]
        rows.append({"map": name, "cells": int(k.sum()), "changed_17_23": (a != z).mean(),
                     "flip_flop": ((a == z) & (b != a)).mean(),
                     "built_gain_17_23": ((a != 1) & (z == 1)).mean(), "built_loss_17_23": ((a == 1) & (z != 1)).mean()})
    a5, b5, z5 = (df[f"ours_{yy}"].values for yy in YEARS)
    rows.append({"map": "ours (5 use classes)", "cells": len(df), "changed_17_23": (a5 != z5).mean(),
                 "flip_flop": ((a5 == z5) & (b5 != a5)).mean(), "built_gain_17_23": np.nan, "built_loss_17_23": np.nan})
    ch = pd.DataFrame(rows); ch.to_csv(DST / "change_rates.csv", index=False)

    oa, oz = lc(df.ours_2017.values, OURS_LC), lc(df.ours_2023.values, OURS_LC)
    ea, ez = lc(df.esri_2017.values, ESRI_LC), lc(df.esri_2023.values, ESRI_LC)
    k = (oa > 0) & (oz > 0) & (ea > 0) & (ez > 0)
    og, eg = (oa[k] != 1) & (oz[k] == 1), (ea[k] != 1) & (ez[k] == 1)
    # which class pairs the change comes from
    pairs = []
    for name, (p, q) in {"ours": (oa, oz), "Esri": (ea, ez)}.items():
        s = pd.Series([f"{LC[i - 1]} -> {LC[j - 1]}" for i, j in zip(p[k], q[k]) if i != j]).value_counts() / k.sum()
        pairs.append(s.rename(name))
    pr = pd.concat(pairs, axis=1).fillna(0).sort_values("ours", ascending=False).head(8)
    pr.to_csv(DST / "change_pairs.csv")
    nt = (oa[k] != 3) & (oz[k] != 3)
    rep += ["## 3. Change 2017 -> 2023 on the same cells\n",
            "`flip_flop` = same class in 2017 and 2023 but different in 2020.\n",
            md(ch) + "\n",
            f"Built gain 2017 -> 2023: Esri flags {eg.sum()} sampled cells, ours {og.sum()}; both flag {(og & eg).sum()} "
            f"({(og & eg).sum() / max(eg.sum(), 1):.1%} of Esri's, {(og & eg).sum() / max(og.sum(), 1):.1%} of ours).\n",
            "### Largest class-pair changes (share of sampled cells)\n",
            md(pr.reset_index().rename(columns={"index": "change"})) + "\n",
            f"Leaving out cells we map as trees in 2017 or 2023, our change rate is "
            f"**{((oa[k] != oz[k]) & nt).mean():.1%}** against Esri's {((ea[k] != ez[k]) & nt).mean():.1%} on the same cells.\n"]


ESRI_NAMES = {1: "water", 2: "trees", 4: "flooded veg.", 5: "crops", 7: "built area", 8: "bare", 9: "snow",
              10: "clouds", 11: "rangeland"}
OURS_NAMES = {1: "residential", 2: "non-res", 3: "water", 4: "trees", 5: "open"}


def head_on(rep):
    """Class-by-class side-by-side table for 2023, from the CSVs the other sections wrote."""
    hs = pd.read_csv(DST / "handlabel_landcover_scores.csv").set_index("map")
    ag = pd.read_csv(DST / "map_agreement.csv").set_index("year").loc[2023]
    df = pd.read_csv(DST / "map_sample_cells.csv")
    o, e = lc(df.ours_2023.values, OURS_LC), lc(df.esri_2023.values, ESRI_LC)
    k = (o > 0) & (e > 0)
    o, e = o[k], e[k]
    rows = []
    for i, c in enumerate(LC, 1):
        a, b = o == i, e == i
        rows.append({"class": c, "HMDA share, ours": a.mean(), "HMDA share, Esri": b.mean(),
                     "cells agree (IoU)": (a & b).sum() / max((a | b).sum(), 1),
                     "hand-label F1, ours": hs.loc["ours year_2023 (20 m)", f"F1_{c}"],
                     "hand-label F1, Esri": hs.loc["Esri 2023", f"F1_{c}"],
                     "UA ours / Esri": f"{hs.loc['ours year_2023 (20 m)', f'UA_{c}']:.2f} / {hs.loc['Esri 2023', f'UA_{c}']:.2f}",
                     "PA ours / Esri": f"{hs.loc['ours year_2023 (20 m)', f'PA_{c}']:.2f} / {hs.loc['Esri 2023', f'PA_{c}']:.2f}"})
    rows.append({"class": "all (macro-F1 / agreement)", "cells agree (IoU)": ag["agreement"],
                 "hand-label F1, ours": hs.loc["ours year_2023 (20 m)", "macro_F1"],
                 "hand-label F1, Esri": hs.loc["Esri 2023", "macro_F1"], "UA ours / Esri": "", "PA ours / Esri": ""})
    t = pd.DataFrame(rows); t.to_csv(DST / "head_on_2023.csv", index=False)

    # our 5 classes against Esri's own classes, row shares
    ct = pd.crosstab(df.ours_2023.map(OURS_NAMES), df.esri_2023.map(ESRI_NAMES), normalize="index")
    ct = ct.reindex(index=list(OURS_NAMES.values()),
                    columns=[c for c in ESRI_NAMES.values() if c in ct.columns]).fillna(0)
    ct.to_csv(DST / "head_on_2023_native.csv")
    rep += ["## 4. Head-on, class by class (2023)\n",
            "HMDA shares and IoU from the random 20 m cells (section 2); F1, user's (UA) and producer's (PA) "
            "accuracy from the hand labels (section 1). IoU = cells both maps put in the class / cells either "
            "map puts in it.\n",
            md(t) + "\n",
            "### Our classes against Esri's own classes (2023, row shares)\n",
            md(ct.reset_index().rename(columns={"ours_2023": "our class"}), nd=2) + "\n"]


def main():
    ee = ee_init()
    rep = ["# Check against Esri / Impact Observatory 10 m land cover\n",
           "Auto-generated by `scripts/lu20/08_esri_check.py`. Esri's product is land cover only (no residential / "
           "non-residential split), so it can check built vs water vs trees vs open and built change, never our "
           "use split. Esri and our model both use Sentinel-2, so they are not fully independent.\n",
           "Class match: built = ours 1+2 = Esri 7 (Built area); water = ours 3 = Esri 1; trees = ours 4 = Esri 2; "
           "open = ours 5 = Esri 4, 5, 8, 9, 11 (flooded veg., crops, bare, snow, rangeland). Esri 10 (clouds) dropped.\n"]
    hand_label_check(ee, rep)
    map_check(ee, rep)
    head_on(rep)
    (DST / "ESRI_CHECK.md").write_text("\n".join(rep), encoding="utf8")
    log(f"wrote {DST / 'ESRI_CHECK.md'}")


if __name__ == "__main__":
    main()
