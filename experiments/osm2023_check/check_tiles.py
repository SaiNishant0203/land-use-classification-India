"""
How much do the OSM-derived training labels change if OSM is taken as of mid-2023 instead of
today? For a few 4 km tiles: fetch the same OSM layers as 01_osm_label_sources.py (and the
landuse=* layer) twice from the ohsome OSM-history API, as mapped on 2023-06-30 and on
2026-07-27 (the newest date ohsome holds), rebuild the label tile with the
exact rules of 04_labels.py from each, and compare.

Sanity check: the "now" rebuild should closely match the stored lab/ tile (made from OSM of
~Sept 2026 via Overpass).

Needs prod/ and lab/ from the raster zip under data/raw/lu/ or LU_RAW.
Output: results/summary.csv, results/transitions_<tile>.csv, results/<tile>.png
Usage: python check_tiles.py
"""
import json, os, sys, time
from pathlib import Path
import numpy as np, pandas as pd, geopandas as gpd, rasterio, requests
from rasterio.features import rasterize
from rasterio.transform import from_origin
from shapely.geometry import box

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "scripts" / "lu"))
from lu_common import LU, LURAW, UTM, log
import importlib
L = importlib.import_module("04_labels")
Q = {"landuse": {"landuse": True}}
src01 = (HERE.parents[1] / "scripts" / "lu" / "01_osm_label_sources.py").read_text()
exec(src01[src01.index("QUERIES = {"):src01.index("KEEP = [")], globals())   # his tag queries, verbatim
Q.update({k: QUERIES[k] for k in ["amenity", "office", "shopmall", "building"]})

RAW = Path(os.environ.get("LU_RAW", LURAW))
DATES = {"2023": "2023-06-30", "now": "2026-07-27"}   # ohsome data ends 2026-07-27; his OSM is ~Sept 2026
SITES = {                                     # lon, lat -> the 4 km tile containing it
    "financial_district": (78.3410, 17.4180),     # construction boom
    "kollur_tellapur": (78.2700, 17.4700),        # fringe high-rise growth along the ORR
    "charminar": (78.4746, 17.3616),              # old city, little change (control)
}
WORK = HERE / "work"; WORK.mkdir(exist_ok=True)
OUT = HERE / "results"; OUT.mkdir(exist_ok=True)
NAMES = {0: "unlabelled", 1: "residential", 2: "non-res", 3: "water", 4: "forest", 5: "open"}


def ohsome_filter(tags):
    """osmnx-style tag dict -> ohsome filter, polygons only (as 01/04 keep only polygons)."""
    parts = [f"{k}=*" if v is True else f"{k} in ({','.join(v)})" for k, v in tags.items()]
    return "(" + " or ".join(parts) + ") and geometry:polygon"


def fetch(tile, bb_ll, q, when):
    """OSM polygons as mapped at `when`, from the ohsome history API (HeiGIT)."""
    fp = WORK / f"{tile}_{q}_{when[:7]}.gpkg"
    if fp.exists():
        return gpd.read_file(fp)
    data = {"bboxes": ",".join(f"{v:.6f}" for v in bb_ll), "time": when,
            "filter": ohsome_filter(Q[q]), "properties": "tags"}
    for k in range(6):
        try:
            r = requests.post("https://api.ohsome.org/v1/elements/geometry", data=data, timeout=(15, 900))
            r.raise_for_status()
            feats = r.json()["features"]
            g = gpd.GeoDataFrame.from_features(feats, crs=4326) if feats else gpd.GeoDataFrame(geometry=[], crs=4326)
            g = g[[c for c in ["landuse", "amenity", "office", "shop", "building"] if c in g.columns] + ["geometry"]]
            g.to_file(fp, driver="GPKG")
            log(f"  {tile} {q} {when}: {len(g)} polygons")
            return g
        except Exception as e:
            log(f"  retry {k} {q}: {type(e).__name__} {str(e)[:150]}"); time.sleep(20 * (k + 1))
    raise RuntimeError(f"{tile} {q} failed")


def osm_parts(d):
    """Same grouping as 04_labels.load_osm()."""
    col = lambda g, c: g[c] if c in g.columns else pd.Series(index=g.index, dtype=object)
    lu, am, b = d["landuse"], d["amenity"], d["building"]
    parts = {"res": [lu[col(lu, "landuse").isin(L.RES_LANDUSE)], b[col(b, "building").isin(L.RES_BUILDING)]],
             "nonres": [lu[col(lu, "landuse").isin(L.NONRES_LANDUSE)], am[col(am, "amenity").isin(L.NONRES_AMENITY)],
                        d["office"], d["shopmall"], b[col(b, "building").isin(L.NONRES_BUILDING)]],
             "open": [lu[col(lu, "landuse").isin(L.OPEN_LANDUSE)]],
             "forest": [lu[col(lu, "landuse").isin(L.FOREST_LANDUSE)]]}
    return {k: gpd.GeoDataFrame(pd.concat([x[["geometry"]] for x in v]), crs=4326).to_crs(UTM) for k, v in parts.items()}


def build_lab(osm, prod, tr, bb, excl):
    """Exact rules of 04_labels.main()."""
    dw, wc, jrc, ghsc = prod
    shp = (400, 400)

    def paint(g):
        g = g[g.intersects(bb)]
        if not len(g):
            return np.zeros(shp, bool)
        return rasterize(((geom, 1) for geom in g.geometry), shp, transform=tr, dtype="uint8").astype(bool)

    res, nonres, o_open, o_forest = (paint(osm[k]) for k in ("res", "nonres", "open", "forest"))
    built_use = res | nonres
    lab = np.zeros(shp, np.uint8)
    ghs_built = (ghsc >= 11) & (ghsc <= 25)
    open_prod = np.isin(wc, [20, 30, 40, 60]) & np.isin(dw, [2, 4, 5, 7]) & ~ghs_built
    lab[(o_open | open_prod) & ~built_use] = 5
    lab[(o_forest | ((wc == 10) & (dw == 1))) & ~built_use] = 4
    lab[((jrc >= 80).astype(int) + (wc == 80) + (dw == 0)) >= 2] = 3
    lab[res] = 1
    lab[nonres] = 2
    lab[paint(excl)] = 0
    return lab, {k: float(paint(osm[k]).sum() * 100 / 1e6) for k in osm}


def main():
    tiles = json.loads((RAW / "feat_2023" / "tiles.json").read_text())
    val = gpd.read_file(LU / "validation_points.gpkg", layer="validation_pixels").to_crs(UTM)
    excl = gpd.GeoDataFrame(geometry=val.geometry.centroid.buffer(L.EXCLUDE_M), crs=UTM)
    samp = pd.concat([pd.read_parquet(f, columns=["tile", "row", "col", "label"])
                      for f in sorted((LU / "samples_parts").glob("*.parquet"))])
    rows = []
    for site, (lon, lat) in SITES.items():
        p = gpd.GeoSeries(gpd.points_from_xy([lon], [lat]), crs=4326).to_crs(UTM).iloc[0]
        k = f"x{int(p.x // 4000 * 4)}_y{int(p.y // 4000 * 4)}"
        minx, miny, maxx, maxy = tiles[k]
        bb = box(minx, miny, maxx, maxy)
        bb_ll = tuple(gpd.GeoSeries([bb], crs=UTM).to_crs(4326).total_bounds)
        log(f"{site}: tile {k}")
        with rasterio.open(RAW / "prod" / f"{k}.tif") as s:
            prod = [s.read(i) for i in (1, 2, 3, 4)]
        with rasterio.open(RAW / "lab" / f"{k}.tif") as s:
            stored = s.read(1)
        tr = from_origin(minx, maxy, 10, 10)
        labs, areas = {}, {}
        for tag, date in DATES.items():
            osm = osm_parts({q: fetch(k, bb_ll, q, date) for q in Q})
            labs[tag], areas[tag] = build_lab(osm, prod, tr, bb, excl)
        a, b = labs["2023"], labs["now"]
        t = pd.crosstab(pd.Series(a.ravel(), name="osm_2023").map(NAMES),
                        pd.Series(b.ravel(), name="osm_now").map(NAMES))
        t.to_csv(OUT / f"transitions_{site}.csv")
        s = samp[samp.tile == k]
        s23 = a[s.row.values, s.col.values]
        r = {"site": site, "tile": k,
             "now_vs_stored_lab_match_pct": round(100 * float((b == stored).mean()), 2),
             "labelled_px_2023": int((a > 0).sum()), "labelled_px_now": int((b > 0).sum()),
             "px_label_differs": int((a != b).sum()),
             "pct_of_labelled_differs": round(100 * float((a != b).sum() / max(1, ((a > 0) | (b > 0)).sum())), 1),
             "train_samples_in_tile": len(s),
             "train_samples_changed": int((s23 != s.label.values).sum()),
             "train_samples_dropped_in_2023": int((s23 == 0).sum())}
        for c in ("res", "nonres", "open", "forest"):
            r[f"{c}_km2_2023"] = round(areas["2023"][c], 3); r[f"{c}_km2_now"] = round(areas["now"][c], 3)
        rows.append(r); log(r)
        plot(site, k, a, b)
    pd.DataFrame(rows).to_csv(OUT / "summary.csv", index=False)
    log("\n" + pd.DataFrame(rows).T.to_string())


def plot(site, k, a, b):
    import matplotlib; matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import ListedColormap
    cm = ListedColormap(["#f0f0f0", "#e6550d", "#756bb1", "#3182bd", "#2ca02c", "#fee391"])
    ch = np.where(a == b, 0, np.where(a == 0, 1, np.where(b == 0, 2, 3)))
    fig, ax = plt.subplots(1, 3, figsize=(15, 5.4))
    for i, (img, ttl) in enumerate([(a, "labels from OSM mid-2023"), (b, "labels from OSM now")]):
        ax[i].imshow(img, cmap=cm, vmin=0, vmax=5, interpolation="nearest"); ax[i].set_title(ttl)
    ax[2].imshow(ch, cmap=ListedColormap(["#f0f0f0", "#d62728", "#1f77b4", "#000000"]), vmin=0, vmax=3,
                 interpolation="nearest")
    ax[2].set_title("red: labelled only now   blue: only 2023   black: class differs")
    for x in ax: x.set_xticks([]); x.set_yticks([])
    fig.suptitle(f"{site} ({k}, 4 x 4 km)   orange res, purple non-res, blue water, green forest, yellow open")
    fig.tight_layout(); fig.savefig(OUT / f"{site}.png", dpi=110); plt.close(fig)


if __name__ == "__main__":
    main()
