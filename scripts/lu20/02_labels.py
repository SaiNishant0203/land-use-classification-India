"""
10 m training labels for one year, from that year's OSM (01_osm_dated.py). Same rules and class
priority as scripts/lu/04_labels.py:
  5 open   OSM farmland/grass/... OR (WorldCover AND Dynamic World crop/grass/bare/shrub AND GHS not built)
  4 forest OSM forest OR (WorldCover tree AND Dynamic World tree)           both outside OSM built use
  3 water  2023: at least 2 of {JRC occurrence >= 80%, WorldCover water, DW 2023 water}
           2017, 2020: JRC occurrence >= 80% AND (WorldCover OR DW water)
           (WorldCover 2021 and DW 2023 show reservoirs filled after 2017, e.g. Kondapochamma Sagar;
            JRC covers 1984-2021, so requiring it leaves such pixels unlabelled in earlier years)
  1 residential, then 2 non-residential painted last (a school inside a residential polygon is 2)
  0 within 300 m of a hand-label point, and everything no rule touched
The land-cover products (DW 2023, WorldCover 2021, JRC, GHS-BUILT-C 2018) are the same for every
year; only the OSM part and the water rule change.

Usage: python 02_labels.py <year>
Output: data/raw/lu/lu20/lab_<year>/<tile>.tif, outputs/lu20/label_stats_<year>.csv
"""
import sys, glob
import numpy as np, pandas as pd, geopandas as gpd, rasterio
from rasterio.features import rasterize
from rasterio.transform import from_origin
from shapely.geometry import box
from common20 import *

EXCLUDE_M = 300
RES_LANDUSE = {"residential"}
NONRES_LANDUSE = {"industrial", "commercial", "retail", "education", "civic"}
OPEN_LANDUSE = {"farmland", "farmyard", "meadow", "grass", "orchard", "quarry", "brownfield", "greenfield",
                "village_green", "plant_nursery"}
FOREST_LANDUSE = {"forest"}
RES_BUILDING = {"residential", "house", "apartments", "detached", "terrace", "dormitory", "semidetached_house",
                "bungalow"}
NONRES_BUILDING = {"commercial", "industrial", "office", "retail", "warehouse", "school", "university", "college",
                   "hospital", "government", "public", "civic", "hotel", "supermarket", "factory"}
NONRES_AMENITY = {"school", "college", "university", "hospital", "clinic", "townhall", "police", "fire_station",
                  "courthouse", "bus_station", "marketplace", "prison", "research_institute", "library",
                  "community_centre", "place_of_worship"}
NONRES_SHOP = {"mall", "supermarket", "department_store", "wholesale"}


def load_osm(year):
    g = pd.concat([gpd.read_file(f) for f in glob.glob(str(OSM / f"osm_{year}" / "*.gpkg"))], ignore_index=True)
    g = g[g.geom_type.isin(["Polygon", "MultiPolygon"])].to_crs(32644)
    lu, b, am = g.landuse, g.building, g.amenity
    sel = {"res": lu.isin(RES_LANDUSE) | b.isin(RES_BUILDING),
           "nonres": lu.isin(NONRES_LANDUSE) | am.isin(NONRES_AMENITY) | g.office.notna() | g.shop.isin(NONRES_SHOP)
                     | b.isin(NONRES_BUILDING),
           "open": lu.isin(OPEN_LANDUSE), "forest": lu.isin(FOREST_LANDUSE)}
    out = {}
    for k, m in sel.items():
        out[k] = g.loc[m, ["geometry"]].drop_duplicates().reset_index(drop=True)
        log(f"  {year} {k}: {len(out[k])} polygons, {out[k].area.sum() / 1e6:.1f} km2")
    return out


def main():
    year = int(sys.argv[1])
    assert (W20 / f"osm_{year}.done").exists(), f"OSM for {year} not complete; run 01_osm_dated.py"
    T = tiles()
    out = W20 / f"lab_{year}"; out.mkdir(exist_ok=True)
    osm = load_osm(year)
    val = gpd.read_file(LUP / "validation_points.gpkg", layer="validation_pixels").to_crs(32644)
    excl = gpd.GeoDataFrame(geometry=val.geometry.centroid.buffer(EXCLUDE_M), crs=32644)
    stats = []
    for n, (k, (minx, miny, maxx, maxy)) in enumerate(T.items(), 1):
        tr = from_origin(minx, maxy, 10, 10); shp = (TS, TS); bb = box(minx, miny, maxx, maxy)
        with rasterio.open(RAW / "prod" / f"{k}.tif") as s:
            dw, wc, jrc, ghsc = (s.read(i) for i in (1, 2, 3, 4))

        def paint(g):
            g = g[g.intersects(bb)]
            if not len(g):
                return np.zeros(shp, bool)
            return rasterize(((geom, 1) for geom in g.geometry), shp, transform=tr, dtype="uint8").astype(bool)

        res, nonres = paint(osm["res"]), paint(osm["nonres"])
        built_use = res | nonres
        lab = np.zeros(shp, np.uint8)
        ghs_built = (ghsc >= 11) & (ghsc <= 25)
        open_prod = np.isin(wc, [20, 30, 40, 60]) & np.isin(dw, [2, 4, 5, 7]) & ~ghs_built
        lab[(paint(osm["open"]) | open_prod) & ~built_use] = 5
        lab[(paint(osm["forest"]) | ((wc == 10) & (dw == 1))) & ~built_use] = 4
        if year >= 2023:
            water = ((jrc >= 80).astype(int) + (wc == 80) + (dw == 0)) >= 2
        else:
            water = (jrc >= 80) & ((wc == 80) | (dw == 0))
        lab[water] = 3
        lab[res] = 1
        lab[nonres] = 2
        lab[paint(excl)] = 0
        with rasterio.open(out / f"{k}.tif", "w", driver="GTiff", width=TS, height=TS, count=1, dtype="uint8",
                           crs="EPSG:32644", transform=tr, compress="deflate") as d:
            d.write(lab, 1)
        stats.append({"tile": k, **{f"c{c}": int((lab == c).sum()) for c in range(6)}})
        if n % 100 == 0:
            log(f"  {n}/{len(T)} tiles")
    st = pd.DataFrame(stats)
    st.to_csv(OUT / f"label_stats_{year}.csv", index=False)
    (W20 / f"labels_{year}.done").write_text("ok")
    log(f"{year} labelled pixels per class:\n" + st.drop(columns="tile").sum().to_string())


if __name__ == "__main__":
    main()
