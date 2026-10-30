"""
OSM area behind each training-label rule, as mapped on 2023-06-30 vs 2026-07-27, for three
4 km tiles, from the ohsome history API (aggregate endpoint; its public geometry endpoint is
blocked). Tag groups are those of 04_labels.py, restricted to what 01_osm_label_sources.py fetches.

Area is the sum of polygon areas, so overlaps inside one group count twice; land-use polygons
and tagged buildings are kept as separate groups for that reason.

Output: results/area_by_date.csv
"""
import json, os, sys, time
from pathlib import Path
import pandas as pd, geopandas as gpd, requests
from shapely.geometry import box

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "scripts" / "lu"))
from lu_common import LURAW, UTM, log
import importlib
L = importlib.import_module("04_labels")
src01 = (HERE.parents[1] / "scripts" / "lu" / "01_osm_label_sources.py").read_text()
exec(src01[src01.index("QUERIES = {"):src01.index("KEEP = [")], globals())

RAW = Path(os.environ.get("LU_RAW", LURAW))
TIMES = "2023-06-30,2026-07-27"
SITES = {"financial_district": (78.3410, 17.4180), "kollur_tellapur": (78.2700, 17.4700),
         "charminar": (78.4746, 17.3616)}
OUT = HERE / "results"; OUT.mkdir(exist_ok=True)
inlist = lambda k, v: f"{k} in ({','.join(sorted(v))})"
amen = sorted(set(QUERIES["amenity"]["amenity"]) & L.NONRES_AMENITY)
GROUPS = {
    "res_landuse": "landuse=residential",
    "res_buildings": inlist("building", set(QUERIES["building"]["building"]) & L.RES_BUILDING),
    "nonres_landuse": inlist("landuse", L.NONRES_LANDUSE),
    "nonres_amenity_office_mall": f"{inlist('amenity', amen)} or office=* or {inlist('shop', QUERIES['shopmall']['shop'])}",
    "nonres_buildings": inlist("building", set(QUERIES["building"]["building"]) & L.NONRES_BUILDING),
    "open_landuse": inlist("landuse", L.OPEN_LANDUSE),
    "forest_landuse": "landuse=forest",
}


def main():
    tiles = json.loads((RAW / "feat_2023" / "tiles.json").read_text())
    boxes = []
    for site, (lon, lat) in SITES.items():
        p = gpd.GeoSeries(gpd.points_from_xy([lon], [lat]), crs=4326).to_crs(UTM).iloc[0]
        k = f"x{int(p.x // 4000 * 4)}_y{int(p.y // 4000 * 4)}"
        bb = gpd.GeoSeries([box(*tiles[k])], crs=UTM).to_crs(4326).total_bounds
        boxes.append(f"{site}:" + ",".join(f"{v:.6f}" for v in bb))
        log(f"{site}: tile {k}")
    rows = []
    for g, f in GROUPS.items():
        data = {"bboxes": "|".join(boxes), "time": TIMES, "filter": f"({f}) and geometry:polygon"}
        for k in range(5):
            try:
                r = requests.post("https://api.ohsome.org/v1/elements/area/groupBy/boundary", data=data, timeout=(15, 900))
                r.raise_for_status(); break
            except Exception as e:
                log(f"  retry {k} {g}: {type(e).__name__} {str(e)[:120]}"); time.sleep(30 * (k + 1))
        else:
            raise RuntimeError(g)
        for res in r.json()["groupByResult"]:
            for v in res["result"]:
                rows.append({"site": res["groupByObject"], "group": g, "date": v["timestamp"][:10], "km2": v["value"] / 1e6})
        log(f"  {g} done")
    d = pd.DataFrame(rows).pivot_table(index=["site", "group"], columns="date", values="km2").reset_index()
    a, b = sorted(c for c in d.columns if c[:2] == "20")
    d["change_km2"] = d[b] - d[a]
    d["pct_of_2026_added_after_2023"] = (100 * d.change_km2 / d[b]).where(d[b] > 0).round(1)
    d = d.round(4); d.to_csv(OUT / "area_by_date.csv", index=False)
    log("\n" + d.to_string(index=False))


if __name__ == "__main__":
    main()
