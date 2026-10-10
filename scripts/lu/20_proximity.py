"""
Proximity variables: straight-line distance (km) from any point to
  - fixed landmarks: old CBD (Abids), Charminar, Secunderabad station, Cyber Towers / HITEC
    City, Financial District (Nanakramguda), RGIA airport;
  - the nearest Outer Ring Road (ORR) access point (interchange);
  - the nearest metro station open by the end of 2017, and by the end of 2020 (all three
    corridors were complete by then);
  - the nearest major road (motorway / trunk / primary / secondary and their links) in the
    OpenStreetMap network as it was mapped on 1 January of a given year (Overpass query with
    [date:...]). Caveat: OSM mapping completeness grew over time, not only the road network.

Usage:
    P = Prox(years=("2023",))
    d = P.at(x, y)          # x, y in EPSG:32644 -> DataFrame, one d_* column per distance

Inputs, all in data/processed/lu/prox/:
    roads_major_<year>.gpkg        downloaded from Overpass if missing (no account needed)
    orr_access.gpkg                ORR interchange points
    metro_stations_opening.csv     station positions and opening dates
"""
import json
import numpy as np, pandas as pd, geopandas as gpd, requests
from shapely.geometry import Point, shape
from shapely import STRtree
from scipy.spatial import cKDTree
from lu_common import LU, UTM, ROOT, RAW, log

PX = LU / "prox"; PX.mkdir(exist_ok=True)
BBOX = "77.90,16.90,79.10,18.00"            # covers HMDA
LANDMARKS = {                               # lon, lat (Nominatim-checked 2026-10-02)
    "cbd_abids": (78.4772, 17.3895),
    "charminar": (78.4746, 17.3616),
    "secunderabad": (78.5021, 17.4339),
    "hitec_cyber_towers": (78.3801, 17.4507),
    "financial_district": (78.3410, 17.4180),
    "airport_rgia": (78.4294, 17.2403),
}


def overpass_roads(date):
    """Major roads as mapped in OSM on `date` (Overpass attic query); cached as GeoPackage."""
    tag = date[:4] if date else "now"
    fp = PX / f"roads_major_{tag}.gpkg"
    if fp.exists():
        return gpd.read_file(fp)
    cache = LU / f"overpass_roads_{tag}.json"
    if not cache.exists():
        import time
        els, ok = {}, True
        lats, lons = np.linspace(16.90, 18.00, 4), np.linspace(77.90, 79.10, 4)
        for i in range(3):
            for j in range(3):
                s, n, w, e = lats[i], lats[i + 1], lons[j], lons[j + 1]
                cell = LU / "prox" / f"overpass_{tag}_{i}{j}.json"
                if cell.exists():
                    for el in json.loads(cell.read_text(encoding="utf-8"))["elements"]:
                        els[el["id"]] = el
                    continue
                dt = f'[date:"{date}T00:00:00Z"]' if date else ""
                q = (f'[out:json][timeout:600]{dt};'
                     'way[highway~"^(motorway|motorway_link|trunk|trunk_link|primary|secondary)$"]'
                     f'({s},{w},{n},{e});out geom;')
                for k in range(6):
                    u = ("https://overpass-api.de/api/interpreter",
                         "https://overpass.kumi.systems/api/interpreter")[k % 2]
                    try:
                        r = requests.post(u, data={"data": q}, timeout=700,
                                          headers={"User-Agent": "iith-landuse-research/0.1"})
                        if r.status_code == 200 and r.content.startswith(b"{"):
                            cell.write_bytes(r.content)
                            for el in r.json()["elements"]:
                                els[el["id"]] = el
                            log(f"  overpass {date} cell {i},{j}: ok ({len(els)} ways so far)")
                            break
                        log(f"  overpass {date} cell {i},{j}: HTTP {r.status_code}, retry {k}")
                    except Exception as ex:
                        log(f"  overpass {date} cell {i},{j}: {str(ex)[:80]}, retry {k}")
                    time.sleep(min(300, 30 * 2 ** k))
                else:
                    ok = False
        if not ok:
            raise RuntimeError(f"Overpass attic query for {date} failed")
        cache.write_text(json.dumps({"elements": list(els.values())}), encoding="utf-8")
    from shapely.geometry import LineString
    els = json.loads(cache.read_text(encoding="utf-8"))["elements"]
    g = gpd.GeoDataFrame({"highway": [e["tags"].get("highway") for e in els]},
                         geometry=[LineString([(p["lon"], p["lat"]) for p in e["geometry"]]) for e in els
                                   if len(e.get("geometry", [])) > 1], crs=4326).to_crs(UTM)
    g.to_file(fp, driver="GPKG")
    log(f"  OSM major roads {date}: {len(g)} ways, {g.length.sum() / 1000:.0f} km")
    return g


def orr_access():
    fp = PX / "orr_access.gpkg"
    if fp.exists():
        return gpd.read_file(fp)
    # rebuild from an OSM motorway extract (only needed if orr_access.gpkg is deleted)
    mw = gpd.read_file(RAW / "overnight" / "osm_motorways.gpkg").to_crs(UTM)
    txt = (mw.get("name", "").astype(str) + " " + mw.get("ref", "").astype(str)).str.lower()
    main = mw[txt.str.contains("outer ring|\\borr\\b|nehru outer", regex=True) & (mw["highway"] == "motorway")]
    links = mw[mw["highway"] == "motorway_link"]
    ring = main.geometry.union_all()
    pts = []
    for geom in links[links.geometry.distance(ring) < 30].geometry:
        for part in getattr(geom, "geoms", [geom]):
            cs = list(part.coords); pts += [cs[0], cs[-1]]
    acc = gpd.GeoDataFrame(geometry=[Point(p) for p in pts], crs=UTM)
    acc["k"] = (acc.geometry.x // 800).astype(int).astype(str) + "_" + (acc.geometry.y // 800).astype(int).astype(str)
    acc = gpd.GeoDataFrame(geometry=list(acc.dissolve("k").centroid), crs=UTM)
    acc.to_file(fp, driver="GPKG")
    log(f"  ORR access points: {len(acc)}")
    return acc


def metro(by):
    st = pd.read_csv(PX / "metro_stations_opening.csv")
    st = st[pd.to_datetime(st.opened) <= pd.Timestamp(by)]
    return st[["x", "y"]].values


class Prox:
    def __init__(self, years=("2017", "2020", "2023")):
        to = lambda lon, lat: gpd.GeoSeries([Point(lon, lat)], crs=4326).to_crs(UTM).iloc[0]
        self.lm = {k: to(*v) for k, v in LANDMARKS.items()}
        self.roads = {}
        for yr in years:
            try:
                self.roads[yr] = overpass_roads(f"{yr}-01-01")
            except RuntimeError as ex:
                log(f"  WARNING {ex}; using the CURRENT network for {yr}")
                self.roads[yr] = overpass_roads(None)
        self.trees = {y: STRtree(list(g.geometry)) for y, g in self.roads.items()}
        self.geoms = {y: list(g.geometry) for y, g in self.roads.items()}
        acc = orr_access()
        self.kd = {"orr_access": cKDTree(np.c_[acc.geometry.x, acc.geometry.y]),
                   "metro_2017": cKDTree(metro("2017-12-31")),
                   "metro_2020": cKDTree(metro("2020-12-31"))}

    def at(self, x, y):
        x, y = np.asarray(x, float), np.asarray(y, float)
        out = {}
        for k, p in self.lm.items():
            out[f"d_{k}"] = np.hypot(x - p.x, y - p.y) / 1000
        out["d_employment"] = np.minimum(out["d_hitec_cyber_towers"], out["d_financial_district"])
        for k, t in self.kd.items():
            out[f"d_{k}"] = t.query(np.c_[x, y])[0] / 1000
        import shapely
        pts = shapely.points(x, y)
        for yr in self.trees:
            idx = self.trees[yr].nearest(pts)
            geo = np.array(self.geoms[yr], dtype=object)[idx]
            out[f"d_major_road_{yr}"] = shapely.distance(pts, geo) / 1000
        return pd.DataFrame(out)


if __name__ == "__main__":
    P = Prox()
    d = P.at([231000, 220000], [1921000, 1930000])
    log("\n" + d.round(2).T.to_string())
