"""
OSM land-use sources as mapped at the end of each year, from Geofabrik's dated snapshots
(download.geofabrik.de, no login; each file is the OSM database as of 1 January of the next year):

  2017 -> india-180101.osm.pbf          2020 -> india-210101.osm.pbf
  2023 -> india/southern-zone-240101.osm.pbf   (the southern zone contains all of HMDA)
  2018, 2019, 2021, 2022 -> india-190101, india-200101, india-220101, india-230101 (final maps only)

Replaces 01_osm_dated.py (Overpass history queries), which stalled because overpass-api.de was at
capacity and then unreachable. GDAL's OSM driver (through pyogrio) reads the file, keeps the HMDA
bounding box and the tags used by 02_labels.py, and assembles multipolygons.

Usage: python 01b_osm_geofabrik.py [years...]
Input:  data/raw/osm_snapshots/<file>
Output: data/processed/lu20/osm_<year>/geofabrik.gpkg, data/raw/lu/lu20/osm_<year>.done,
        outputs/lu20/osm_counts.csv. Any partial Overpass tiles are moved to osm_<year>_overpass_partial/.
"""
import sys, time, shutil, warnings
import pandas as pd, geopandas as gpd, pyogrio
from common20 import *

warnings.filterwarnings("ignore")
SNAP = RAW.parent / "osm_snapshots"
FILES = {2017: "india-180101.osm.pbf", 2020: "india-210101.osm.pbf", 2023: "southern-zone-240101.osm.pbf",
         2018: "india-190101.osm.pbf", 2019: "india-200101.osm.pbf", 2021: "india-220101.osm.pbf",
         2022: "india-230101.osm.pbf"}
AMENITY = ["school", "college", "university", "hospital", "clinic", "townhall", "police", "fire_station", "courthouse",
           "bus_station", "marketplace", "place_of_worship", "prison", "community_centre", "library", "research_institute"]
SHOP = ["mall", "supermarket", "department_store", "wholesale"]
BUILDING = ["commercial", "industrial", "office", "retail", "warehouse", "apartments", "residential", "house", "detached",
            "terrace", "school", "university", "college", "hospital", "government", "public", "civic", "hotel",
            "supermarket", "factory", "dormitory", "semidetached_house", "bungalow"]
KEEP = ["landuse", "amenity", "office", "shop", "building", "name"]
q = lambda v: ",".join(f"'{x}'" for x in v)
WHERE = (f"landuse IS NOT NULL OR office IS NOT NULL OR amenity IN ({q(AMENITY)}) OR shop IN ({q(SHOP)}) "
         f"OR building IN ({q(BUILDING)})")
pyogrio.set_gdal_config_options({"OSM_MAX_TMPFILE_SIZE": "6000"})     # MB of node index kept in RAM


def main():
    years = [int(a) for a in sys.argv[1:]] or YEARS
    aoi = gpd.read_file(PROC / "aoi_utm44n.gpkg").to_crs(4326)
    if TEST:
        T = tiles(); x0 = min(b[0] for b in T.values()); x1 = max(b[2] for b in T.values())
        y0 = min(b[1] for b in T.values()); y1 = max(b[3] for b in T.values())
        bbox = tuple(gpd.GeoSeries.from_xy([x0, x1], [y0, y1], crs=32644).to_crs(4326).total_bounds)
    else:
        bbox = tuple(aoi.total_bounds)
    rows = []
    for y in years:
        f = SNAP / FILES[y]
        if not f.exists():
            log(f"{y}: {f.name} missing; skipped"); continue
        t = time.time()
        g = pyogrio.read_dataframe(f, layer="multipolygons", bbox=bbox, where=WHERE, columns=KEEP + ["osm_id", "osm_way_id"])
        g = g[g.geom_type.isin(["Polygon", "MultiPolygon"]) & g.geometry.notna()]
        g["osm_id"] = ("r" + g.osm_id.astype(str)).where(g.osm_id.notna(), "w" + g.osm_way_id.astype(str))
        g = g[KEEP + ["osm_id", "geometry"]].reset_index(drop=True)
        d = OSM / f"osm_{y}"
        if d.exists() and any(p.name != "geofabrik.gpkg" for p in d.iterdir()):
            shutil.move(str(d), str(OSM / f"osm_{y}_overpass_partial"))
        d.mkdir(exist_ok=True)
        g.to_file(d / "geofabrik.gpkg", driver="GPKG")
        (W20 / f"osm_{y}.done").write_text(f"{FILES[y]} (Geofabrik snapshot)")
        log(f"{y}: {len(g):,} polygons from {FILES[y]} in {(time.time() - t) / 60:.1f} min")
        gu = g.to_crs(32644)
        for col in ("landuse", "amenity", "office", "shop", "building"):
            s = gu[gu[col].notna()]
            rows.append({"year": y, "tag": col, "polygons": len(s), "km2": s.area.sum() / 1e6, "source": FILES[y]})
    if rows:
        p = OUT / "osm_counts.csv"
        new = pd.DataFrame(rows)
        if p.exists():
            new = pd.concat([pd.read_csv(p), new]).drop_duplicates(["year", "tag"], keep="last")
        new.sort_values(["tag", "year"]).to_csv(p, index=False)


if __name__ == "__main__":
    main()
