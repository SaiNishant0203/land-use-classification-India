"""
Fetch OSM polygons that carry land-USE meaning beyond `landuse=*`:
institutional amenities, offices, malls, leisure, airports, and buildings whose
`building=*` tag states a function. Tile-by-tile with mirror retry and caching,
same pattern as scripts/osm_landuse_map.py.

Output: data/processed/lu/osm_extra_tiles/*.gpkg  (raw, WGS84)
"""
from pathlib import Path
import time, warnings
import numpy as np
import geopandas as gpd
import osmnx as ox
from shapely.geometry import box

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parents[2]
PROC = ROOT / "data/processed"
CACHE = PROC / "lu" / "osm_extra_tiles"; CACHE.mkdir(parents=True, exist_ok=True)

ox.settings.requests_timeout = 300
ox.settings.overpass_rate_limit = True
MIRRORS = ["https://overpass-api.de/api/interpreter",
           "https://overpass.kumi.systems/api/interpreter",
           "https://maps.mail.ru/osm/tools/overpass/api/interpreter"]

QUERIES = {
    "amenity": {"amenity": ["school", "college", "university", "hospital", "clinic",
                            "townhall", "police", "fire_station", "courthouse",
                            "bus_station", "marketplace", "place_of_worship", "prison",
                            "community_centre", "library", "research_institute"]},
    "office": {"office": True},
    "shopmall": {"shop": ["mall", "supermarket", "department_store", "wholesale"]},
    "leisure": {"leisure": ["park", "stadium", "golf_course", "sports_centre", "pitch",
                            "nature_reserve", "garden", "playground"]},
    "aeroway": {"aeroway": ["aerodrome"]},
    "building": {"building": ["commercial", "industrial", "office", "retail", "warehouse",
                              "apartments", "residential", "house", "detached", "terrace",
                              "school", "university", "college", "hospital", "government",
                              "public", "civic", "hotel", "supermarket", "factory",
                              "dormitory", "semidetached_house", "bungalow"]},
}
KEEP = ["amenity", "office", "shop", "leisure", "aeroway", "building", "landuse", "name"]

poly = gpd.read_file(PROC / "aoi_utm44n.gpkg").to_crs(4326).geometry.iloc[0]
N = 4
minx, miny, maxx, maxy = poly.bounds
xs = np.linspace(minx, maxx, N + 1)
ys = np.linspace(miny, maxy, N + 1)

for q, tags in QUERIES.items():
    for i in range(N):
        for j in range(N):
            fp = CACHE / f"{q}_{i}_{j}.gpkg"
            tile = box(xs[i], ys[j], xs[i + 1], ys[j + 1]).intersection(poly)
            if tile.is_empty or fp.exists():
                continue
            for k in range(6):
                ox.settings.overpass_url = MIRRORS[k % len(MIRRORS)]
                try:
                    try:
                        g = ox.features_from_polygon(tile, tags)
                    except ox._errors.InsufficientResponseError:
                        g = gpd.GeoDataFrame(geometry=[], crs=4326)
                    if len(g):
                        g = g[g.geom_type.isin(["Polygon", "MultiPolygon"])]
                        g = g[[c for c in KEEP if c in g.columns] + ["geometry"]].reset_index(drop=True)
                    g["src"] = q
                    g.to_file(fp, driver="GPKG")
                    print(f"[ok] {q} {i},{j}: {len(g)}", flush=True)
                    break
                except Exception as e:
                    print(f"[retry {k}] {q} {i},{j}: {type(e).__name__} {e}"[:200], flush=True)
                    time.sleep(8 * (k + 1))
            else:
                print(f"[FAIL] {q} {i},{j}", flush=True)
print("done")
