"""
"Sure" 20 m cells: 175 per class where every source agrees across the whole cell, for manual
verification in QGIS. NOT an accuracy test set (it is the easy cases by construction); use the
stratified random sets (02, 02b) for that. Good for training, sanity checks and examples.

A cell (2 x 2 pixels of the 10 m grid, corners at multiples of 20 m in EPSG:32644) qualifies
for class c when ALL 4 pixels satisfy the class rule below AND, in OSM as mapped on 2023-06-30,
the cell is >= 98% covered by class-c polygons and <= 1% by any other class's polygons
("confirms"). OSM rarely maps farmland, scrub or woodland in Hyderabad, so for forest and open
the set is topped up with cells where OSM 2023 has no polygon of any class ("silent": nothing
contradicts, but OSM does not confirm either). Column `osm2023` records which.

  1 residential   lab 1, DW built, WorldCover built, GHS-BUILT-C residential (11-15)
  2 non-res       lab 2, DW built, WorldCover built, and GHS non-res (21-25) or Global
                  Industrial Land industrial or WRI non-residential
  3 water         lab 3, DW water, WorldCover water, JRC occurrence >= 80
  4 forest        lab 4, DW trees, WorldCover tree
  5 other open    lab 5, DW grass/crops/shrub/bare, WorldCover shrub/grass/crop/bare, GHS not built
(lab = his training label tile: OSM ~2026 + land-cover agreement, see 04_labels.py)

OSM 2023 coverage comes from the ohsome history API (aggregate endpoint, per-cell polygons).
Cells within 400 m of either hand-label test set are excluded; cells are drawn round-robin over
4 km tiles, so the set spreads over HMDA.

Needs prod/, lab/ and feat_2023/tiles.json under data/raw/lu/ or LU_RAW.
Outputs (data/processed/lu/):
  consensus20_cells.gpkg  - pre-labelled 20 m squares; `proposed_class` = what the sources say,
                            `true_class` = your verified label (starts equal to proposed)
  consensus20_cells.kml   - same cells for Google Earth Pro
  consensus20_osm2023.csv - OSM 2023 coverage of every candidate cell checked
Usage: python 02c_consensus_cells_20m.py [n_per_class]
"""
import json, os, sqlite3, sys, time
from pathlib import Path
import numpy as np, pandas as pd, geopandas as gpd, rasterio, requests
from rasterio.features import rasterize
from rasterio.transform import from_origin
from scipy.spatial import cKDTree
from shapely.geometry import box
from lu_common import LU, LURAW, PROC, UTM, log
import importlib
L = importlib.import_module("04_labels")

N = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 175
OVERSAMPLE = 4                                   # candidates sent to the OSM 2023 check = OVERSAMPLE * N per class
SEED = 20261017
CELL, K = 20, 2
EXCL_M = 400
PER_TILE = {1: 8, 2: 8, 3: 60, 4: 8, 5: 8}      # candidates kept per 4 km tile; water sits in few big lakes
OSM_DATE = "2023-06-30"
RAW = Path(os.environ.get("LU_RAW", LURAW))
NAMES = {1: "residential", 2: "non-residential built", 3: "water", 4: "forest/trees", 5: "other open"}
inlist = lambda k, v: f"{k} in ({','.join(sorted(v))})"
OSM = {                                          # ohsome filters per class, polygons only
    1: f"landuse=residential or {inlist('building', L.RES_BUILDING)}",
    2: f"{inlist('landuse', L.NONRES_LANDUSE)} or {inlist('amenity', L.NONRES_AMENITY)} or office=* "
       f"or shop in (mall,supermarket,department_store,wholesale) or {inlist('building', L.NONRES_BUILDING)}",
    3: "natural=water or water=* or waterway=riverbank or landuse in (reservoir,basin)",
    4: "landuse=forest or natural=wood",
    5: f"{inlist('landuse', L.OPEN_LANDUSE)} or natural in (grassland,scrub,heath,bare_rock,sand)",
}


def blocks(a):
    n = a.shape[0] // K
    return a.reshape(n, K, n, K).transpose(0, 2, 1, 3).reshape(n, n, K * K)


def class_masks(lab, p):
    dw, wc, jrc, ghsc, wri, ind = (blocks(x) for x in p)
    lb = blocks(lab)
    every = lambda m: m.all(-1)
    built = (dw == 6) & (wc == 50)
    return {
        1: every((lb == 1) & built & (ghsc >= 11) & (ghsc <= 15)),
        2: every((lb == 2) & built & (((ghsc >= 21) & (ghsc <= 25)) | (ind == 1) | (wri == 1))),
        3: every((lb == 3) & (dw == 0) & (wc == 80) & (jrc >= 80) & (jrc <= 100)),
        4: every((lb == 4) & (dw == 1) & (wc == 10)),
        5: every((lb == 5) & np.isin(dw, [2, 4, 5, 7]) & np.isin(wc, [20, 30, 40, 60]) & ~((ghsc >= 11) & (ghsc <= 25))),
    }


def candidates():
    tiles = json.loads((RAW / "feat_2023" / "tiles.json").read_text())
    aoi = gpd.read_file(PROC / "aoi_utm44n.gpkg").to_crs(UTM).geometry.iloc[0]
    tests = [gpd.read_file(LU / "validation_points.gpkg", layer="validation_pixels")]
    if (LU / "validation20_cells.gpkg").exists():
        tests.append(gpd.read_file(LU / "validation20_cells.gpkg", layer="validation_pixels"))
    c = pd.concat([t.to_crs(UTM).geometry.centroid for t in tests])
    tree = cKDTree(np.c_[c.x, c.y])
    n = 4000 // CELL
    off = (np.arange(n) + 0.5) * CELL
    rng = np.random.default_rng(SEED)
    rows = []
    for k, (minx, miny, maxx, maxy) in tiles.items():
        with rasterio.open(RAW / "prod" / f"{k}.tif") as s:
            p = s.read()
        with rasterio.open(RAW / "lab" / f"{k}.tif") as s:
            lab = s.read(1)
        inside = rasterize([(aoi.intersection(box(minx, miny, maxx, maxy)), 1)], (n, n),
                           transform=from_origin(minx, maxy, CELL, CELL), dtype="uint8").astype(bool)
        cx, cy = np.meshgrid(minx + off, maxy - off)
        far = tree.query(np.c_[cx.ravel(), cy.ravel()], distance_upper_bound=EXCL_M)[0].reshape(n, n) == np.inf
        for cls, m in class_masks(lab, p).items():
            r, cc = np.nonzero(m & inside & far)
            if len(r):
                pick = rng.permutation(len(r))[:PER_TILE[cls]]          # a few per tile; trimmed later
                for i in pick:
                    rows.append({"cls": cls, "tile": k, "x0": minx + cc[i] * CELL, "y1": maxy - r[i] * CELL,
                                 "n_tile": len(r)})
    d = pd.DataFrame(rows)
    log("candidate cells per class (after per-tile cap):\n" + d.cls.value_counts().sort_index().to_string())
    log("tiles with at least one candidate:\n" + d.groupby("cls").tile.nunique().to_string())
    return d


def spread(d, n, rng):
    """Random cells, round-robin over tiles (every tile's 1st cell, then every tile's 2nd, ...),
    so the set is as spread out as the candidates allow."""
    d = d.sample(frac=1, random_state=int(rng.integers(1 << 31)))
    d = d.assign(rank=d.groupby("tile").cumcount())
    return d.sort_values("rank", kind="stable").head(n).drop(columns="rank")


def osm_cover(cells, cls_filter):
    """Area (m2) of OSM-2023 polygons matching `cls_filter` inside each cell, via ohsome."""
    out = {}
    for i in range(0, len(cells), 300):
        part = cells.iloc[i:i + 300]
        fc = {"type": "FeatureCollection", "features": [
            {"type": "Feature", "id": str(cid), "properties": {"id": str(cid)}, "geometry": g.__geo_interface__}
            for cid, g in zip(part.cid, part.geometry.to_crs(4326))]}
        data = {"bpolys": json.dumps(fc), "time": OSM_DATE, "filter": f"({cls_filter}) and geometry:polygon"}
        for k in range(6):
            try:
                r = requests.post("https://api.ohsome.org/v1/elements/area/groupBy/boundary", data=data, timeout=(15, 900))
                r.raise_for_status(); break
            except Exception as e:
                log(f"  ohsome retry {k}: {type(e).__name__} {str(e)[:120]}"); time.sleep(30 * (k + 1))
        else:
            raise RuntimeError("ohsome failed")
        for g in r.json()["groupByResult"]:
            out[g["groupByObject"]] = g["result"][0]["value"]
    return cells.cid.astype(str).map(out).fillna(0).values


def main():
    rng = np.random.default_rng(SEED)
    d = candidates()
    pool = pd.concat([spread(d[d.cls == c], OVERSAMPLE * N, rng) for c in NAMES]).reset_index(drop=True)
    pool["cid"] = np.arange(len(pool))
    pool = gpd.GeoDataFrame(pool, geometry=[box(x, y - CELL, x + CELL, y) for x, y in zip(pool.x0, pool.y1)], crs=UTM)
    log(f"checking OSM {OSM_DATE} coverage for {len(pool)} candidate cells")
    for c, f in OSM.items():
        pool[f"osm23_{c}"] = np.minimum(osm_cover(pool, f) / (CELL * CELL), 9.99).round(3)
        log(f"  OSM class {c} done")
    cov = pool[[f"osm23_{c}" for c in NAMES]].values
    own = cov[np.arange(len(pool)), pool.cls.values - 1]
    other = np.where(np.eye(5, dtype=bool)[pool.cls.values - 1], 0, cov).max(1)
    silent = cov.max(1) == 0
    pool["osm2023"] = np.where((own >= 0.98) & (other <= 0.01), "confirms",
                               np.where(silent & pool.cls.isin([4, 5]), "silent", "rejected"))
    pool.drop(columns="geometry").to_csv(LU / "consensus20_osm2023.csv", index=False)
    log("passed OSM 2023 check / checked:\n" + pd.crosstab(pool.cls, pool.osm2023).to_string())

    sel = []
    for c in NAMES:                              # OSM-confirmed cells first, then silent ones
        a = spread(pool[(pool.cls == c) & (pool.osm2023 == "confirms")], N, rng)
        b = spread(pool[(pool.cls == c) & (pool.osm2023 == "silent")], N - len(a), rng)
        sel += [a, b]
        if len(a) + len(b) < N:
            log(f"  class {c}: only {len(a) + len(b)} cells available")
    sel = pd.concat(sel)
    sel = sel.sample(frac=1, random_state=SEED).reset_index(drop=True)
    ll = sel.geometry.centroid.to_crs(4326)
    u = gpd.GeoDataFrame({"pid": np.arange(1, len(sel) + 1), "lon": ll.x.round(6), "lat": ll.y.round(6),
                          "proposed_class": sel.cls.astype(int), "true_class": sel.cls.astype(int),
                          "checked": 0, "confidence": pd.Series([None] * len(sel), dtype="Int64"),
                          "notes": "", "osm2023": sel.osm2023, "tile": sel.tile}, geometry=sel.geometry.values, crs=UTM)
    fp = LU / "consensus20_cells.gpkg"
    fp.unlink(missing_ok=True)
    u.to_file(fp, layer="consensus_cells", driver="GPKG")
    add_style(fp)
    u.to_crs(4326).assign(Name=u.pid.astype(str) + " " + u.proposed_class.map(NAMES))[["Name", "geometry"]] \
     .to_file(LU / "consensus20_cells.kml", driver="KML")
    log(f"wrote {fp}\n" + u.proposed_class.map(NAMES).value_counts().to_string())


QML = """<!DOCTYPE qgis PUBLIC 'http://mrcc.com/qgis.dtd' 'SYSTEM'>
<qgis version="3.44" styleCategories="Fields|Forms|Symbology|Labeling">
 <renderer-v2 type="categorizedSymbol" attr="true_class" symbollevels="0" enableorderby="0">
  <categories>
   <category value="1" symbol="0" label="1 residential" render="true"/>
   <category value="2" symbol="1" label="2 non-residential built" render="true"/>
   <category value="3" symbol="2" label="3 water" render="true"/>
   <category value="4" symbol="3" label="4 forest/trees" render="true"/>
   <category value="5" symbol="4" label="5 other open" render="true"/>
   <category value="0" symbol="5" label="0 reject (not a clean cell)" render="true"/>
  </categories>
  <symbols>%SYMBOLS%</symbols>
 </renderer-v2>
 <labeling type="simple"><settings calloutType="simple"><text-style fieldName="pid" fontSize="9" textColor="255,255,0,255"><text-buffer bufferDraw="1" bufferSize="0.8" bufferColor="0,0,0,255"/></text-style><placement placement="1" dist="1.5"/></settings></labeling>
 <fieldConfiguration>
  <field name="true_class"><editWidget type="ValueMap"><config><Option type="Map"><Option type="List" name="map">
   <Option type="Map"><Option type="QString" name="1 residential" value="1"/></Option>
   <Option type="Map"><Option type="QString" name="2 non-residential built" value="2"/></Option>
   <Option type="Map"><Option type="QString" name="3 water" value="3"/></Option>
   <Option type="Map"><Option type="QString" name="4 forest/trees" value="4"/></Option>
   <Option type="Map"><Option type="QString" name="5 other open" value="5"/></Option>
   <Option type="Map"><Option type="QString" name="0 reject (mixed / unclear)" value="0"/></Option>
  </Option></Option></config></editWidget></field>
  <field name="proposed_class"><editWidget type="ValueMap"><config><Option type="Map"><Option type="List" name="map">
   <Option type="Map"><Option type="QString" name="1 residential" value="1"/></Option>
   <Option type="Map"><Option type="QString" name="2 non-residential built" value="2"/></Option>
   <Option type="Map"><Option type="QString" name="3 water" value="3"/></Option>
   <Option type="Map"><Option type="QString" name="4 forest/trees" value="4"/></Option>
   <Option type="Map"><Option type="QString" name="5 other open" value="5"/></Option>
  </Option></Option></config></editWidget></field>
  <field name="checked"><editWidget type="CheckBox"><config><Option type="Map"><Option type="QString" name="CheckedState" value="1"/><Option type="QString" name="UncheckedState" value="0"/></Option></config></editWidget></field>
  <field name="confidence"><editWidget type="ValueMap"><config><Option type="Map"><Option type="List" name="map">
   <Option type="Map"><Option type="QString" name="1 sure" value="1"/></Option>
   <Option type="Map"><Option type="QString" name="2 probably" value="2"/></Option>
   <Option type="Map"><Option type="QString" name="3 guess" value="3"/></Option>
  </Option></Option></config></editWidget></field>
 </fieldConfiguration>
 <editable><field name="pid" editable="0"/><field name="lon" editable="0"/><field name="lat" editable="0"/><field name="proposed_class" editable="0"/><field name="osm2023" editable="0"/><field name="tile" editable="0"/></editable>
</qgis>"""


def add_style(fp):
    """Default QGIS style inside the GeoPackage: dropdowns, outline squares coloured by label."""
    cols = ["230,85,13", "117,107,177", "49,130,189", "44,160,44", "255,237,111", "255,0,255"]
    sym = "".join(
        f'<symbol type="fill" name="{k}" alpha="1"><layer class="SimpleFill"><Option type="Map">'
        f'<Option type="QString" name="style" value="no"/>'
        f'<Option type="QString" name="outline_color" value="{c},255"/>'
        f'<Option type="QString" name="outline_width" value="0.8"/></Option></layer></symbol>'
        for k, c in enumerate(cols))
    con = sqlite3.connect(fp)
    con.execute("""CREATE TABLE IF NOT EXISTS layer_styles (id INTEGER PRIMARY KEY AUTOINCREMENT,
        f_table_catalog TEXT, f_table_schema TEXT, f_table_name TEXT, f_geometry_column TEXT,
        styleName TEXT, styleQML TEXT, styleSLD TEXT, useAsDefault BOOLEAN, description TEXT,
        owner TEXT, ui TEXT, update_time DATETIME DEFAULT CURRENT_TIMESTAMP)""")
    con.execute("INSERT INTO layer_styles (f_table_catalog,f_table_schema,f_table_name,f_geometry_column,"
                "styleName,styleQML,styleSLD,useAsDefault,description,owner) VALUES "
                "('','','consensus_cells','geom','verify',?,'',1,'verification form','')",
                (QML.replace("%SYMBOLS%", sym),))
    con.commit(); con.close()


if __name__ == "__main__":
    main()
