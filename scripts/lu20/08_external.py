"""
External validation of the 20 m maps against independent datasets (overnight job).

Stages (each cached; run all with no argument, or name stages):
  ee        Earth Engine products on our 20 m grid (16 chunks each, <= 2 parallel requests):
            Esri/Impact Observatory 10 m annual LULC 2017/2020/2023 (built, water, trees fractions),
            WSF 2019 (built fraction), JRC yearly water 2017/2020, ETH canopy height 2020 (>= 5 m
            fraction), Local Climate Zones (Demuzere 2022, LCZ_Filter)
  ms        Microsoft ML building footprints for HMDA (direct download) -> building cover per cell
  overture  Overture Maps Places for the HMDA bounding box (overturemaps CLI, GeoParquet)
  analyse   all comparisons -> outputs/lu20/external/RESULTS_external.md

Independence: our model uses Sentinel-2, Open Buildings, VIIRS; labels use OSM, WorldCover 2021,
Dynamic World 2023, JRC occurrence, GHS-BUILT-C. Esri IO, WSF, Microsoft buildings, ETH canopy, LCZ
and Overture Places are independent of the labels (Esri, ETH and LCZ also use Sentinel-2 imagery).
Map-to-map comparisons are intercomparison, not accuracy (CEOS 2025); accuracy comes only from the
hand-labelled sample, on which every product is scored the same way.
"""
import sys, io, os, json, time, gzip, math, subprocess, importlib.util as iu
from concurrent.futures import ThreadPoolExecutor
import numpy as np, pandas as pd, geopandas as gpd, rasterio, requests
from rasterio.io import MemoryFile
from pyproj import Transformer
from common20 import *

E = W20 / "ext"; E.mkdir(exist_ok=True)
R = OUT / "external"; R.mkdir(exist_ok=True)
META = json.loads((W20 / "grid_2023" / "meta.json").read_text())
NY, NX = META["ny"], META["nx"]
YRS = [2017, 2020, 2023]
EE_PROJECT = os.environ.get("EE_PROJECT", "exploringclass")


# --------------------------------------------------------------------------- Earth Engine stage
def ee_images():
    import ee
    ee.Initialize(project=EE_PROJECT)
    x0, y1 = META["minx"], META["maxy"]
    region = ee.Geometry.Rectangle([x0, y1 - NY * CELL, x0 + NX * CELL, y1], "EPSG:32644", False)
    at10 = lambda im: im.reproject("EPSG:32644", None, 10)                 # fix the input grid before reduceResolution
    frac = lambda m: m.toFloat().reduceResolution(ee.Reducer.mean(), False, 64).multiply(100).round().toUint8()
    out = {}
    for y in YRS:
        m = at10(ee.ImageCollection("projects/sat-io/open-datasets/landcover/ESRI_Global-LULC_10m_TS")
                 .filterDate(f"{y}-01-01", f"{y}-12-31").filterBounds(region).mosaic())
        out[f"esri_{y}"] = (frac(m.eq(7)).rename("built").addBands(frac(m.eq(1)).rename("water"))
                            .addBands(frac(m.eq(2)).rename("trees")))
    w = at10(ee.ImageCollection("projects/sat-io/open-datasets/WSF/WSF_2019").filterBounds(region).mosaic())
    out["wsf_2019"] = frac(w.eq(255)).rename("built")
    for y in (2017, 2020):
        j = ee.ImageCollection("JRC/GSW1_4/YearlyHistory").filter(ee.Filter.eq("year", y)).first().select("waterClass")
        out[f"jrc_{y}"] = j.gte(2).multiply(100).toUint8().rename("water")
    c = at10(ee.Image("users/nlang/ETH_GlobalCanopyHeight_2020_10m_v1"))
    out["eth_2020"] = frac(c.gte(5).And(c.lt(255))).rename("trees")
    out["lcz"] = ee.ImageCollection("RUB/RUBCLIM/LCZ/global_lcz_map/latest").mosaic().select("LCZ_Filter").toUint8()
    return out


def chunks(n=4):
    cw, ch = NX // n, NY // n
    return [(i * cw, j * ch, cw if i < n - 1 else NX - i * cw, ch if j < n - 1 else NY - j * ch)
            for j in range(n) for i in range(n)]


def fetch_chunk(img, c0, r0, w, h):
    t = [CELL, 0, META["minx"] + c0 * CELL, 0, -CELL, META["maxy"] - r0 * CELL]
    for k in range(5):
        try:
            url = img.getDownloadURL({"crs": "EPSG:32644", "crs_transform": t, "dimensions": f"{w}x{h}", "format": "GEO_TIFF"})
            r = requests.get(url, timeout=900); r.raise_for_status()
            with MemoryFile(r.content) as mf, mf.open() as s:
                return s.read()
        except Exception as e:
            log(f"    retry {k}: {str(e)[:120]}"); time.sleep(30 * (k + 1))
    raise RuntimeError("chunk failed")


def stage_ee():
    imgs = ee_images()
    only = os.environ.get("LU20_EE_ONLY")                 # e.g. "lcz" to fetch one product (testing)
    for name, img in imgs.items():
        if (E / f"{name}.npz").exists() or (only and name != only):
            continue
        t = time.time(); arr = None
        with ThreadPoolExecutor(2) as ex:
            futs = {ex.submit(fetch_chunk, img, *ch): ch for ch in chunks()}
            for f, (c0, r0, w, h) in futs.items():
                a = f.result()
                if arr is None:
                    arr = np.zeros((a.shape[0], NY, NX), np.uint8)
                arr[:, r0:r0 + h, c0:c0 + w] = a
        bands = img.bandNames().getInfo()
        np.savez_compressed(E / f"{name}.npz", **{b: arr[i] for i, b in enumerate(bands)})
        log(f"  {name}: {bands} in {(time.time() - t) / 60:.1f} min")


# --------------------------------------------------------------------------- Microsoft buildings
def quadkey(tx, ty, z):
    return "".join(str(((tx >> (i - 1)) & 1) + 2 * ((ty >> (i - 1)) & 1)) for i in range(z, 0, -1))


def tile_xy(lon, lat, z):
    n = 2 ** z; lat_r = math.radians(lat)
    return int((lon + 180) / 360 * n), int((1 - math.asinh(math.tan(lat_r)) / math.pi) / 2 * n)


def stage_ms():
    out = E / "ms_cover.npy"
    if out.exists():
        return
    import shapely
    links = pd.read_csv("https://minedbuildings.z5.web.core.windows.net/global-buildings/dataset-links.csv", dtype={"QuadKey": str})
    links = links[links.Location == "India"]
    to_ll = Transformer.from_crs(32644, 4326, always_xy=True)
    lon0, lat1 = to_ll.transform(META["minx"], META["maxy"]); lon1, lat0 = to_ll.transform(META["minx"] + NX * CELL, META["maxy"] - NY * CELL)
    z = len(links.QuadKey.iloc[0])
    (xa, ya), (xb, yb) = tile_xy(lon0, lat1, z), tile_xy(lon1, lat0, z)
    qks = {quadkey(x, y, z) for x in range(xa, xb + 1) for y in range(ya, yb + 1)}
    sel = links[links.QuadKey.isin(qks)]
    if sel.empty:
        raise RuntimeError(f"no Microsoft files for quadkeys {sorted(qks)}")
    log(f"  Microsoft buildings: {len(sel)} files for quadkeys {sorted(qks)}")
    cover = np.zeros((NY, NX), np.float64)
    to_utm = Transformer.from_crs(4326, 32644, always_xy=True)
    D = RAW.parent / "ms_buildings"; D.mkdir(exist_ok=True)
    nb = 0
    for _, row in sel.iterrows():
        fp = D / f"{row.QuadKey}_{os.path.basename(row.Url)}"
        if not fp.exists():
            fp.write_bytes(requests.get(row.Url, timeout=1800).content)
        with gzip.open(fp, "rt", encoding="utf-8") as f:
            lines = [json.loads(l)["geometry"] for l in f if l.strip()]
        g = shapely.from_geojson([json.dumps(x) for x in lines])
        c = shapely.centroid(g); lon, lat = shapely.get_x(c), shapely.get_y(c)
        area = shapely.area(g) * (111320.0 ** 2) * np.cos(np.radians(lat))          # m2, small polygons
        x, y = to_utm.transform(lon, lat)
        r = ((META["maxy"] - y) // CELL).astype(int); cc = ((x - META["minx"]) // CELL).astype(int)
        ok = (r >= 0) & (r < NY) & (cc >= 0) & (cc < NX)
        np.add.at(cover, (r[ok], cc[ok]), area[ok])
        nb += int(ok.sum()); log(f"    {row.QuadKey}: {ok.sum():,} buildings in the grid")
    np.save(out, np.minimum(cover / (CELL * CELL), 1).astype(np.float32))
    log(f"  Microsoft buildings: {nb:,} buildings; cover saved")


# --------------------------------------------------------------------------- Overture places
def stage_overture():
    out = RAW.parent / "overture" / "places_hmda.parquet"
    if out.exists():
        return
    out.parent.mkdir(exist_ok=True)
    to_ll = Transformer.from_crs(32644, 4326, always_xy=True)
    lon0, lat1 = to_ll.transform(META["minx"], META["maxy"]); lon1, lat0 = to_ll.transform(META["minx"] + NX * CELL, META["maxy"] - NY * CELL)
    cmd = [sys.executable, "-m", "overturemaps", "download", f"--bbox={lon0:.4f},{lat0:.4f},{lon1:.4f},{lat1:.4f}",
           "-f", "geoparquet", "--type=place", "-o", str(out)]
    log("  " + " ".join(cmd))
    subprocess.run(cmd, check=True)
    log(f"  Overture places: {out.stat().st_size / 1e6:.1f} MB")


# --------------------------------------------------------------------------- analysis helpers
def load_map(y, kind="year"):
    with rasterio.open(OUT / "maps" / f"landuse_{y}_20m_{kind}.tif") as s:
        return s.read(1)


def ext(name):
    return dict(np.load(E / f"{name}.npz"))


def binstats(o, r, m):
    o, r = o[m], r[m]; n = o.size
    tp = np.sum(o & r); fp = np.sum(o & ~r); fn = np.sum(~o & r)
    return {"cells": n, "share_ours": o.mean(), "share_ref": r.mean(), "agreement": 1 - (fp + fn) / n,
            "F1_vs_ref": 2 * tp / max(2 * tp + fp + fn, 1),
            "quantity_dis": abs(fp - fn) / n, "allocation_dis": 2 * min(fp, fn) / n}


def zone_sum(a, k=50):
    ny, nx = a.shape[0] // k, a.shape[1] // k
    return a[:ny * k, :nx * k].reshape(ny, k, nx, k).sum((1, 3), dtype=np.float64)


def spearman(a, b):
    return pd.Series(np.asarray(a)).rank().corr(pd.Series(np.asarray(b)).rank())


def zone_corr(a, b, inside, extra=None):
    za, zb, zi = zone_sum(a.astype(np.float32)), zone_sum(b.astype(np.float32)), zone_sum(inside.astype(np.float32)) / 2500
    m = zi >= 0.9
    if extra is not None:
        m &= extra
    return spearman(za[m], zb[m]), int(m.sum())


def md(df, nd=3):
    df = df.copy()
    for c in df.columns:
        if df[c].dtype.kind == "f":
            df[c] = df[c].map(lambda v: "" if pd.isna(v) else f"{v:.{nd}f}")
    return ("| " + " | ".join(map(str, df.columns)) + " |\n|" + "---|" * len(df.columns) + "\n" +
            "\n".join("| " + " | ".join(map(str, r)) + " |" for r in df.values))


# --------------------------------------------------------------------------- analyses
def a_handlabels():
    """Same hand-labelled points, every map scored with the stratified (Stehman 2014) estimator."""
    s = iu.spec_from_file_location("ev", Path(__file__).parent / "05_eval.py"); ev = iu.module_from_spec(s); s.loader.exec_module(ev)
    import features20 as FX
    v = ev.hand_labels(FX.open_grid(2023))
    v = v[(v.confidence.fillna(3) <= 2).values].reset_index(drop=True)
    W = pd.read_csv(LUP / "validation_strata.csv", index_col=0)["weight"].to_dict()
    flat = v.flat.values; r, c = flat // NX, flat % NX
    to4 = {1: 1, 2: 1, 3: 2, 4: 3, 5: 4}                                 # built, water, trees, open
    ref = v.true_class.map(to4).values; st = v.stratum.values
    ours = pd.Series(load_map(2023)[r, c]).map(to4).fillna(4).astype(int).values
    es = ext("esri_2023"); bw, ww, tw = es["built"][r, c], es["water"][r, c], es["trees"][r, c]
    esri = np.argmax(np.stack([bw, ww, tw, 100 - bw - ww - tw]), 0) + 1
    wsf = np.where(ext("wsf_2019")["built"][r, c] >= 50, 1, 4)
    # Dynamic World 2023 and WorldCover 2021 at the 10 m pixel (prod tiles, as in 07_eval_handlabels)
    s2 = iu.spec_from_file_location("eh", ROOT / "scripts" / "lu" / "07_eval_handlabels.py"); eh = iu.module_from_spec(s2)
    sys.path.insert(0, str(ROOT / "scripts" / "lu")); s2.loader.exec_module(eh)
    x, y = Transformer.from_crs(4326, 32644, always_xy=True).transform(v.lon.values, v.lat.values)
    dw = pd.Series(eh.read_at("prod", 1, x, y)).map({0: 2, 1: 3, 2: 4, 3: 4, 4: 4, 5: 4, 6: 1, 7: 4, 8: 4}).fillna(4).astype(int).values
    wc = pd.Series(eh.read_at("prod", 2, x, y)).map({10: 3, 20: 4, 30: 4, 40: 4, 50: 1, 60: 4, 70: 4, 80: 2, 90: 4, 95: 3, 100: 4}).fillna(4).astype(int).values
    preds = {"ours 2023 (20 m)": ours, "Esri IO 2023": esri, "Dynamic World 2023": dw, "WorldCover 2021": wc}

    def score(ref_, p, st_, cls):
        P = np.zeros((4, 4))
        for h, w in W.items():
            m = st_ == h
            if m.sum():
                P += w * np.bincount((p[m] - 1) * 4 + (ref_[m] - 1), minlength=16).reshape(4, 4) / m.sum()
        ua = np.divide(np.diag(P), P.sum(1), out=np.zeros(4), where=P.sum(1) > 0)
        pa = np.divide(np.diag(P), P.sum(0), out=np.zeros(4), where=P.sum(0) > 0)
        f1 = np.divide(2 * ua * pa, ua + pa, out=np.zeros(4), where=(ua + pa) > 0)
        return f1[cls].mean(), f1, ua, pa
    rng = np.random.default_rng(0); idx = [np.nonzero(st == h)[0] for h in np.unique(st)]
    rows, prs = [], []
    for tag, cls, P_ in (("4-class (built / water / trees / open)", [0, 1, 2, 3], preds),
                         ("built vs not built", [0], {**preds, "WSF 2019": wsf})):
        P2 = {k: (np.where(p == 1, 1, 4) if tag.startswith("built") else p) for k, p in P_.items()}
        R2 = np.where(ref == 1, 1, 4) if tag.startswith("built") else ref
        boots = {k: [] for k in P2}
        for _ in range(1000):
            ii = np.concatenate([rng.choice(ix, len(ix)) for ix in idx])
            for k, p in P2.items():
                boots[k].append(score(R2[ii], p[ii], st[ii], cls)[0])
        for k, p in P2.items():
            m, f1, ua, pa = score(R2, p, st, cls)
            rows.append({"test": tag, "map": k, "score": m, "lo": np.percentile(boots[k], 2.5), "hi": np.percentile(boots[k], 97.5),
                         "UA_built": ua[0], "PA_built": pa[0]})
            if k != "ours 2023 (20 m)":
                d = np.array(boots["ours 2023 (20 m)"]) - np.array(boots[k])
                prs.append({"test": tag, "comparison": f"ours minus {k}", "diff": score(R2, P2["ours 2023 (20 m)"], st, cls)[0] - m,
                            "lo": np.percentile(d, 2.5), "hi": np.percentile(d, 97.5)})
    return pd.DataFrame(rows), pd.DataFrame(prs), len(v)


def a_builtup(maps, inside):
    rows, zrows = [], []
    ob = {y: np.nan_to_num(np.load(W20 / f"grid_{y}" / "mean.npy", mmap_mode="r")[BANDS.index("ob_cov")]) for y in YRS}
    for y in YRS:
        o = np.isin(maps[y], [1, 2]); es = ext(f"esri_{y}")["built"] >= 50
        rows.append({"year": y, "reference": "Esri IO built", **binstats(o, es, inside)})
        rho, n = zone_corr(o, es, inside); zrows.append({"year": y, "pair": "built share: ours vs Esri IO", "spearman": rho, "zones": n})
        rho, n = zone_corr(o, ob[y] > 0, inside); zrows.append({"year": y, "pair": "built share: ours vs Open Buildings (our input)", "spearman": rho, "zones": n})
    w = ext("wsf_2019")["built"] >= 50
    for y in (2017, 2020):
        rows.append({"year": y, "reference": "WSF 2019 built", **binstats(np.isin(maps[y], [1, 2]), w, inside)})
    rho, n = zone_corr(np.isin(maps[2020], [1, 2]), w, inside); zrows.append({"year": 2020, "pair": "built share: ours vs WSF 2019", "spearman": rho, "zones": n})
    if (E / "ms_cover.npy").exists():
        ms = np.load(E / "ms_cover.npy")
        # Microsoft has no files for the z9 tiles east of 78.75 E (1233102xx), so compare only west of it
        lon = Transformer.from_crs(32644, 4326, always_xy=True).transform(
            META["minx"] + (np.arange(NX) + 0.5) * CELL, np.full(NX, META["maxy"] - NY * CELL / 2))[0]
        msin = inside & (lon < 78.75)[None, :]
        rho, n = zone_corr(np.isin(maps[2023], [1, 2]), ms, msin); zrows.append({"year": 2023, "pair": "built share: ours vs Microsoft building cover (west of 78.75 E)", "spearman": rho, "zones": n})
        rho, n = zone_corr(ob[2023], ms, msin); zrows.append({"year": 2023, "pair": "Open Buildings cover (our input) vs Microsoft cover (west of 78.75 E)", "spearman": rho, "zones": n})
        rows.append({"year": 2023, "reference": "Microsoft building in cell (west of 78.75 E)", **binstats(np.isin(maps[2023], [1, 2]), ms > 0, msin)})
    # change 2017 -> 2023 at zone level
    zi = zone_sum(inside.astype(np.float32)) / 2500 >= 0.9
    d_ours = zone_sum(np.isin(maps[2023], [1, 2]).astype(np.float32)) - zone_sum(np.isin(maps[2017], [1, 2]).astype(np.float32))
    d_esri = zone_sum((ext("esri_2023")["built"] >= 50).astype(np.float32)) - zone_sum((ext("esri_2017")["built"] >= 50).astype(np.float32))
    d_ob = zone_sum(ob[2023].astype(np.float32)) - zone_sum(ob[2017].astype(np.float32))
    for pair, a, b in (("built change 2017-2023: ours vs Esri IO", d_ours, d_esri), ("built change: ours vs Open Buildings cover change", d_ours, d_ob),
                       ("built change: Esri IO vs Open Buildings cover change", d_esri, d_ob)):
        zrows.append({"year": "2017-2023", "pair": pair, "spearman": spearman(a[zi], b[zi]), "zones": int(zi.sum())})
    return pd.DataFrame(rows), pd.DataFrame(zrows)


def a_water_trees(maps, inside):
    rows = []
    for y in YRS:
        rows.append({"class": "water", "year": y, "reference": "Esri IO water", **binstats(maps[y] == 3, ext(f"esri_{y}")["water"] >= 50, inside)})
        if y in (2017, 2020):
            rows.append({"class": "water", "year": y, "reference": "JRC yearly water (seasonal + permanent)", **binstats(maps[y] == 3, ext(f"jrc_{y}")["water"] >= 50, inside)})
        rows.append({"class": "trees", "year": y, "reference": "Esri IO trees", **binstats(maps[y] == 4, ext(f"esri_{y}")["trees"] >= 50, inside)})
    rows.append({"class": "trees", "year": 2020, "reference": "ETH canopy height >= 5 m", **binstats(maps[2020] == 4, ext("eth_2020")["trees"] >= 50, inside)})
    return pd.DataFrame(rows)


LCZ = {1: "compact high-rise", 2: "compact mid-rise", 3: "compact low-rise", 4: "open high-rise", 5: "open mid-rise",
       6: "open low-rise", 7: "lightweight low-rise", 8: "large low-rise", 9: "sparsely built", 10: "heavy industry"}


def a_lcz(maps, inside):
    lcz = ext("lcz")["LCZ_Filter"]; rows = []
    for y in YRS:
        for cls, nm in ((1, "residential"), (2, "non-residential")):
            m = (maps[y] == cls) & inside
            v = lcz[m]; tot = len(v)
            rows.append({"year": y, "our class": nm, "cells": tot,
                         **{LCZ[k]: (v == k).mean() for k in LCZ}, "natural (LCZ A-G)": (v > 10).mean()})
    t = pd.DataFrame(rows)
    lift = []
    for y in YRS:
        a = t[(t.year == y) & (t["our class"] == "non-residential")].iloc[0]; b = t[(t.year == y) & (t["our class"] == "residential")].iloc[0]
        ind = lambda r: r["large low-rise"] + r["heavy industry"]
        lift.append({"year": y, "non-res in large low-rise + heavy industry": ind(a), "res in large low-rise + heavy industry": ind(b),
                     "ratio": ind(a) / max(ind(b), 1e-9)})
    return t, pd.DataFrame(lift)


GROUPS = [
    ("industrial", ["industr", "factory", "manufactur", "warehouse", "logistic", "wholesale", "plant", "machinery", "metal", "chemical"]),
    ("office / business", ["office", "professional", "business", "software", "information_technology", "it_service", "corporate",
                           "consult", "coworking", "real_estate", "financial", "bank", "insurance", "marketing", "engineering"]),
    ("institutional", ["school", "college", "university", "education", "hospital", "clinic", "health", "medical", "doctor", "dentist",
                       "pharmacy", "government", "police", "fire_station", "post_office", "court", "religious", "temple", "mosque",
                       "church", "place_of_worship", "community", "library"]),
    ("retail / food / services", ["shop", "store", "retail", "restaurant", "food", "cafe", "bakery", "bar", "market", "mall",
                                  "supermarket", "grocery", "salon", "beauty", "automotive", "car_", "repair", "hotel", "fitness", "gym"]),
    ("residential", ["apartment", "residential", "housing", "condominium", "home_owner", "gated_community"]),
]


def a_overture(maps, inside):
    p = RAW.parent / "overture" / "places_hmda.parquet"
    g = gpd.read_parquet(p)
    def cat(row):
        for c in ("basic_category", "taxonomy", "categories"):
            if c in row and row[c] is not None:
                v = row[c]
                if isinstance(v, dict):
                    v = " ".join(str(x) for x in v.values() if x is not None)
                return str(v).lower()
        return ""
    g["cat"] = [cat(r) for r in g.drop(columns="geometry").to_dict("records")]
    def grp(s):
        for name, keys in GROUPS:
            if any(k in s for k in keys):
                return name
        return "other / unknown"
    g["group"] = g.cat.map(grp)
    xy = g.to_crs(32644).geometry
    g["r"] = ((META["maxy"] - xy.y) // CELL).astype(int).values; g["c"] = ((xy.x - META["minx"]) // CELL).astype(int).values
    g = g[(g.r >= 0) & (g.r < NY) & (g.c >= 0) & (g.c < NX)].copy()
    m23 = maps[2023]; g = g[inside[g.r.values, g.c.values]].copy(); g["ours"] = m23[g.r.values, g.c.values]
    built = np.isin(m23, [1, 2]) & inside
    base = (m23[built] == 2).mean()                                       # non-res share of built cells
    # within-zone expectation: the non-res share of built cells in the POI's own 1 km zone, so the
    # comparison is not driven by POIs clustering in the dense core while non-res land sits outside it
    zb_n = zone_sum((m23 == 2).astype(np.float32)); zb_b = zone_sum(built.astype(np.float32))
    zr, zc = np.minimum(g.r.values // 50, zb_n.shape[0] - 1), np.minimum(g.c.values // 50, zb_n.shape[1] - 1)
    g["expect"] = np.where(zb_b[zr, zc] > 0, zb_n[zr, zc] / np.maximum(zb_b[zr, zc], 1), np.nan)
    x_utm = META["minx"] + (g.c.values + 0.5) * CELL; y_utm = META["maxy"] - (g.r.values + 0.5) * CELL
    g["block"] = np.floor(x_utm / 12000).astype(int) * 1000 + np.floor(y_utm / 12000).astype(int)
    rng = np.random.default_rng(0)
    rows = []
    for name in [n for n, _ in GROUPS] + ["other / unknown"]:
        s = g[g.group == name]; sb = s[s.ours.isin([1, 2]) & s.expect.notna()]
        obs = (sb.ours == 2).values.astype(float); exp_ = sb.expect.values
        lift_w = obs.sum() / exp_.sum() if len(sb) else np.nan
        ub = np.unique(sb.block.values); ix = {b: np.nonzero(sb.block.values == b)[0] for b in ub}; bl = []
        for _ in range(1000 if len(sb) else 0):
            ii = np.concatenate([ix[b] for b in rng.choice(ub, len(ub))])
            bl.append(obs[ii].sum() / exp_[ii].sum())
        rows.append({"POI group": name, "POIs": len(s), "in built cells": len(sb) / max(len(s), 1),
                     "in our non-res (of built)": obs.mean() if len(sb) else np.nan,
                     "lift vs HMDA-wide share": (obs.mean() / base) if len(sb) else np.nan,
                     "lift within own 1 km zone": lift_w,
                     "lo": np.percentile(bl, 2.5) if bl else np.nan, "hi": np.percentile(bl, 97.5) if bl else np.nan})
    t = pd.DataFrame(rows)
    # zone level, built-up zones: non-res-type POI counts vs our non-res and res area
    pois = np.zeros((NY, NX), np.float32)
    nr = g.group.isin(["industrial", "office / business", "institutional", "retail / food / services"]).values
    np.add.at(pois, (g.r.values[nr], g.c.values[nr]), 1)
    zb = zone_sum(built.astype(np.float32)) / 2500 >= 0.10
    z = {k: zone_corr(a, pois, inside, zb) for k, a in (("our non-res area", m23 == 2), ("our res area", m23 == 1), ("our built area", built))}
    zt = pd.DataFrame([{"pair": f"non-residential POIs vs {k}", "spearman": v[0], "built-up 1 km zones": v[1]} for k, v in z.items()])
    cols = [c for c in ("basic_category", "taxonomy", "categories") if c in g.columns]
    return t, zt, base, len(g), cols


# --------------------------------------------------------------------------- report
def stage_analyse():
    maps = {y: load_map(y) for y in YRS}
    inside = maps[2023] > 0
    rep = ["# External validation of the 20 m maps (internal)\n",
           "Auto-generated by `scripts/lu20/08_external.py`. Maps: year models, `outputs/lu20/maps/landuse_<y>_20m_year.tif`. "
           "Map-to-map comparisons are agreement between two imperfect maps (intercomparison), not accuracy; the accuracy "
           "statement is section 1, where every map is scored on the same hand-labelled points.\n"]
    try:
        hs, hp, n = a_handlabels()
        rep += [f"## 1. Same hand-labelled points (n = {n}, confidence <= 2), every map scored the same way\n",
                "Stratum-weighted (Stehman 2014) macro-F1; 95% stratified bootstrap. Land-cover maps cannot separate residential "
                "from non-residential, so the comparison is on built / water / trees / open, and on built vs not built.\n",
                md(hs) + "\n", "Paired differences (same bootstrap draws):\n", md(hp) + "\n"]
        hs.to_csv(R / "handlabels_products.csv", index=False); hp.to_csv(R / "handlabels_paired.csv", index=False)
    except Exception as e:
        rep += [f"## 1. Hand-labelled points: FAILED ({type(e).__name__}: {e})\n"]
    for title, fn in (("2. Built-up land (residential + non-residential) vs independent built-up maps", a_builtup),):
        try:
            b, z = fn(maps, inside)
            rep += [f"## {title}\n", "Cell level (inside HMDA). `quantity_dis` = disagreement in how much is built; "
                    "`allocation_dis` = disagreement in where (Pontius & Millones 2011).\n", md(b) + "\n",
                    "1 km zones (at least 90% inside HMDA), Spearman correlation:\n", md(z) + "\n"]
            b.to_csv(R / "builtup_cells.csv", index=False); z.to_csv(R / "builtup_zones.csv", index=False)
        except Exception as e:
            rep += [f"## {title}: FAILED ({type(e).__name__}: {e})\n"]
    try:
        wt = a_water_trees(maps, inside)
        rep += ["## 3. Water and trees\n", "Our forest class excludes trees inside compounds (those are labelled by use), so it "
                "is expected to be smaller than canopy maps.\n", md(wt) + "\n"]
        wt.to_csv(R / "water_trees.csv", index=False)
    except Exception as e:
        rep += [f"## 3. Water and trees: FAILED ({type(e).__name__}: {e})\n"]
    try:
        lt, lf = a_lcz(maps, inside)
        rep += ["## 4. Residential vs non-residential against Local Climate Zones (Demuzere et al. 2022, ~2018 inputs)\n",
                "Share of our residential and our non-residential cells in each built LCZ type. LCZ describes urban form, not use, "
                "but 'large low-rise' (warehouses, factories, malls) and 'heavy industry' are mostly non-residential.\n",
                md(lt) + "\n", md(lf) + "\n"]
        lt.to_csv(R / "lcz_crosstab.csv", index=False); lf.to_csv(R / "lcz_ratio.csv", index=False)
    except Exception as e:
        rep += [f"## 4. LCZ: FAILED ({type(e).__name__}: {e})\n"]
    try:
        ot, oz, base, n, cols = a_overture(maps, inside)
        rep += ["## 5. Residential vs non-residential against Overture Places (POIs, independent of OSM)\n",
                f"{n:,} places inside HMDA (category fields used: {cols}). Of our built cells in 2023, {base:.1%} are non-residential. "
                "Lift = how often POIs of a kind sit in our non-residential cells, divided by what is expected. "
                "'Within own 1 km zone' (the fair test) uses the non-residential share of built land in the POI's own zone as the "
                "expectation; the HMDA-wide version is confounded because POIs cluster in the dense core, where the map is mostly "
                "residential. A correct split gives lifts above 1 for non-residential POI kinds and below 1 for residential POIs. "
                "Overture is a 2026 snapshot scored against the 2023 map, and many Hyderabad shops are on residential plots, so "
                "lifts are conservative. Interval: 95%, bootstrap over 12 km blocks.\n", md(ot) + "\n",
                "1 km built-up zones (at least 10% built):\n", md(oz) + "\n"]
        ot.to_csv(R / "overture_groups.csv", index=False); oz.to_csv(R / "overture_zones.csv", index=False)
    except Exception as e:
        rep += [f"## 5. Overture: FAILED ({type(e).__name__}: {e})\n"]
    (R / "RESULTS_external.md").write_text("\n".join(rep), encoding="utf-8")
    log(f"wrote {R / 'RESULTS_external.md'}")


if __name__ == "__main__":
    stages = sys.argv[1:] or ["ee", "ms", "overture", "analyse"]
    for st in stages:
        t = time.time(); log(f"=== stage {st}")
        try:
            {"ee": stage_ee, "ms": stage_ms, "overture": stage_overture, "analyse": stage_analyse}[st]()
            log(f"=== stage {st} done in {(time.time() - t) / 60:.1f} min")
        except Exception as e:
            log(f"=== stage {st} FAILED: {type(e).__name__}: {e}")
