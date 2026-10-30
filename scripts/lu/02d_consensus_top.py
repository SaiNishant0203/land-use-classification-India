"""
Keep the most confident N consensus cells per class from consensus20_cells.gpkg (02c).

Ranking, best first, by score = purity + 0.3 if OSM 2023 confirms the class:
  purity  share of the 100 m x 100 m block around the cell where his label tile, Dynamic
          World and WorldCover all agree with the class (cells deep inside a lake, colony or
          forest beat cells near an edge)
  OSM     confirmed cells get a bonus over "silent" ones (OSM maps nothing there), but a
          confirmed cell on a forest edge does not outrank a silent one deep inside the forest
Ties: his trained model predicts the class on all 4 pixels, then its mean probability.
The model is used only to rank cells that already passed every source check, never to pick them.

With --total T, keep T cells in all, split across classes in proportion to the HMDA 2023 class
shares estimated from the random hand labels (stratum-weighted), best-scoring cells first.

Output: data/processed/lu/consensus20_top<N>.gpkg or consensus20_hmda<T>.gpkg (+ .kml), same
fields and QGIS form as 02c, plus `purity`, `model_prob` and `score`.
Usage: python 02d_consensus_top.py [n_per_class]     |     python 02d_consensus_top.py --total 150
"""
import importlib, os, sys
from pathlib import Path
import numpy as np, pandas as pd, geopandas as gpd, rasterio
from rasterio.windows import Window
from lu_common import LU, LURAW, log

C = importlib.import_module("02c_consensus_cells_20m")
TOTAL = int(sys.argv[2]) if len(sys.argv) > 2 and sys.argv[1] == "--total" else 0
N = 0 if TOTAL else (int(sys.argv[1]) if len(sys.argv) > 1 else 150)
RAW = Path(os.environ.get("LU_RAW", LURAW))
HALF = 5                                          # 10 pixels = 100 m block centred on the cell
DW_OK = {1: [6], 2: [6], 3: [0], 4: [1], 5: [2, 4, 5, 7]}
WC_OK = {1: [50], 2: [50], 3: [80], 4: [10], 5: [20, 30, 40, 60]}


def scores(u):
    pur, agree, prob = [], [], []
    for _, r in u.iterrows():
        tl = rasterio.open(RAW / "lab" / f"{r.tile}.tif")
        x0, y1 = r.geometry.bounds[0], r.geometry.bounds[3]
        col, row = int((x0 - tl.bounds.left) / 10), int((tl.bounds.top - y1) / 10)
        win = Window(col + 1 - HALF, row + 1 - HALF, 2 * HALF, 2 * HALF)
        c = int(r.proposed_class)
        lab = tl.read(1, window=win, boundless=True, fill_value=0); tl.close()
        with rasterio.open(RAW / "prod" / f"{r.tile}.tif") as s:
            dw = s.read(1, window=win, boundless=True, fill_value=255)
            wc = s.read(2, window=win, boundless=True, fill_value=255)
        pur.append(float(((lab == c) & np.isin(dw, DW_OK[c]) & np.isin(wc, WC_OK[c])).mean()))
        with rasterio.open(RAW / "pred_2023" / f"{r.tile}.tif") as s:
            p = s.read(window=Window(col, row, 2, 2))
        agree.append(bool((p[0] == c).all()))
        prob.append(float(p[1].mean()) if agree[-1] else 0.0)
    return np.array(pur), np.array(agree), np.array(prob)


def hmda_shares():
    """Area share of each class in HMDA 2023, estimated from the 325 random hand labels with
    stratum weights (Olofsson et al. 2014), as in 07_eval_handlabels."""
    v = gpd.read_file(LU / "validation_points.gpkg", layer="validation_pixels")[["pid", "true_class"]]
    d = pd.read_csv(LU / "validation_key.csv").merge(v, on="pid").dropna(subset=["true_class"])
    w = pd.read_csv(LU / "validation_strata.csv", index_col=0)["weight"]
    p = pd.concat([w[h] * d[d.stratum == h].true_class.value_counts(normalize=True) for h in w.index],
                  axis=1).fillna(0).sum(axis=1)
    return p.reindex(range(1, 6), fill_value=0) / p.sum()


def allocate(total, shares):
    """Largest-remainder split of `total` cells in proportion to `shares`."""
    raw = shares * total
    n = np.floor(raw).astype(int)
    n[(raw - n).sort_values(ascending=False).index[:total - n.sum()]] += 1
    return n


def main():
    u = gpd.read_file(LU / "consensus20_cells.gpkg", layer="consensus_cells")
    if TOTAL:
        sh = hmda_shares(); quota = allocate(TOTAL, sh)
        log("HMDA shares from hand labels: " + ", ".join(f"{c} {100 * s:.1f}%" for c, s in sh.items()))
        log("cells per class: " + quota.to_string().replace("\n", ", "))
    u["purity"], agree, u["model_prob"] = scores(u)
    u["purity"] = u.purity.round(2)
    u["score"] = (u.purity + 0.3 * (u.osm2023 == "confirms")).round(2)
    u["_agree"] = agree.astype(int)
    ranked = u.sort_values(["score", "_agree", "model_prob"], ascending=False)
    if TOTAL:
        top = pd.concat([ranked[ranked.proposed_class == c].head(int(quota[c])) for c in quota.index])
    else:
        top = ranked.groupby("proposed_class", group_keys=False).head(N)
    top = top.sample(frac=1, random_state=C.SEED).reset_index(drop=True)
    top["pid"] = np.arange(1, len(top) + 1)
    log("kept per class:\n" + pd.crosstab(top.proposed_class, top.osm2023).to_string())
    log("purity of kept cells (min / median):\n" +
        top.groupby("proposed_class").purity.agg(["min", "median"]).to_string())
    log(f"model agrees on all 4 pixels: {int(top._agree.sum())} of {len(top)}")
    top = top.drop(columns=["_agree"])
    tag = f"hmda{TOTAL}" if TOTAL else f"top{N}"
    fp = LU / f"consensus20_{tag}.gpkg"
    fp.unlink(missing_ok=True)
    top.to_file(fp, layer="consensus_cells", driver="GPKG")
    C.add_style(fp)
    top.to_crs(4326).assign(Name=top.pid.astype(str) + " " + top.proposed_class.map(C.NAMES))[["Name", "geometry"]] \
       .to_file(LU / f"consensus20_{tag}.kml", driver="KML")
    log(f"wrote {fp} ({len(top)} cells)")


if __name__ == "__main__":
    main()
