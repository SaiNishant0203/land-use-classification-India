"""
Adds the rest of the CHANGE_MODEL_PLAN.md §5c factors to the trial sample (trial_cells.parquet from
02_trial_data.py), so the full model can be fitted. All factors are measured at the start year t0 of
the period, except the two marked as checks.

  land use nearby  res_1km, nonres_1km, water_1km, trees_1km (open is the reference), lu_mix_1km
                   (entropy of the 5 class shares / ln 5), all from the final map at t0, 1 km window
  built-up edge    d_urban: km to the nearest cell whose 1 km built share is >= 0.4 (the dense city)
  night lights     viirs_1km: VIIRS annual average radiance at t0 (nW/cm2/sr), 1 km window
  roads            major_km_4km (motorway..secondary + links), minor_km_4km (tertiary, unclassified,
                   residential, living street) in the 4 x 4 km window, OSM at t0.
                   CHECK: road_gain_4km = all-road km added during the period (OSM at t1 - at t0)
  terrain          elev_m, slope_deg (Copernicus GLO-30), relief_m (st. dev. of elevation within
                   150 m: rock outcrops and boulders), sampled in Earth Engine at the points
  lakes            d_lake: km to a water body >= 2 ha (final map 2023, the fullest water extent);
                   near_lake: within 100 m (a stand-in for the lake full-tank-level buffer, where
                   building is not allowed)
  restricted land  restricted: inside OSM military land, forest, protected area, nature reserve or
                   airport land (OSM at t0)
  GO 111           go111: within 10 km of the Osman Sagar or Himayat Sagar water spread (the
                   catchment zone where building was restricted from 1996 until April 2022). A
                   stand-in: the GO lists 84 villages, which we don't have as boundaries.
  contagion        chg_prev_1km: share of the 1 km window that changed in 2017 -> 2020 (same rule as
                   the outcome). 2020 -> 2023 period only.

Usage: python 04_more_factors.py
Output: data/processed/change/trial_cells_full.parquet
"""
import sys, json, time
from pathlib import Path
import numpy as np, pandas as pd, geopandas as gpd, rasterio, pyogrio
from rasterio.features import rasterize
from rasterio.transform import from_origin
from scipy.ndimage import uniform_filter, distance_transform_edt, label

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "lu"))
CH = ROOT / "data" / "processed" / "change"
G = ROOT / "data" / "raw" / "lu" / "lu20"
MAPS = ROOT / "outputs" / "lu20" / "maps_final"
OSM = ROOT / "data" / "raw" / "osm_snapshots"
SNAP = {2017: "india-180101.osm.pbf", 2020: "india-210101.osm.pbf", 2023: "southern-zone-240101.osm.pbf"}
MAJOR = ["motorway", "trunk", "primary", "secondary", "motorway_link", "trunk_link", "primary_link", "secondary_link"]
MINOR = ["tertiary", "tertiary_link", "unclassified", "residential", "living_street"]
CELL, PAD = 20, 6000
log = lambda *a: print(time.strftime("%H:%M:%S"), *a, flush=True)


def window(d, meta):
    X0, Y1 = meta["minx"], meta["maxy"]
    c0 = max(int((d.x.min() - PAD - X0) // CELL), 0); c1 = min(int((d.x.max() + PAD - X0) // CELL), meta["nx"])
    r0 = max(int((Y1 - d.y.max() - PAD) // CELL), 0); r1 = min(int((Y1 - d.y.min() + PAD) // CELL), meta["ny"])
    return r0, r1, c0, c1


def osm_polys(snap, bbox):
    """Restricted land and the two GO 111 lakes from one OSM snapshot, cached (reading multipolygons
    from the India file takes minutes)."""
    fn = CH / f"osm_constraints_{snap.split('.')[0]}.gpkg"
    if fn.exists():
        return gpd.read_file(fn)
    w = ("military IS NOT NULL OR landuse IN ('military','forest') OR boundary='protected_area' "
         "OR aeroway='aerodrome' OR leisure='nature_reserve' OR natural='water'")
    t = time.time()
    g = pyogrio.read_dataframe(OSM / snap, layer="multipolygons", bbox=bbox, where=w,
                               columns=["name", "landuse", "military", "boundary", "aeroway", "leisure", "natural"])
    g = g.to_crs(32644); g = g[g.geometry.notna() & g.is_valid]
    g.to_file(fn); log(f"  OSM polygons {snap}: {len(g):,} ({time.time() - t:.0f}s)")
    return g


def ee_terrain(d):
    from lu_common import ee_init
    ee = ee_init()
    dem = ee.ImageCollection("COPERNICUS/DEM/GLO30_2024_1").select("DEM").mosaic() \
        .setDefaultProjection(ee.ImageCollection("COPERNICUS/DEM/GLO30_2024_1").first().select("DEM").projection())
    img = ee.Image.cat([dem.rename("elev_m"), ee.Terrain.slope(dem).rename("slope_deg"),
                        dem.reduceNeighborhood(ee.Reducer.stdDev(), ee.Kernel.circle(150, "meters")).rename("relief_m")])
    lon, lat = gpd.GeoSeries.from_xy(d.x, d.y, crs=32644).to_crs(4326).pipe(lambda s: (s.x.values, s.y.values))
    out = np.full((len(d), 3), np.nan)
    B = 2500
    for i in range(0, len(d), B):
        fc = ee.FeatureCollection([ee.Feature(ee.Geometry.Point([float(lon[j]), float(lat[j])]), {"i": j})
                                   for j in range(i, min(i + B, len(d)))])
        r = img.reduceRegions(fc, ee.Reducer.first(), scale=30).getInfo()["features"]
        for f in r:
            p = f["properties"]; out[p["i"]] = [p.get("elev_m", np.nan), p.get("slope_deg", np.nan), p.get("relief_m", np.nan)]
        log(f"  terrain {min(i + B, len(d)):,}/{len(d):,}")
    return out


def main():
    d = pd.read_parquet(CH / "trial_cells.parquet").reset_index(drop=True)
    meta = json.loads((G / "grid_2020" / "meta.json").read_text())
    X0, Y1 = meta["minx"], meta["maxy"]
    r0, r1, c0, c1 = window(d, meta); ny, nx = r1 - r0, c1 - c0
    tr = from_origin(X0 + c0 * CELL, Y1 - r0 * CELL, CELL, CELL)
    cx = X0 + (np.arange(c0, c1) + 0.5) * CELL; cy = Y1 - (np.arange(r0, r1) + 0.5) * CELL
    bbox = tuple(gpd.GeoSeries.from_xy([cx[0], cx[-1]], [cy[-1], cy[0]], crs=32644).to_crs(4326).total_bounds)
    rr = ((Y1 - d.y.values) // CELL).astype(int) - r0; cc = ((d.x.values - X0) // CELL).astype(int) - c0
    log(f"window {ny} x {nx} cells, {len(d):,} sample cells")

    def rd(y):
        with rasterio.open(MAPS / f"landuse_{y}_20m.tif") as s:
            return s.read(1, window=((r0, r1), (c0, c1)))

    def grid(y, b):
        return np.array(np.load(G / f"grid_{y}" / "mean.npy", mmap_mode="r")[b, r0:r1, c0:c1], dtype=np.float32)

    def raster(gs):
        return rasterize(((g, 1) for g in gs), (ny, nx), transform=tr, dtype="uint8") if len(gs) else np.zeros((ny, nx), "uint8")

    # lakes: water bodies >= 2 ha in the 2023 map
    w23 = rd(2023) == 3
    lab, n = label(w23); sz = np.bincount(lab.ravel()); big = (sz >= 50); big[0] = False
    lake = big[lab]
    dl = distance_transform_edt(~lake) * CELL / 1000
    d["d_lake"] = dl[rr, cc]; d["near_lake"] = (dl[rr, cc] <= 0.1).astype(int)
    log(f"lakes >= 2 ha: {big.sum():,} water bodies")

    cols = {k: np.full(len(d), np.nan) for k in
            ["res_1km", "nonres_1km", "water_1km", "trees_1km", "lu_mix_1km", "d_urban", "viirs_1km", "major_km_4km",
             "minor_km_4km", "road_gain_4km", "restricted", "go111", "chg_prev_1km"]}
    for t0, t1 in ((2017, 2020), (2020, 2023)):
        m = (d.t0 == t0).values; i_r, i_c = rr[m], cc[m]
        ma = rd(t0)
        sh = {c: uniform_filter((ma == c).astype(np.float32), 51, mode="constant") for c in (1, 2, 3, 4, 5)}
        tot = sum(sh.values()) + 1e-9
        p = np.stack([sh[c] / tot for c in (1, 2, 3, 4, 5)])
        mix = -(np.where(p > 0, p * np.log(np.clip(p, 1e-12, 1)), 0)).sum(0) / np.log(5)
        for c, k in ((1, "res_1km"), (2, "nonres_1km"), (3, "water_1km"), (4, "trees_1km")):
            cols[k][m] = sh[c][i_r, i_c]
        cols["lu_mix_1km"][m] = mix[i_r, i_c]
        dense = (sh[1] + sh[2]) >= 0.4
        cols["d_urban"][m] = (distance_transform_edt(~dense) * CELL / 1000)[i_r, i_c]
        cols["viirs_1km"][m] = (uniform_filter(grid(t0, 11), 51, mode="constant") / 100)[i_r, i_c]

        km = {}
        for y in (t0, t1):
            t = time.time()
            q = ",".join(f"'{h}'" for h in MAJOR + MINOR)
            rl = pyogrio.read_dataframe(OSM / SNAP[y], layer="lines", bbox=bbox, where=f"highway IN ({q})",
                                        columns=["highway"]).to_crs(32644)
            for nm, cl in (("major", MAJOR), ("minor", MINOR)):
                a = raster(rl.geometry[rl.highway.isin(cl)].values).astype(np.float32)
                km[(y, nm)] = (uniform_filter(a, 201, mode="constant") * 201 ** 2 * CELL / 1000)[i_r, i_c]
            log(f"  roads {SNAP[y]}: {len(rl):,} lines ({time.time() - t:.0f}s)")
        cols["major_km_4km"][m] = km[(t0, "major")]; cols["minor_km_4km"][m] = km[(t0, "minor")]
        cols["road_gain_4km"][m] = (km[(t1, "major")] + km[(t1, "minor")]) - (km[(t0, "major")] + km[(t0, "minor")])

        g = osm_polys(SNAP[t0], bbox)
        res = g[g.natural.fillna("") != "water"]          # the query returns only restricted land or water
        cols["restricted"][m] = raster(res.geometry.values)[i_r, i_c]
        nm = g.name.fillna("").str.lower()
        go = g[(g.natural == "water") & (nm.str.contains("osman|gandipet|himayat|himayath"))]
        go = go[go.area > 2e6]
        log(f"  restricted polygons {len(res):,}; GO 111 lakes: {sorted(set(go.name))}, {go.area.sum() / 1e6:.0f} km2")
        if len(go):
            cols["go111"][m] = (gpd.GeoSeries(go.geometry.values, crs=32644).union_all().distance(
                gpd.points_from_xy(d.x[m], d.y[m], crs=32644)) <= 10000).astype(int)

        if t0 == 2020:      # change in the previous period, same rule as the outcome, all cells in the window
            m17, m20 = rd(2017), ma
            c17, c20 = grid(2017, 7), grid(2020, 7)
            und = np.isin(m17, [4, 5]) & (c17 < 0.05)
            y1 = und & np.isin(m20, [1, 2]) & (c20 >= 0.20) & (uniform_filter(c20, 3) - uniform_filter(c17, 3) >= 0.10)
            cols["chg_prev_1km"][m] = uniform_filter(y1.astype(np.float32), 51, mode="constant")[i_r, i_c]
    for k, v in cols.items():
        d[k] = v
    d[["elev_m", "slope_deg", "relief_m"]] = ee_terrain(d)
    fn = CH / "trial_cells_full.parquet"; d.to_parquet(fn)
    log(f"wrote {fn}"); print(d.drop(columns=["period"]).describe().T.round(3).to_string())


if __name__ == "__main__":
    main()
