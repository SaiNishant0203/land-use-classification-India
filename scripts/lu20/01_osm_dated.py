"""
OSM land-use sources as mapped on 31 December of each year (Overpass attic query, [date:...]).

Same tags as 01_osm_label_sources.py + the landuse values used by 04_labels.py, fetched in one
union query per tile and year on an 8 x 8 grid over HMDA. Only overpass-api.de keeps OSM history
(the mirrors return HTTP 500 for [date:] queries), and it is often at capacity, so every pending
tile is retried in turn with back-off until LU20_OSM_HOURS (default 6) have passed. Each finished
tile is cached, so a rerun resumes.

Usage: python 01_osm_dated.py [years...]       (default 2017 2020 2023)
Output: data/processed/lu20/osm_<year>/<i>_<j>.gpkg, data/raw/lu/lu20/osm_<year>.done,
        outputs/lu20/osm_counts.csv
Test hooks: LU20_OSM_CURRENT=1 fetches current OSM from a mirror (no history) to test the code path.
"""
import os, sys, time, warnings
import numpy as np, pandas as pd, geopandas as gpd, requests
from shapely.geometry import box, Polygon, LineString
from shapely.ops import linemerge, polygonize, unary_union
from common20 import *

warnings.filterwarnings("ignore")
CURRENT = os.environ.get("LU20_OSM_CURRENT") == "1"
URL = "https://overpass.private.coffee/api/interpreter" if CURRENT else "https://overpass-api.de/api/interpreter"
HOURS = float(os.environ.get("LU20_OSM_HOURS", "6"))
NG = int(os.environ.get("LU20_OSM_GRID", "8"))      # NG x NG query tiles, ~15 km at 8

# A lean query (bounding box, geometry inline with `out geom`) answers in ~80 s for a dense 7.5 km
# box; osmnx's polygon filter plus recursion timed out at 20 min on history queries.
TAGS = {
    "amenity": ["school", "college", "university", "hospital", "clinic", "townhall", "police", "fire_station",
                "courthouse", "bus_station", "marketplace", "place_of_worship", "prison", "community_centre", "library",
                "research_institute"],
    "shop": ["mall", "supermarket", "department_store", "wholesale"],
    "building": ["commercial", "industrial", "office", "retail", "warehouse", "apartments", "residential", "house",
                 "detached", "terrace", "school", "university", "college", "hospital", "government", "public", "civic",
                 "hotel", "supermarket", "factory", "dormitory", "semidetached_house", "bungalow"],
}
CLAUSES = ['nwr["landuse"]', 'nwr["office"]'] + [f'nwr["{k}"~"^({"|".join(v)})$"]' for k, v in TAGS.items()]
KEEP = ["landuse", "amenity", "office", "shop", "building", "name"]


def osm_tiles():
    poly = gpd.read_file(PROC / "aoi_utm44n.gpkg").to_crs(4326).geometry.iloc[0]
    minx, miny, maxx, maxy = poly.bounds
    xs, ys = np.linspace(minx, maxx, NG + 1), np.linspace(miny, maxy, NG + 1)
    if TEST:                                               # only the OSM tiles under the test area
        T = tiles(); x0 = min(b[0] for b in T.values()); x1 = max(b[2] for b in T.values())
        y0 = min(b[1] for b in T.values()); y1 = max(b[3] for b in T.values())
        area = gpd.GeoSeries([box(x0, y0, x1, y1)], crs=32644).to_crs(4326).iloc[0]
        poly = poly.intersection(area)
    out = {}
    for i in range(NG):
        for j in range(NG):
            t = box(xs[i], ys[j], xs[i + 1], ys[j + 1])     # plain rectangle: a polygon clipped to the HMDA
            if t.intersects(poly):                            # boundary is too long for Overpass (HTTP 413)
                out[f"{i}_{j}"] = t if not TEST else box(*t.intersection(poly).bounds)
    return out


def rings(lines):
    """Polygons formed by a set of (possibly split) member ways."""
    lines = [l for l in lines if l.length > 0]
    if not lines:
        return None
    polys = list(polygonize(linemerge(lines)))
    return unary_union(polys) if polys else None


def to_geom(e):
    if e["type"] == "way":
        pts = [(p["lon"], p["lat"]) for p in e.get("geometry") or [] if p]
        if len(pts) >= 4 and pts[0] == pts[-1]:
            g = Polygon(pts)
            return g if g.is_valid else g.buffer(0)
    elif e["type"] == "relation" and e.get("tags", {}).get("type") in ("multipolygon", "boundary"):
        by = {"outer": [], "inner": []}
        for m in e.get("members", []):
            pts = [(p["lon"], p["lat"]) for p in m.get("geometry") or [] if p]
            if m.get("type") == "way" and len(pts) >= 2:
                by["inner" if m.get("role") == "inner" else "outer"].append(LineString(pts))
        outer, inner = rings(by["outer"]), rings(by["inner"])
        if outer is not None:
            return outer.difference(inner) if inner is not None else outer
    return None


def fetch(tile, date):
    w, s, e_, n = tile.bounds
    bb = f"{s:.5f},{w:.5f},{n:.5f},{e_:.5f}"
    dt = "" if CURRENT else f'[date:"{date}"]'
    q = f'[out:json][timeout:900]{dt};(' + "".join(f"{c}({bb});" for c in CLAUSES) + ");out geom;"
    r = requests.post(URL, data={"data": q}, timeout=(60, 1000), headers={"User-Agent": "iith-landuse-research/0.1"})
    if r.status_code != 200:
        raise RuntimeError(f"HTTP {r.status_code}: {r.text[:100]}")
    js = r.json()
    if "remark" in js and "error" in js["remark"].lower():          # server-side timeout or out-of-memory
        raise RuntimeError(js["remark"][:150])
    rows = []
    for el in js["elements"]:
        try:
            g = to_geom(el)
        except Exception:
            continue
        if g is None or g.is_empty or g.geom_type not in ("Polygon", "MultiPolygon"):
            continue
        t = el.get("tags", {})
        rows.append({**{c: t.get(c) for c in KEEP}, "osm_id": f"{el['type'][0]}{el['id']}", "geometry": g})
    if not rows:
        return gpd.GeoDataFrame({c: [] for c in KEEP + ["osm_id"]}, geometry=[], crs=4326)
    return gpd.GeoDataFrame(rows, crs=4326).astype({c: "object" for c in KEEP})


def main():
    years = [int(a) for a in sys.argv[1:]] or YEARS
    T = osm_tiles()
    todo = [(y, k) for y in years for k in T if not (OSM / f"osm_{y}" / f"{k}.gpkg").exists()]
    log(f"{len(T)} OSM tiles x {len(years)} years; {len(todo)} to fetch from {URL}")
    t_end, fails = time.time() + HOURS * 3600, 0
    pri = {y: n for n, y in enumerate(years)}
    while todo and time.time() < t_end:
        i = min(range(len(todo)), key=lambda j: (pri[todo[j][0]], j))   # finish the first-listed year first
        y, k = todo.pop(i)
        (OSM / f"osm_{y}").mkdir(exist_ok=True)
        t = time.time()
        try:
            g = fetch(T[k], OSM_DATE[y])
            g.to_file(OSM / f"osm_{y}" / f"{k}.gpkg", driver="GPKG")
            log(f"[ok] {y} tile {k}: {len(g)} polygons ({time.time() - t:.0f}s); {len(todo)} left")
            fails = 0
        except Exception as e:
            todo.append((y, k))                            # back of the queue; other tiles get a turn
            busy = isinstance(e, (requests.ConnectTimeout, requests.ConnectionError)) or \
                any(f"HTTP {c}" in str(e) for c in (429, 502, 503, 504))   # server full or refusing connections
            fails = 0 if busy else fails + 1
            wait = 60 if busy else min(600, 30 * 2 ** min(fails, 5))   # "at capacity" replies are instant: poll steadily
            log(f"[retry] {y} tile {k}: {type(e).__name__}: {str(e)[:120]} -> sleep {wait}s")
            time.sleep(wait)
    rows = []
    for y in years:
        files = [OSM / f"osm_{y}" / f"{k}.gpkg" for k in T]
        if all(f.exists() for f in files):
            (W20 / f"osm_{y}.done").write_text(OSM_DATE[y])
            g = pd.concat([gpd.read_file(f) for f in files]).to_crs(32644)
            for col in ("landuse", "amenity", "office", "shop", "building"):
                s = g[g[col].notna()]
                rows.append({"year": y, "tag": col, "polygons": len(s), "km2": s.area.sum() / 1e6})
            log(f"{y}: complete")
        else:
            log(f"{y}: INCOMPLETE ({sum(f.exists() for f in files)}/{len(files)} tiles)")
    if rows:
        p = OUT / "osm_counts.csv"
        new = pd.DataFrame(rows)
        if p.exists():
            new = pd.concat([pd.read_csv(p), new]).drop_duplicates(["year", "tag"], keep="last")
        new.sort_values(["tag", "year"]).to_csv(p, index=False)


if __name__ == "__main__":
    main()
