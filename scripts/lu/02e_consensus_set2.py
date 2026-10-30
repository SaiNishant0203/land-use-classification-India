"""
Second batch of "sure" 20 m cells for manual verification: 30 per class, stricter than 02c/02d
after review of the first batch (set 1, 13 of 150 rejected, mostly forest, roads and yards):

  residential, non-res  the cell is on roofs, not roads or yards: Open Buildings cover >= 0.4 in
                        each of its 4 pixels and >= 0.6 on average
  forest                no building within ~50 m, and the 100 m block around it is all tree in
                        both Dynamic World and WorldCover
  open                  no tree pixel (DW or WorldCover) and no building within ~50 m
  all classes           the 02c rules (every source agrees on all 4 pixels, OSM 2023 confirms or,
                        for forest/open only, is silent), ranked by the 02d score

Cells are picked greedily, best score first, at least MIN_DIST m from every other new cell and
from every set-1 cell (relaxed step by step for a class that runs short, e.g. water), and
400 m from both hand-label test sets.

Output: data/processed/lu/consensus20_set2.gpkg (+ .kml); the OSM-checked candidate pool is
cached in consensus20_set2_pool.gpkg (delete it to rescan).
Usage: python 02e_consensus_set2.py [n_per_class]
"""
import importlib, json, os, sys
from pathlib import Path
import numpy as np, pandas as pd, geopandas as gpd, rasterio
from rasterio.features import rasterize
from rasterio.transform import from_origin
from scipy.ndimage import maximum_filter, minimum_filter
from scipy.spatial import cKDTree
from shapely.geometry import box
from lu_common import LU, LURAW, PROC, UTM, log

C = importlib.import_module("02c_consensus_cells_20m")
D = importlib.import_module("02d_consensus_top")
N = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 30
RAW = Path(os.environ.get("LU_RAW", LURAW))
SEED = 20261020
PER_TILE = {1: 6, 2: 6, 3: 150, 4: 6, 5: 6}     # water: few big lakes, take more per tile
POOL = 12                                       # candidates per needed cell sent to the OSM check
MIN_DIST = [2000, 1500, 1000, 600, 400]          # m; relaxed in this order if a class runs short (water)
PREV = ["consensus20_set1_reviewed.gpkg"]
CELL, K = 20, 2


def strict_masks(lab, p, cov):
    """02c class masks plus the set-2 rules, per 20 m cell."""
    m = C.class_masks(lab, p)
    dw, wc = p[0], p[1]
    cb = C.blocks(cov)
    roof = (cb.min(-1) >= 0.4) & (cb.mean(-1) >= 0.6)
    m[1] &= roof
    m[2] &= roof
    near_bldg = C.blocks(maximum_filter(cov, size=11) > 0.05).any(-1)          # building within ~50 m
    near_tree = C.blocks(maximum_filter(((dw == 1) | (wc == 10)).astype(np.uint8), size=11) > 0).any(-1)
    all_tree = C.blocks(minimum_filter(((dw == 1) & (wc == 10)).astype(np.uint8), size=10) > 0).all(-1)
    m[4] &= ~near_bldg & all_tree
    m[5] &= ~near_bldg & ~near_tree
    return m


def candidates(prev_pts):
    tiles = json.loads((RAW / "feat_2023" / "tiles.json").read_text())
    aoi = gpd.read_file(PROC / "aoi_utm44n.gpkg").to_crs(UTM).geometry.iloc[0]
    tests = [gpd.read_file(LU / f, layer="validation_pixels") for f in ("validation_points.gpkg", "validation20_cells.gpkg")]
    t = pd.concat([x.to_crs(UTM).geometry.centroid for x in tests])
    ttree, ptree = cKDTree(np.c_[t.x, t.y]), cKDTree(prev_pts)
    n = 4000 // CELL
    off = (np.arange(n) + 0.5) * CELL
    rng = np.random.default_rng(SEED)
    rows = []
    for i, (k, (minx, miny, maxx, maxy)) in enumerate(tiles.items()):
        with rasterio.open(RAW / "prod" / f"{k}.tif") as s:
            p = s.read()
        with rasterio.open(RAW / "lab" / f"{k}.tif") as s:
            lab = s.read(1)
        with rasterio.open(RAW / "feat_2023" / f"{k}.tif") as s:
            cov = s.read(8).astype(np.float32) / 1000
        cov[cov < 0] = 0
        inside = rasterize([(aoi.intersection(box(minx, miny, maxx, maxy)), 1)], (n, n),
                           transform=from_origin(minx, maxy, CELL, CELL), dtype="uint8").astype(bool)
        cx, cy = np.meshgrid(minx + off, maxy - off)
        xy = np.c_[cx.ravel(), cy.ravel()]
        ok = ((ttree.query(xy, distance_upper_bound=C.EXCL_M)[0] == np.inf) &
              (ptree.query(xy, distance_upper_bound=MIN_DIST[-1])[0] == np.inf)).reshape(n, n) & inside
        for cls, m in strict_masks(lab, p, cov).items():
            r, cc = np.nonzero(m & ok)
            for j in rng.permutation(len(r))[:PER_TILE[cls]]:
                rows.append({"cls": cls, "tile": k, "x0": minx + cc[j] * CELL, "y1": maxy - r[j] * CELL})
        if i % 100 == 0:
            log(f"  scanned {i} tiles")
    d = pd.DataFrame(rows)
    log("candidates per class:\n" + d.cls.value_counts().sort_index().to_string() +
        "\ntiles per class:\n" + d.groupby("cls").tile.nunique().to_string())
    return d


def pick(pool, prev_pts, n):
    """Greedy: best score first, keep a cell if it is >= dist from every kept and set-1 cell."""
    kept = []
    xy = np.c_[pool.geometry.centroid.x, pool.geometry.centroid.y]
    order = pool.sort_values(["score", "_agree", "model_prob"], ascending=False).index
    for c in sorted(pool.cls.unique()):
        idx = [i for i in order if pool.at[i, "cls"] == c]
        for dist in MIN_DIST:
            got = [i for i in kept if pool.at[i, "cls"] == c]
            for i in idx:
                if len(got) >= n or i in kept:
                    continue
                others = np.vstack([prev_pts] + ([xy[kept]] if kept else []))
                if np.hypot(*(others - xy[i]).T).min() >= dist:
                    kept.append(i); got.append(i)
            if len(got) >= n:
                break
        log(f"  class {c}: {len(got)} cells, spacing >= {dist} m")
    return pool.loc[kept]


def main():
    prev = pd.concat([gpd.read_file(LU / f, layer="consensus_cells").to_crs(UTM) for f in PREV])
    prev_pts = np.c_[prev.geometry.centroid.x, prev.geometry.centroid.y]
    cache = LU / "consensus20_set2_pool.gpkg"          # OSM-checked pool; delete to rebuild
    if cache.exists():
        pool = gpd.read_file(cache)
    else:
        d = candidates(prev_pts)
        rng = np.random.default_rng(SEED)
        pool = pd.concat([C.spread(d[d.cls == c], POOL * N, rng) for c in C.NAMES]).reset_index(drop=True)
        pool["cid"] = np.arange(len(pool))
        pool = gpd.GeoDataFrame(pool, geometry=[box(x, y - CELL, x + CELL, y) for x, y in zip(pool.x0, pool.y1)], crs=UTM)
        log(f"checking OSM {C.OSM_DATE} coverage for {len(pool)} cells")
        for c, f in C.OSM.items():
            pool[f"osm23_{c}"] = np.minimum(C.osm_cover(pool, f) / (CELL * CELL), 9.99).round(3)
            log(f"  OSM class {c} done")
        pool.to_file(cache, driver="GPKG")
    cov = pool[[f"osm23_{c}" for c in C.NAMES]].values
    own = cov[np.arange(len(pool)), pool.cls.values - 1]
    other = np.where(np.eye(5, dtype=bool)[pool.cls.values - 1], 0, cov).max(1)
    pool["osm2023"] = np.where((own >= 0.98) & (other <= 0.01), "confirms",
                               np.where((cov.max(1) == 0) & pool.cls.isin([4, 5]), "silent", "rejected"))
    log("OSM 2023:\n" + pd.crosstab(pool.cls, pool.osm2023).to_string())
    pool = pool[pool.osm2023 != "rejected"].reset_index(drop=True)
    pool["proposed_class"] = pool.cls
    pur, agree, prob = D.scores(pool)
    pool["purity"], pool["_agree"], pool["model_prob"] = np.round(pur, 2), agree.astype(int), prob
    pool["score"] = (pool.purity + 0.3 * (pool.osm2023 == "confirms")).round(2)
    sel = pick(pool, prev_pts, N)
    sel = sel.sample(frac=1, random_state=SEED).reset_index(drop=True)
    ll = sel.geometry.centroid.to_crs(4326)
    u = gpd.GeoDataFrame({"pid": np.arange(1, len(sel) + 1), "lon": ll.x.round(6), "lat": ll.y.round(6),
                          "proposed_class": sel.cls.astype(int), "true_class": sel.cls.astype(int),
                          "checked": 0, "confidence": pd.Series([None] * len(sel), dtype="Int64"),
                          "notes": "", "osm2023": sel.osm2023, "tile": sel.tile, "purity": sel.purity,
                          "model_prob": sel.model_prob, "score": sel.score},
                         geometry=sel.geometry.values, crs=UTM)
    allpts = np.c_[u.geometry.centroid.x, u.geometry.centroid.y]
    nn = cKDTree(allpts).query(allpts, k=2)[0][:, 1]
    log(f"nearest other new cell: min {nn.min():.0f} m, median {np.median(nn):.0f} m; "
        f"nearest set-1 cell: min {cKDTree(prev_pts).query(allpts)[0].min():.0f} m")
    fp = LU / "consensus20_set2.gpkg"
    fp.unlink(missing_ok=True)
    u.to_file(fp, layer="consensus_cells", driver="GPKG")
    C.add_style(fp)
    u.to_crs(4326).assign(Name=u.pid.astype(str) + " " + u.proposed_class.map(C.NAMES))[["Name", "geometry"]] \
     .to_file(LU / "consensus20_set2.kml", driver="KML")
    log(f"wrote {fp}\n" + pd.crosstab(u.proposed_class, u.osm2023).to_string())


if __name__ == "__main__":
    main()
