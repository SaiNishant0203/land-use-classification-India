"""
Stratified random validation sample for hand-labelling (TEST SET ONLY, never training).

Classes to label (land USE, 5 classes):
  1 residential | 2 non-residential built | 3 water | 4 forest/trees | 5 other open

Strata (independent of any model we will train or audit):
  S1 inside OSM non-residential polygons (industrial/commercial/retail/institutional)
  S2 Dynamic World 2023 'built' elsewhere        <- most res/non-res confusion lives here
  S3 DW water   S4 DW trees   S5 everything else (crops, grass, bare, shrub, flooded veg)

Each point carries its stratum area weight so accuracy/area can be estimated without bias
(Olofsson et al. 2014, "Good practices for estimating area and assessing accuracy").

Outputs (data/processed/lu/):
  validation_points.gpkg  - 10 m pixel squares, `true_class` dropdown when opened in QGIS
  validation_points.kml   - same points for Google Earth Pro (use the 2023 historical imagery)
  validation_key.csv      - pid -> stratum and weight (kept apart so labelling stays blind)
  validation_strata.csv   - stratum pixel counts and weights
"""
import glob, sqlite3
import numpy as np, pandas as pd, geopandas as gpd
from shapely.geometry import box
from lu_common import ee_init, LU, PROC, UTM, log

N_PER_STRATUM = {1: 70, 2: 130, 3: 30, 4: 35, 5: 60}          # 325 points
SEED = 20260919
YEAR = 2023
NONRES_LANDUSE = {"industrial", "commercial", "retail", "education", "civic", "religious"}
NONRES_AMENITY = {"school", "college", "university", "hospital", "townhall", "police",
                  "fire_station", "courthouse", "bus_station", "marketplace", "prison",
                  "research_institute", "library", "community_centre"}


def osm_nonres():
    lu = pd.concat([gpd.read_file(f) for f in glob.glob(str(PROC / "osm_cache/landuse_tiles/*.gpkg"))])
    lu = lu[lu.landuse.isin(NONRES_LANDUSE)]
    am = [gpd.read_file(f) for f in glob.glob(str(LU / "osm_extra_tiles/amenity_*.gpkg"))]
    am = pd.concat([a for a in am if len(a)])
    am = am[am.amenity.isin(NONRES_AMENITY)]
    g = gpd.GeoDataFrame(pd.concat([lu[["geometry"]], am[["geometry"]]]), crs=4326)
    g = g[g.geom_type.isin(["Polygon", "MultiPolygon"])].to_crs(UTM)
    g = g[g.area > 2000]                                   # >= 20 pixels; drops tiny shrine plots
    log(f"OSM non-res polygons: {len(g)}  ({g.area.sum()/1e6:.1f} km2)")
    return g.to_crs(4326)


def main():
    ee = ee_init()
    aoi = gpd.read_file(PROC / "aoi_utm44n.gpkg").to_crs(4326).geometry.iloc[0].simplify(0.002)
    region = ee.Geometry(aoi.__geo_interface__)
    nr = osm_nonres()
    nr_fc = ee.FeatureCollection([ee.Feature(ee.Geometry(gm.simplify(0.00005).__geo_interface__))
                                  for gm in nr.geometry])
    dw = (ee.ImageCollection("GOOGLE/DYNAMICWORLD/V1").filterBounds(region)
          .filterDate(f"{YEAR}-01-01", f"{YEAR}-12-31").select("label").mode())
    in_nr = ee.Image(0).paint(nr_fc, 1)
    strat = (ee.Image(5).where(dw.eq(1), 4).where(dw.eq(0), 3).where(dw.eq(6), 2)
             .where(in_nr.eq(1), 1).rename("stratum").toInt().clip(region)
             .reproject(f"EPSG:{UTM}", None, 10))

    # Equal-probability sampling within each stratum, done in 4x4 sub-regions so every EE
    # request stays small (restricted mode): stratum pixel counts per sub-region -> allocate
    # each stratum's n across sub-regions by multinomial draw proportional to area -> sample.
    minx, miny, maxx, maxy = aoi.bounds
    xs, ys = np.linspace(minx, maxx, 5), np.linspace(miny, maxy, 5)
    subs, counts = [], []
    for i in range(4):
        for j in range(4):
            sub = box(xs[i], ys[j], xs[i + 1], ys[j + 1]).intersection(aoi)
            if sub.is_empty:
                continue
            h = strat.reduceRegion(ee.Reducer.frequencyHistogram(), ee.Geometry(sub.__geo_interface__),
                                   30, maxPixels=1e10, tileScale=8).get("stratum").getInfo() or {}
            subs.append(sub); counts.append({int(k): v * 9 for k, v in h.items()})
            log(f"  sub-region {i},{j}: {counts[-1]}")
    cnt = pd.DataFrame(counts).fillna(0)[sorted(N_PER_STRATUM)]
    st = pd.DataFrame({"pixels_10m": cnt.sum().round().astype(int)})
    st["area_km2"] = st.pixels_10m * 100 / 1e6
    st["weight"] = st.pixels_10m / st.pixels_10m.sum()
    st["n_sample"] = [N_PER_STRATUM[k] for k in st.index]
    st.index.name = "stratum"
    st.to_csv(LU / "validation_strata.csv"); log("\n" + st.to_string())

    rng = np.random.default_rng(SEED)
    alloc = pd.DataFrame({s: rng.multinomial(n, cnt[s] / cnt[s].sum()) for s, n in N_PER_STRATUM.items()})
    pts = []
    for k, sub in enumerate(subs):
        need = {s: int(alloc.loc[k, s]) for s in N_PER_STRATUM if alloc.loc[k, s] > 0}
        if not need:
            continue
        fc = strat.stratifiedSample(numPoints=0, classBand="stratum",
                                    region=ee.Geometry(sub.__geo_interface__), scale=10,
                                    classValues=list(need), classPoints=list(need.values()),
                                    seed=SEED + k, geometries=True, tileScale=4)
        for f in fc.getInfo()["features"]:
            x, y = f["geometry"]["coordinates"]
            pts.append((f["properties"]["stratum"], x, y))
        log(f"  sampled sub-region {k}: {need}")
    v = gpd.GeoDataFrame(pd.DataFrame(pts, columns=["stratum", "lon", "lat"]),
                         geometry=gpd.points_from_xy([p[1] for p in pts], [p[2] for p in pts]), crs=4326)
    v = v.sample(frac=1, random_state=SEED).reset_index(drop=True)   # shuffle: labeller blind to stratum
    v.insert(0, "pid", np.arange(1, len(v) + 1))
    v["stratum_weight"] = v.stratum.map(st.weight)
    v["true_class"] = pd.Series([None] * len(v), dtype="Int64")
    v["confidence"] = pd.Series([None] * len(v), dtype="Int64")   # 1 sure / 2 probably / 3 guess
    v["is_road"] = pd.Series([None] * len(v), dtype="Int64")
    v["notes"] = ""
    # label the 10 m pixel, not a point: square on the UTM 10 m grid containing the point
    u = v.to_crs(UTM)
    x0 = np.floor(u.geometry.x / 10) * 10; y0 = np.floor(u.geometry.y / 10) * 10
    u["geometry"] = [box(a, b, a + 10, b + 10) for a, b in zip(x0, y0)]
    # stratum is kept out of the labelling file so the labeller stays blind to it
    u[["pid", "stratum", "stratum_weight", "lon", "lat"]].to_csv(LU / "validation_key.csv", index=False)
    fp = LU / "validation_points.gpkg"
    fp.unlink(missing_ok=True)
    u.drop(columns=["stratum", "stratum_weight"]).to_file(fp, layer="validation_pixels", driver="GPKG")
    add_qgis_style(fp)
    v.drop(columns=["true_class", "confidence", "is_road", "notes", "stratum_weight"]) \
     .assign(Name=v.pid.astype(str))[["Name", "geometry"]] \
     .to_file(LU / "validation_points.kml", driver="KML")
    log(f"wrote {fp} ({len(u)} pixels) and validation_points.kml")
    log(u.stratum.value_counts().sort_index().to_string())


QML = """<!DOCTYPE qgis PUBLIC 'http://mrcc.com/qgis.dtd' 'SYSTEM'>
<qgis version="3.34" styleCategories="Fields|Forms|Symbology|Labeling">
 <renderer-v2 type="categorizedSymbol" attr="true_class" symbollevels="0" enableorderby="0">
  <categories>
   <category value="" symbol="0" label="not labelled yet" render="true"/>
   <category value="1" symbol="1" label="1 residential" render="true"/>
   <category value="2" symbol="2" label="2 non-residential built" render="true"/>
   <category value="3" symbol="3" label="3 water" render="true"/>
   <category value="4" symbol="4" label="4 forest/trees" render="true"/>
   <category value="5" symbol="5" label="5 other open" render="true"/>
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
  </Option></Option></config></editWidget></field>
  <field name="confidence"><editWidget type="ValueMap"><config><Option type="Map"><Option type="List" name="map">
   <Option type="Map"><Option type="QString" name="1 sure" value="1"/></Option>
   <Option type="Map"><Option type="QString" name="2 probably" value="2"/></Option>
   <Option type="Map"><Option type="QString" name="3 guess" value="3"/></Option>
  </Option></Option></config></editWidget></field>
  <field name="is_road"><editWidget type="CheckBox"><config><Option type="Map"><Option type="QString" name="CheckedState" value="1"/><Option type="QString" name="UncheckedState" value="0"/></Option></config></editWidget></field>
 </fieldConfiguration>
 <editable><field name="pid" editable="0"/><field name="lon" editable="0"/><field name="lat" editable="0"/></editable>
</qgis>"""


def add_qgis_style(fp):
    """Store a default QGIS style inside the GeoPackage: dropdowns for the label fields,
    outline-only squares coloured by label, pid shown next to each pixel."""
    cols = ["255,0,255", "230,85,13", "49,130,189", "44,160,44", "35,139,69", "255,255,153"]
    sym = "".join(
        f'<symbol type="fill" name="{k}" alpha="1"><layer class="SimpleFill"><Option type="Map">'
        f'<Option type="QString" name="style" value="no"/>'
        f'<Option type="QString" name="outline_color" value="{c},255"/>'
        f'<Option type="QString" name="outline_width" value="0.8"/></Option></layer></symbol>'
        for k, c in enumerate(cols))
    qml = QML.replace("%SYMBOLS%", sym)
    con = sqlite3.connect(fp)
    con.execute("""CREATE TABLE IF NOT EXISTS layer_styles (id INTEGER PRIMARY KEY AUTOINCREMENT,
        f_table_catalog TEXT, f_table_schema TEXT, f_table_name TEXT, f_geometry_column TEXT,
        styleName TEXT, styleQML TEXT, styleSLD TEXT, useAsDefault BOOLEAN, description TEXT,
        owner TEXT, ui TEXT, update_time DATETIME DEFAULT CURRENT_TIMESTAMP)""")
    con.execute("INSERT INTO layer_styles (f_table_catalog,f_table_schema,f_table_name,f_geometry_column,"
                "styleName,styleQML,styleSLD,useAsDefault,description,owner) VALUES "
                "('','','validation_pixels','geom','labelling',?,'',1,'labelling form','')", (qml,))
    con.commit(); con.close()


if __name__ == "__main__":
    main()
