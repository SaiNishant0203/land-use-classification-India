"""
Wall-to-wall 10 m land-use map of HMDA with our model (ALL features), trained on every
sampled pixel. Writes one GeoTIFF per tile, then a single mosaic clipped to HMDA and a PNG.

Outputs:
  data/raw/lu/pred_2023/<tile>.tif        uint8 class (1..5), band 2 = confidence x100
  outputs/lu/landuse_hmda_2023_10m.tif    mosaic (0 = outside HMDA)
  outputs/lu/landuse_hmda_2023.png        overview map
"""
import json, pickle
import numpy as np, pandas as pd, lightgbm as lgb, rasterio, geopandas as gpd
from rasterio.transform import from_origin
from rasterio.merge import merge
from rasterio.features import geometry_mask
from lu_common import LU, LURAW, LUOUT, PROC, UTM, log
import lu_features as F

OUT = LURAW / "pred_2023"; OUT.mkdir(exist_ok=True)
COLORS = {1: "#e8a33d", 2: "#c0392b", 3: "#2e86c1", 4: "#1e8449", 5: "#e5e1c9"}
NAMES = {1: "Residential", 2: "Non-residential built", 3: "Water", 4: "Forest / trees", 5: "Other open"}


def train():
    s = pd.read_parquet(LU / "samples.parquet")
    meta = {"label", "tile", "x", "y", "row", "col"} | {c for c in s if c.startswith("p_")}
    cols = [c for c in s.columns if c not in meta]
    m = lgb.LGBMClassifier(n_estimators=400, learning_rate=0.05, num_leaves=63, subsample=0.8,
                           subsample_freq=1, colsample_bytree=0.6, class_weight="balanced",
                           n_jobs=14, verbose=-1)
    m.fit(s[cols], s.label.values)
    pickle.dump((m, cols), open(LU / "model_all_2023.pkl", "wb"))
    imp = pd.Series(m.booster_.feature_importance("gain"), index=cols).sort_values(ascending=False)
    (imp / imp.sum()).head(40).to_csv(LUOUT / "feature_importance.csv")
    log(f"trained on {len(s)} pixels, {len(cols)} features")
    return m, cols


def main():
    m, cols = train()
    T = F.tiles()
    todo = [k for k in T if (LURAW / "feat_2023" / f"{k}.tif").exists() and not (OUT / f"{k}.tif").exists()]
    log(f"predicting {len(todo)} tiles")
    for i, k in enumerate(todo, 1):
        names, arr = F.compute(k)
        X = pd.DataFrame(arr.reshape(len(names), -1).T, columns=names)[cols]
        pr = m.predict_proba(X)
        cls = m.classes_[pr.argmax(1)].reshape(400, 400).astype(np.uint8)
        conf = (pr.max(1) * 100).reshape(400, 400).astype(np.uint8)
        minx, miny, maxx, maxy = T[k]
        with rasterio.open(OUT / f"{k}.tif", "w", driver="GTiff", width=400, height=400, count=2, dtype="uint8",
                           crs=f"EPSG:{UTM}", transform=from_origin(minx, maxy, 10, 10), compress="deflate") as d:
            d.write(cls, 1); d.write(conf, 2)
        if i % 25 == 0:
            log(f"  {i}/{len(todo)}")
    mosaic()


def mosaic():
    srcs = [rasterio.open(p) for p in sorted(OUT.glob("*.tif"))]
    arr, tr = merge(srcs, indexes=[1])
    for s in srcs:
        s.close()
    aoi = gpd.read_file(PROC / "aoi_utm44n.gpkg").to_crs(UTM)
    outside = geometry_mask(aoi.geometry, out_shape=arr.shape[1:], transform=tr)
    arr[0][outside] = 0
    fp = LUOUT / "landuse_hmda_2023_10m.tif"
    with rasterio.open(fp, "w", driver="GTiff", width=arr.shape[2], height=arr.shape[1], count=1, dtype="uint8",
                       crs=f"EPSG:{UTM}", transform=tr, compress="deflate", nodata=0) as d:
        d.write(arr[0], 1)
        d.write_colormap(1, {0: (255, 255, 255, 0), **{k: tuple(int(v[i:i + 2], 16) for i in (1, 3, 5)) + (255,)
                                                        for k, v in COLORS.items()}})
    a = arr[0]
    share = {NAMES[c]: round(float((a == c).sum() / (a > 0).sum()), 4) for c in NAMES}
    json.dump(share, open(LUOUT / "landuse_hmda_2023_shares.json", "w"), indent=1)
    log(f"mosaic {a.shape}, class shares {share}")
    import matplotlib; matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import ListedColormap
    from matplotlib.patches import Patch
    step = max(1, a.shape[0] // 3000)
    cm = ListedColormap(["#ffffff"] + [COLORS[c] for c in range(1, 6)])
    fig, ax = plt.subplots(figsize=(13, 13))
    ax.imshow(a[::step, ::step], cmap=cm, vmin=0, vmax=5, interpolation="nearest")
    ax.legend(handles=[Patch(color=COLORS[c], label=NAMES[c]) for c in NAMES], loc="lower left", fontsize=11)
    ax.set_title("HMDA land use 2023, 10 m (our model, preliminary: OSM-trained, not yet validated)")
    ax.set_axis_off(); fig.tight_layout()
    fig.savefig(LUOUT / "landuse_hmda_2023.png", dpi=120)


if __name__ == "__main__":
    main()
