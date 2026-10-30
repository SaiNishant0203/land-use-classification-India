"""
20 m land-use maps for every year with a grid, from the pooled model (class + 5 class probabilities)
and from that year's own model (class), plus year-to-year stability statistics.

Stability: real land-use change in HMDA is ~0.1% of land per year, so most class changes between
maps are model noise. Reported per model type: share of cells whose class changes, the flip-flop
share (2020 differs, 2017 and 2023 agree), built -> open reversals (which almost never happen on the
ground), inside HMDA and in the two 2 x 2 km windows of 13_change.py.

Usage: python 06_maps.py
Output: outputs/lu20/maps/landuse_<year>_20m_pooled.tif (band 1 class 1-5, 0 outside HMDA;
        bands 2-6 P(class) x 100), landuse_<year>_20m_year.tif (class), outputs/lu20/map_stats.csv
"""
import pickle, time
import numpy as np, pandas as pd, geopandas as gpd, rasterio
from rasterio.features import rasterize
from rasterio.transform import from_origin
from pyproj import Transformer
from common20 import *
import features20 as FX


def main():
    years = years_done("grid")
    M = OUT / "maps"; M.mkdir(exist_ok=True)
    have_pooled = (OUT / "models" / "pooled.pkl").exists()
    cls = {}
    for y in years:
        grid = FX.open_grid(y); meta = grid["meta"]; ny, nx = meta["ny"], meta["nx"]
        tr = from_origin(meta["minx"], meta["maxy"], CELL, CELL)
        aoi = gpd.read_file(PROC / "aoi_utm44n.gpkg").to_crs(32644)
        inside = rasterize(((g, 1) for g in aoi.geometry), (ny, nx), transform=tr, dtype="uint8").astype(bool)
        mods = {"year": pickle.load(open(OUT / "models" / f"year_{y}.pkl", "rb"))}
        if have_pooled:
            mods["pooled"] = pickle.load(open(OUT / "models" / "pooled.pkl", "rb"))
        out = {k: np.zeros((ny, nx), np.uint8) for k in mods}
        prob = np.zeros((5, ny, nx), np.uint8) if have_pooled else None
        t = time.time()
        for r0, r1 in FX.strips(ny):
            gs, off = FX.load_strip(grid, r0, r1)
            v = gs["valid"][off:off + (r1 - r0)] & inside[r0:r1]
            if not v.any():
                continue
            names, F = FX.compute(gs)
            X = pd.DataFrame(np.stack([F[n][off:off + (r1 - r0)][v] for n in names], 1), columns=names)
            for k, (m, feats) in mods.items():
                p = m.predict_proba(X[feats])
                blk = out[k][r0:r1]; blk[v] = m.classes_[p.argmax(1)]
                if k == "pooled":
                    for c in range(5):
                        pb = prob[c, r0:r1]; pb[v] = np.round(p[:, c] * 100)
        log(f"{y}: mapped {int(inside.sum()):,} cells in {time.time() - t:.0f}s")
        prof = dict(driver="GTiff", width=nx, height=ny, crs="EPSG:32644", transform=tr, dtype="uint8",
                    compress="deflate", tiled=True, nodata=0)
        for k, a in out.items():
            nb = 6 if k == "pooled" else 1
            with rasterio.open(M / f"landuse_{y}_20m_{k}.tif", "w", count=nb, **prof) as d:
                d.write(a, 1)
                if k == "pooled":
                    d.write(prob, list(range(2, 7)))
        cls[y] = out
        cls[y]["_inside"] = inside
        cls["_meta"] = meta

    rows = []
    meta = cls.pop("_meta")
    for y in years:
        ins = cls[y]["_inside"]
        for k in [k for k in cls[y] if not k.startswith("_")]:
            a = cls[y][k][ins]
            rows.append({"stat": "class share", "model": k, "area": "HMDA", "period": str(y),
                         **{f"c{c}": float((a == c).mean()) for c in CL}})
    wins = {}
    tf = Transformer.from_crs(4326, 32644, always_xy=True)
    for n, (lat, lon) in WINDOWS.items():
        x, yy = tf.transform(lon, lat)
        r, c = int((meta["maxy"] - yy) // CELL), int((x - meta["minx"]) // CELL)
        h = 1000 // CELL
        if 0 <= r - h and r + h <= meta["ny"] and 0 <= c - h and c + h <= meta["nx"]:
            wins[n] = (slice(r - h, r + h), slice(c - h, c + h))
    pairs = [(a, b) for a, b in [(2017, 2020), (2020, 2023), (2017, 2023)] if a in cls and b in cls]
    for k in ["year", "pooled"]:
        if not all(k in cls[y] for y in years):
            continue
        areas = {"HMDA": cls[years[-1]]["_inside"]}
        for n, sl in wins.items():
            m = np.zeros_like(areas["HMDA"]); m[sl] = True; areas[n] = m & areas["HMDA"]
        for an, msk in areas.items():
            for a, b in pairs:
                A, Bm = cls[a][k][msk], cls[b][k][msk]
                rows.append({"stat": "changed class", "model": k, "area": an, "period": f"{a}-{b}",
                             "share": float((A != Bm).mean()),
                             "built_to_open": float((np.isin(A, [1, 2]) & (Bm == 5)).mean())})
            if all(y in cls for y in (2017, 2020, 2023)):
                A, Bm, C = (cls[y][k][msk] for y in (2017, 2020, 2023))
                rows.append({"stat": "flip-flop", "model": k, "area": an, "period": "2017-2020-2023",
                             "share": float(((A == C) & (Bm != A)).mean())})
    st = pd.DataFrame(rows)
    st.to_csv(OUT / "map_stats.csv", index=False)
    pd.set_option("display.width", 220)
    log("\n" + st.round(4).to_string(index=False))
    (W20 / "maps.done").write_text(str(years))


if __name__ == "__main__":
    main()
