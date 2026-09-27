"""
EULUC-Globe 2024 (Chen, ..., Gong, Science Bulletin 2026; Zenodo 17476574, CC-BY-4.0):
parcel-level land use from Sentinel-1/2 + POI + multimodal deep learning.
Reads only HMDA parcels out of Asia.zip (bbox filter on the GPKG inside the zip) and burns them
onto our 10 m tiles.

EULUC index -> our class:
  0 residential -> 1
  1 commercial, 2 industrial, 4-7 transport facilities, 8 administrative, 9 educational,
    10 medical, 11 sport & cultural -> 2
  3 road -> 0 (no land-use call; same as roads elsewhere)
  12 park & greenspace -> 4        13 unused -> 5        14 agricultural -> 5        15 water -> 3
Areas without a parcel stay 0 (outside the product).
Output: data/raw/lu/euluc/<tile>.tif (uint8), data/processed/lu/euluc_hmda.gpkg
"""
import zipfile
import numpy as np, pandas as pd, geopandas as gpd, pyogrio, rasterio
from rasterio.features import rasterize
from rasterio.transform import from_origin
from shapely.geometry import box
from lu_common import LU, LURAW, PROC, UTM, log
import lu_features as F

ZIP = LURAW / "euluc" / "Asia.zip"
SRC = LURAW / "euluc" / "Asia.gpkg"     # extracted: querying inside the zip is far too slow
MAP = {0: 1, 1: 2, 2: 2, 3: 0, 4: 2, 5: 2, 6: 2, 7: 2, 8: 2, 9: 2, 10: 2, 11: 2, 12: 4, 13: 5, 14: 5, 15: 3}


def extract():
    fp = LU / "euluc_hmda.gpkg"
    if fp.exists():
        return gpd.read_file(fp)
    aoi = gpd.read_file(PROC / "aoi_utm44n.gpkg")
    if not SRC.exists():
        log(f"extracting {SRC.name} from {ZIP.name} ...")
        with zipfile.ZipFile(ZIP) as z:
            with z.open(SRC.name) as src, open(SRC, "wb") as dst:
                while (chunk := src.read(1 << 24)):
                    dst.write(chunk)
        log(f"extracted {SRC.stat().st_size / 1e9:.1f} GB")
    parts = []
    for lyr in pyogrio.list_layers(SRC)[:, 0]:
        crs = pyogrio.read_info(SRC, layer=lyr)["crs"]
        bb = tuple(aoi.to_crs(crs).total_bounds)
        g = pyogrio.read_dataframe(SRC, layer=lyr, bbox=bb)
        log(f"  {lyr} crs={crs} -> {len(g)} parcels; fields {list(g.columns)[:12]}")
        if len(g):
            parts.append(g.to_crs(UTM))
    if not parts:
        raise RuntimeError("no EULUC parcels over HMDA")
    g = gpd.GeoDataFrame(pd.concat(parts, ignore_index=True), crs=UTM)
    col = next(c for c in g.columns if c.lower() in ("index", "class", "label", "category", "code", "type", "euluc"))
    g["euluc"] = g[col].astype(int)
    g["ours"] = g["euluc"].map(MAP).fillna(0).astype(int)
    g = g[g.intersects(aoi.to_crs(UTM).geometry.iloc[0])]
    g[["euluc", "ours", "geometry"]].to_file(fp, driver="GPKG")
    log(f"HMDA parcels: {len(g)}; EULUC class counts {g.euluc.value_counts().sort_index().to_dict()}")
    return g


def main():
    g = extract()
    out = LURAW / "euluc"; T = F.tiles()
    sidx = g.sindex
    for k, (minx, miny, maxx, maxy) in T.items():
        fp = out / f"{k}.tif"
        if fp.exists():
            continue
        sub = g.iloc[sidx.query(box(minx, miny, maxx, maxy))]
        tr = from_origin(minx, maxy, 10, 10)
        a = (rasterize(((geom, v) for geom, v in zip(sub.geometry, sub.ours) if v > 0), (400, 400), transform=tr,
                       fill=0, dtype="uint8") if len(sub) else np.zeros((400, 400), np.uint8))
        with rasterio.open(fp, "w", driver="GTiff", width=400, height=400, count=1, dtype="uint8",
                           crs=f"EPSG:{UTM}", transform=tr, compress="deflate") as d:
            d.write(a, 1)
    log("EULUC tiles written")


if __name__ == "__main__":
    main()
