"""
Candidate factors built from data already on disk, at the sampled cells of both HMDA samples.
Every factor is dated at or before the start of its period (t0 = 2017 or 2020) or is fixed geography.

  ln_d_ps        ln(km + 0.1) to the nearest polling station, ECI list of April 2017. Polling stations are
                 mostly village schools / panchayat buildings, so this is distance to the settlement core
                 (gramakantham), the Hyderabad analogue of "distance to the village". Dated 2017: valid for both.
  ps_1km         polling stations within 1 km (settlement density, 2017).
  lag_chg_pct    % of the 1 km window that changed in the previous period (2017-20 change, for 2020-23 only):
                 development momentum, lagged so it is known at t0. (already in the sample as chg_prev_1km)
  ln_d_school    ln(km + 0.1) to the nearest school / college / university mapped in OSM at t0
                 (Geofabrik snapshot of 1 Jan t0+1, i.e. as mapped at the end of t0).
  ln_d_health    same for hospital / clinic / doctors.
  ln_poi_1km     ln(1 + OSM amenity / shop / office features within 1 km) at t0.
  inside_orr     inside the Outer Ring Road (convex hull of its interchanges; ORR complete by 2012-13).

Output: experiments/feature_tests/feat_local.parquet  keyed by (period, x, y)
"""
from pathlib import Path
import numpy as np, pandas as pd, geopandas as gpd
from scipy.spatial import cKDTree
from shapely.geometry import MultiPoint
from shapely import contains_xy

ROOT = Path(__file__).resolve().parents[2]
CH = ROOT / "data/processed/change"
cells = pd.concat([pd.read_parquet(CH / f, columns=["period", "t0", "x", "y", "chg_prev_1km"])
                   for f in ("hmda_cells_census.parquet", "hmda_persist_cells_census.parquet")]).drop_duplicates(["period", "x", "y"])
xy = cells[["x", "y"]].to_numpy()
out = cells[["period", "x", "y"]].copy()

ps = gpd.read_file(ROOT / "data/processed/polling_stations_2017_hmda.gpkg").to_crs(32644)
t = cKDTree(np.c_[ps.geometry.x, ps.geometry.y])
out["ln_d_ps"] = np.log(t.query(xy)[0] / 1000 + 0.1)
out["ps_1km"] = [len(i) for i in t.query_ball_point(xy, 1000)]

out["lag_chg_pct"] = np.where(cells.t0 == 2020, 100 * cells.chg_prev_1km, np.nan)

for y in (2017, 2020):
    g = gpd.read_file(ROOT / f"data/processed/lu20/osm_{y}/geofabrik.gpkg").to_crs(32644)
    pts = g.geometry.representative_point()
    P = np.c_[pts.x, pts.y]
    m = (cells.t0 == y).to_numpy()
    for name, mask in (("school", g.amenity.isin(["school", "college", "university", "kindergarten"])),
                       ("health", g.amenity.isin(["hospital", "clinic", "doctors"]))):
        out.loc[m, f"ln_d_{name}"] = np.log(cKDTree(P[mask.to_numpy()]).query(xy[m])[0] / 1000 + 0.1)
    poi = (g.amenity.notna() | g.shop.notna() | g.office.notna()).to_numpy()
    out.loc[m, "ln_poi_1km"] = np.log1p([len(i) for i in cKDTree(P[poi]).query_ball_point(xy[m], 1000)])
    print(y, "schools", int((g.amenity.isin(["school", "college", "university", "kindergarten"])).sum()),
          "health", int(g.amenity.isin(["hospital", "clinic", "doctors"]).sum()), "poi", int(poi.sum()))

orr = gpd.read_file(next((ROOT / "data/processed/lu/prox").glob("*orr*"))).to_crs(32644)
hull = MultiPoint(list(zip(orr.geometry.x, orr.geometry.y))).convex_hull
out["inside_orr"] = contains_xy(hull, xy[:, 0], xy[:, 1]).astype(int)
print("ORR interchanges", len(orr), "hull km2", round(hull.area / 1e6))

out.drop(columns=[]).to_parquet(ROOT / "experiments/feature_tests/feat_local.parquet", index=False)
print(out.describe().T[["count", "mean", "min", "max"]])
