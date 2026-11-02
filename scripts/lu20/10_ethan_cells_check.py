"""
What are the 281 cells in handlabelled_ethan.csv? Tests them against the rasters they came from.

  grid      are the cells 20 m squares (2 x 2 of the 10 m grid)?
  rule      does each cell meet the automatic source rule of 02c for its class, on all 4 pixels?
            If every cell does, no reviewer changed a class: review only accepted or rejected.
  vote      how many of the 4 pixels agree, in the label tile and in each product, to separate
            "all 4 agree" from a majority vote
  training  how many are already labelled the same way in the 2023 training grid
  model     how often year_2023 predicts their class, against the same model on the hand labels

Usage: python 10_ethan_cells_check.py
Output: outputs/lu20/ethan_cells/ethan_cells_check.csv (printed summary)
"""
import json, pickle
import numpy as np, pandas as pd, rasterio
from rasterio.windows import Window
from scipy.spatial import cKDTree
from pyproj import Transformer
from common20 import *
import features20 as FX

NAMES = {1: "residential", 2: "non-res", 3: "water", 4: "forest", 5: "open"}
D = OUT / "ethan_cells"; D.mkdir(exist_ok=True)


def tile_of(x0, y1, T):
    for k, (minx, miny, maxx, maxy) in T.items():
        if minx <= x0 < maxx and miny < y1 <= maxy:
            return k, minx, maxy
    return None, None, None


def main():
    e = pd.read_csv(LUP / "handlabelled_ethan.csv")
    T = tiles()
    print("cells per class:", e["class"].map(NAMES).value_counts().sort_index().to_dict())
    print("all centres at 10 m past a multiple of 20 m:", bool(((e.x % 20 == 10) & (e.y % 20 == 10)).all()))
    rows = []
    for _, c in e.iterrows():
        x0, y1 = int(c.x - 10), int(c.y + 10)
        k, minx, maxy = tile_of(x0, y1, T)
        if k is None:
            continue
        col, row = (x0 - minx) // 10, (maxy - y1) // 10
        win = Window(col, row, 2, 2)
        with rasterio.open(RAW / "prod" / f"{k}.tif") as s:
            dw, wc, jrc, ghs, wri, ind = s.read(window=win)
        with rasterio.open(RAW / "lab" / f"{k}.tif") as s:
            lab26 = s.read(1, window=win)
        with rasterio.open(W20 / "lab_2023" / f"{k}.tif") as s:
            lab23 = s.read(1, window=win)
        with rasterio.open(RAW / "feat_2023" / f"{k}.tif") as s:
            cov = (s.read(8, window=win).astype(float) / 1000).clip(0)
        cl = int(c["class"])
        built = (dw == 6) & (wc == 50)
        rule = {1: (lab26 == 1) & built & (ghs >= 11) & (ghs <= 15),
                2: (lab26 == 2) & built & (((ghs >= 21) & (ghs <= 25)) | (ind == 1) | (wri == 1)),
                3: (lab26 == 3) & (dw == 0) & (wc == 80) & (jrc >= 80) & (jrc <= 100),
                4: (lab26 == 4) & (dw == 1) & (wc == 10),
                5: (lab26 == 5) & np.isin(dw, [2, 4, 5, 7]) & np.isin(wc, [20, 30, 40, 60]) & ~((ghs >= 11) & (ghs <= 25))}
        dw_ok = {1: [6], 2: [6], 3: [0], 4: [1], 5: [2, 4, 5, 7]}[cl]
        wc_ok = {1: [50], 2: [50], 3: [80], 4: [10], 5: [20, 30, 40, 60]}[cl]
        rows.append({"id": c.id, "x": c.x, "y": c.y, "cls": cl, "rule_px": int(rule[cl].sum()),
                     "lab26_px": int((lab26 == cl).sum()), "lab23_px": int((lab23 == cl).sum()),
                     "dw_px": int(np.isin(dw, dw_ok).sum()), "wc_px": int(np.isin(wc, wc_ok).sum()),
                     "cov_mean": float(cov.mean()), "cov_min": float(cov.min())})
    d = pd.DataFrame(rows)
    print(f"\ncells found in tiles: {len(d)} of {len(e)}")
    print("\npixels of 4 meeting the automatic rule for the cell's class:")
    print(pd.crosstab(d.cls.map(NAMES), d.rule_px).to_string())
    print("\npixels of 4 agreeing with the class, per source (counts of cells):")
    for k in ["lab26_px", "lab23_px", "dw_px", "wc_px"]:
        print(f"  {k}: " + str(d[k].value_counts().sort_index(ascending=False).to_dict()))
    print("\nOpen Buildings cover (mean over the 4 pixels) by class:")
    print(d.groupby(d.cls.map(NAMES)).cov_mean.describe()[["min", "50%", "max"]].round(2).to_string())

    grid = FX.open_grid(2023); meta = grid["meta"]
    d["r"] = ((meta["maxy"] - d.y) // CELL).astype(int); d["c"] = ((d.x - meta["minx"]) // CELL).astype(int)
    d["flat"] = d.r * meta["nx"] + d.c
    d = d.sort_values("flat").reset_index(drop=True)
    L = np.stack([np.array(grid["labc"][c])[d.r, d.c] for c in CL])
    d["train_label"] = np.where(L.sum(0) / (K * K) >= MIN_LFRAC, L.argmax(0) + 1, 0)
    print("\n2023 training-grid label vs Ethan's class:")
    print(pd.crosstab(d.cls.map(NAMES), d.train_label.map({0: "unlabelled", **NAMES})).to_string())
    s = pd.read_parquet(OUT / "samples_2023.parquet", columns=["flat", "label"])
    print(f"already rows in samples_2023: {d.flat.isin(s.flat).sum()} of {len(d)} (training rows {len(s):,})")

    names, X = FX.extract(grid, d.flat.values)
    X = pd.DataFrame(X, columns=names)
    m, feats = pickle.load(open(OUT / "models" / "year_2023.pkl", "rb"))
    d["pred"] = m.predict(X[feats]).astype(int)
    d["p_class"] = m.predict_proba(X[feats])[np.arange(len(d)), d.cls.values - 1].round(3)
    print("\nyear_2023 model on these cells:")
    print(pd.crosstab(d.cls.map(NAMES), d.pred.map(NAMES)).to_string())
    print(f"agreement {np.mean(d.pred == d.cls):.3f}; median P(class) {d.p_class.median():.3f}")
    hp = pd.read_csv(OUT / "esri_check" / "handlabel_points.csv")
    print(f"same model on the 313 hand labels, unweighted agreement {np.mean(hp.true_class == hp.ours_2023):.3f}")
    print("non-res only: Ethan cells "
          f"{np.mean(d.pred[d.cls == 2] == 2):.3f}, hand labels {np.mean(hp.ours_2023[hp.true_class == 2] == 2):.3f}")

    v = pd.read_csv(LUP / "validation_key.csv")
    vx, vy = Transformer.from_crs(4326, 32644, always_xy=True).transform(v.lon.values, v.lat.values)
    dist = cKDTree(np.c_[vx, vy]).query(np.c_[d.x, d.y])[0]
    print(f"\nnearest hand-label point: min {dist.min():.0f} m, median {np.median(dist):.0f} m")
    for cl, g in d.groupby("cls"):
        nn = cKDTree(g[["x", "y"]].values).query(g[["x", "y"]].values, k=2)[0][:, 1]
        print(f"  nearest same-class cell, {NAMES[cl]}: median {np.median(nn):.0f} m, under 200 m: {(nn < 200).sum()}")
    d.drop(columns=["r", "c"]).to_csv(D / "ethan_cells_check.csv", index=False)


if __name__ == "__main__":
    main()
