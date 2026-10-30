"""
New, independent stratified random sample of 20 m cells for hand-labelling (TEST SET ONLY).

Same design as 02_validation_sample.py, but the sampling unit is a 20 m cell on the
experiments/res100 grid (2 x 2 pixels of the 10 m grid, corners at multiples of 20 m in
EPSG:32644), and strata are read from the local raster tiles instead of Earth Engine.

Strata (model-independent, decided per cell from its 4 pixels, first rule that fits wins):
  S1 any pixel OSM non-residential (lab == 2)   S2 >= 2 pixels Dynamic World 'built'
  S3 >= 2 pixels DW water   S4 >= 2 pixels DW trees   S5 everything else
S1 uses the lab/ tiles' OSM non-residential layer, a close proxy for the polygons 02 used.

Cells within 400 m of the 10 m test pixels are excluded, so this set shares no ground with it.
Each cell carries its stratum area weight (Olofsson et al. 2014).

Needs the raster zip: prod/, lab/, pred_2023/ and feat_2023/tiles.json under data/raw/lu/,
or set LU_RAW to the folder that holds them.

Outputs (data/processed/lu/):
  validation20_cells.gpkg  - 20 m squares, same QGIS dropdowns/colours as the 10 m file
  validation20_cells.kml   - same cells for Google Earth Pro
  validation20_key.csv     - pid -> stratum, weight, and what labels/products/our model say in
                             the cell (open only after labelling, it would bias the labels)
  validation20_strata.csv  - stratum cell counts and weights
"""
import importlib.util, json, os
from pathlib import Path
import numpy as np, pandas as pd, geopandas as gpd, rasterio
from rasterio.features import rasterize
from rasterio.transform import from_origin
from scipy.spatial import cKDTree
from shapely.geometry import box
from lu_common import LU, LURAW, PROC, UTM, log

N_PER_STRATUM = {1: 70, 2: 130, 3: 30, 4: 35, 5: 60}          # 325 cells, as in 02
SEED = 20261016
CELL = 20
K = CELL // 10                                                 # 10 m pixels per cell edge
EXCL_M = 400                                                   # distance from 10 m test pixels
RAW = Path(os.environ.get("LU_RAW", LURAW))

spec = importlib.util.spec_from_file_location("vs", Path(__file__).with_name("02_validation_sample.py"))
vs = importlib.util.module_from_spec(spec); spec.loader.exec_module(vs)


def blocks(a):
    """(400, 400) -> (200, 200, 4): the 4 pixels of each 20 m cell."""
    n = a.shape[0] // K
    return a.reshape(n, K, n, K).transpose(0, 2, 1, 3).reshape(n, n, K * K)


def cell_strata(lab, dw):
    lb, db = blocks(lab), blocks(dw)
    s = np.full(lb.shape[:2], 5, np.uint8)
    s[(db == 1).sum(-1) >= 2] = 4
    s[(db == 0).sum(-1) >= 2] = 3
    s[(db == 6).sum(-1) >= 2] = 2
    s[(lb == 2).any(-1)] = 1
    return s


def main():
    tiles = json.loads((RAW / "feat_2023" / "tiles.json").read_text())
    aoi = gpd.read_file(PROC / "aoi_utm44n.gpkg").to_crs(UTM).geometry.iloc[0]
    old = gpd.read_file(LU / "validation_points.gpkg", layer="validation_pixels").to_crs(UTM).geometry.centroid
    tree = cKDTree(np.c_[old.x, old.y])
    n = 4000 // CELL
    off = (np.arange(n) + 0.5) * CELL

    strata = {}                                                # tile -> (200, 200) stratum, 0 = not eligible
    for k, (minx, miny, maxx, maxy) in tiles.items():
        with rasterio.open(RAW / "prod" / f"{k}.tif") as s:
            dw = s.read(1)
        with rasterio.open(RAW / "lab" / f"{k}.tif") as s:
            lab = s.read(1)
        st = cell_strata(lab, dw)
        inside = rasterize([(aoi.intersection(box(minx, miny, maxx, maxy)), 1)], (n, n),
                           transform=from_origin(minx, maxy, CELL, CELL), dtype="uint8").astype(bool)
        st[~inside | (blocks(dw) == 255).any(-1)] = 0
        cx, cy = np.meshgrid(minx + off, maxy - off)          # row 0 = north edge
        near = tree.query(np.c_[cx.ravel(), cy.ravel()], distance_upper_bound=EXCL_M)[0] < np.inf
        st[near.reshape(n, n)] = 0
        strata[k] = st
    names = list(strata)
    stack = np.stack([strata[k] for k in names])               # (tiles, 200, 200)
    cnt = {s: int((stack == s).sum()) for s in N_PER_STRATUM}
    st = pd.DataFrame({"cells_20m": cnt}); st.index.name = "stratum"
    st["area_km2"] = st.cells_20m * CELL * CELL / 1e6
    st["weight"] = st.cells_20m / st.cells_20m.sum()
    st["n_sample"] = [N_PER_STRATUM[s] for s in st.index]
    st.to_csv(LU / "validation20_strata.csv"); log("\n" + st.to_string())

    # equal-probability sample within each stratum
    rng = np.random.default_rng(SEED)
    flat = stack.ravel()
    picks = []
    for s, m in N_PER_STRATUM.items():
        idx = np.flatnonzero(flat == s)
        picks += [(s, i) for i in rng.choice(idx, m, replace=False)]
    rows = []
    for s, i in picks:
        t, r, c = np.unravel_index(i, stack.shape)
        k = names[t]; minx, _, _, maxy = tiles[k]
        x0, y1 = minx + c * CELL, maxy - r * CELL
        win = rasterio.windows.Window(c * K, r * K, K, K)
        with rasterio.open(RAW / "lab" / f"{k}.tif") as f:
            lab = f.read(1, window=win).ravel()
        with rasterio.open(RAW / "prod" / f"{k}.tif") as f:
            dw, wc = f.read(1, window=win).ravel(), f.read(2, window=win).ravel()
        with rasterio.open(RAW / "pred_2023" / f"{k}.tif") as f:
            pred = f.read(1, window=win).ravel()
        agree = int(lab[0]) if (lab > 0).all() and (lab == lab[0]).all() else 0
        rows.append({"stratum": s, "tile": k, "geometry": box(x0, y1 - CELL, x0 + CELL, y1),
                     "lab_pixels": "".join(map(str, lab)), "lab_all_agree": agree,
                     "dw_pixels": " ".join(map(str, dw)), "wc_pixels": " ".join(map(str, wc)),
                     "pred10_pixels": "".join(map(str, pred))})
    v = gpd.GeoDataFrame(rows, crs=UTM).sample(frac=1, random_state=SEED).reset_index(drop=True)
    v.insert(0, "pid", np.arange(1, len(v) + 1))
    v["stratum_weight"] = v.stratum.map(st.weight)
    ll = v.geometry.centroid.to_crs(4326)
    v["lon"], v["lat"] = ll.x, ll.y

    v.drop(columns="geometry").to_csv(LU / "validation20_key.csv", index=False)
    u = v[["pid", "lon", "lat", "geometry"]].copy()
    u["true_class"] = pd.Series([None] * len(u), dtype="Int64")
    u["confidence"] = pd.Series([None] * len(u), dtype="Int64")   # 1 sure / 2 probably / 3 guess
    u["is_road"] = pd.Series([None] * len(u), dtype="Int64")
    u["notes"] = ""
    fp = LU / "validation20_cells.gpkg"
    fp.unlink(missing_ok=True)
    u.to_file(fp, layer="validation_pixels", driver="GPKG")
    vs.add_qgis_style(fp)
    u.to_crs(4326).assign(Name=u.pid.astype(str))[["Name", "geometry"]] \
     .to_file(LU / "validation20_cells.kml", driver="KML")
    log(f"wrote {fp} ({len(u)} cells) and validation20_cells.kml")
    log(v.stratum.value_counts().sort_index().to_string())


if __name__ == "__main__":
    main()
