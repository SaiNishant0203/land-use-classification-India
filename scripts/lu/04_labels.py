"""
Training labels at 10 m on the tile grid, 5 classes:
  1 residential  2 non-residential built  3 water  4 forest/trees  5 other open   (0 = unlabelled)

Sources and rules (same "use of the compound" rule as the hand-labelling guide):
  1  OSM landuse=residential polygons + buildings tagged residential/house/apartments/...
  2  OSM landuse industrial/commercial/retail/education/civic, institutional amenities,
     offices, malls, buildings tagged commercial/industrial/office/school/hospital/...
     -> painted AFTER residential, so a school inside a residential polygon stays 2
  3  at least two of {JRC occurrence >= 80 %, WorldCover water, Dynamic World 2023 water}.
     JRC alone misses reservoirs built after its 1984-2021 window (e.g. Kondapochamma Sagar,
     Kaleshwaram, ~2020), which the model then read as residential.
  4  (OSM forest polygon OR (WorldCover tree AND DW 2023 tree))  and outside OSM built-use
  5  OSM farmland/grass/meadow/orchard/quarry/brownfield/greenfield, OR
     (WorldCover crop/grass/bare/shrub AND DW crop/grass/bare/shrub AND GHS not built)
     and outside OSM built-use
Pixels within EXCLUDE_M of a hand-labelled validation pixel are set to 0 (never train on test).

Output: data/raw/lu/lab/<tile>.tif (uint8)
"""
import glob, json
import numpy as np, pandas as pd, geopandas as gpd, rasterio
from rasterio.features import rasterize
from rasterio.transform import from_origin
from shapely.geometry import box
from lu_common import LU, LURAW, PROC, UTM, log

EXCLUDE_M = 300
RES_LANDUSE = {"residential"}
NONRES_LANDUSE = {"industrial", "commercial", "retail", "education", "civic"}
OPEN_LANDUSE = {"farmland", "farmyard", "meadow", "grass", "orchard", "quarry", "brownfield",
                "greenfield", "village_green", "plant_nursery"}
FOREST_LANDUSE = {"forest"}
RES_BUILDING = {"residential", "house", "apartments", "detached", "terrace", "dormitory",
                "semidetached_house", "bungalow"}
NONRES_BUILDING = {"commercial", "industrial", "office", "retail", "warehouse", "school",
                   "university", "college", "hospital", "government", "public", "civic",
                   "hotel", "supermarket", "factory"}
NONRES_AMENITY = {"school", "college", "university", "hospital", "clinic", "townhall", "police",
                  "fire_station", "courthouse", "bus_station", "marketplace", "prison",
                  "research_institute", "library", "community_centre", "place_of_worship"}


def load_osm():
    lu = pd.concat([gpd.read_file(f) for f in glob.glob(str(PROC / "osm_cache/landuse_tiles/*.gpkg"))])
    ex = {q: [gpd.read_file(f) for f in glob.glob(str(LU / f"osm_extra_tiles/{q}_*.gpkg"))]
          for q in ["amenity", "office", "shopmall", "building"]}
    ex = {q: pd.concat([x for x in v if len(x)]) for q, v in ex.items()}
    parts = {
        "res": [lu[lu.landuse.isin(RES_LANDUSE)], ex["building"][ex["building"].building.isin(RES_BUILDING)]],
        "nonres": [lu[lu.landuse.isin(NONRES_LANDUSE)],
                   ex["amenity"][ex["amenity"].amenity.isin(NONRES_AMENITY)],
                   ex["office"], ex["shopmall"],
                   ex["building"][ex["building"].building.isin(NONRES_BUILDING)]],
        "open": [lu[lu.landuse.isin(OPEN_LANDUSE)]],
        "forest": [lu[lu.landuse.isin(FOREST_LANDUSE)]],
    }
    out = {}
    for k, v in parts.items():
        g = gpd.GeoDataFrame(pd.concat([x[["geometry"]] for x in v]), crs=4326).to_crs(UTM)
        g = g[g.geom_type.isin(["Polygon", "MultiPolygon"])].reset_index(drop=True)
        out[k] = g
        log(f"  {k}: {len(g)} polygons, {g.area.sum()/1e6:.1f} km2")
    return out


def main():
    tiles = json.loads((LURAW / "feat_2023" / "tiles.json").read_text())
    out = LURAW / "lab"; out.mkdir(exist_ok=True)
    osm = load_osm()
    val = gpd.read_file(LU / "validation_points.gpkg", layer="validation_pixels").to_crs(UTM)
    excl = val.geometry.centroid.buffer(EXCLUDE_M)
    todo = [k for k in tiles if not (out / f"{k}.tif").exists() and (LURAW / "prod" / f"{k}.tif").exists()]
    log(f"{len(todo)} tiles to label")
    stats = []
    for k in todo:
        minx, miny, maxx, maxy = tiles[k]
        tr = from_origin(minx, maxy, 10, 10); shp = (400, 400); bb = box(minx, miny, maxx, maxy)
        with rasterio.open(LURAW / "prod" / f"{k}.tif") as s:
            dw, wc, jrc, ghsc = (s.read(i) for i in (1, 2, 3, 4))

        def paint(g, all_touched=False):
            g = g[g.intersects(bb)]
            if not len(g):
                return np.zeros(shp, bool)
            return rasterize(((geom, 1) for geom in g.geometry), shp, transform=tr,
                             all_touched=all_touched, dtype="uint8").astype(bool)

        res, nonres = paint(osm["res"]), paint(osm["nonres"])
        o_open, o_forest = paint(osm["open"]), paint(osm["forest"])
        built_use = res | nonres
        lab = np.zeros(shp, np.uint8)
        ghs_built = (ghsc >= 11) & (ghsc <= 25)
        open_prod = np.isin(wc, [20, 30, 40, 60]) & np.isin(dw, [2, 4, 5, 7]) & ~ghs_built
        lab[(o_open | open_prod) & ~built_use] = 5
        lab[(o_forest | ((wc == 10) & (dw == 1))) & ~built_use] = 4
        lab[((jrc >= 80).astype(int) + (wc == 80) + (dw == 0)) >= 2] = 3
        lab[res] = 1
        lab[nonres] = 2                      # institutional/commercial inside residential wins
        lab[paint(gpd.GeoDataFrame(geometry=excl, crs=UTM))] = 0
        with rasterio.open(out / f"{k}.tif", "w", driver="GTiff", width=400, height=400, count=1,
                           dtype="uint8", crs=f"EPSG:{UTM}", transform=tr, compress="deflate") as d:
            d.write(lab, 1)
        stats.append({"tile": k, **{f"c{c}": int((lab == c).sum()) for c in range(6)}})
    if stats:
        st = pd.DataFrame(stats)
        prev = LU / "label_stats.csv"
        if prev.exists():
            st = pd.concat([pd.read_csv(prev), st]).drop_duplicates("tile", keep="last")
        st.to_csv(prev, index=False)
        log("pixels per class:\n" + st.drop(columns="tile").sum().to_string())


if __name__ == "__main__":
    main()
