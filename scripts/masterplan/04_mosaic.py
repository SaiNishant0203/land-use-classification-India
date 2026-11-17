"""
Mosaic the per-sheet zone rasters (03_zones.py) into one HMDA layer on the 20 m grid.

Where sheets overlap (the 300 m buffer around each mandal), the sheet with more colour votes wins. Cells
outside every sheet's mandal stay 0 (not covered: the 2031 plan sheets cover the HMDA area outside the
erstwhile HUDA core).

Usage: python scripts/masterplan/04_mosaic.py
Output: data/processed/masterplan/mp2031_zones_20m.tif (uint8 zone code), mp2031_zones.png, zone_shares.csv
"""
import importlib.util as iu
from pathlib import Path
import numpy as np, pandas as pd, geopandas as gpd, rasterio
from PIL import Image
from rasterio.features import rasterize

ROOT = Path(__file__).resolve().parents[2]
_s = iu.spec_from_file_location("z", Path(__file__).parent / "03_zones.py"); Z3 = iu.module_from_spec(_s); _s.loader.exec_module(Z3)
ZD = Z3.ZD


def main():
    files = sorted(ZD.glob("*_20m.tif"))
    Z = V = prof = None
    for f in files:
        with rasterio.open(f) as s:
            z, v = s.read(1).astype(np.uint8), s.read(2)
            if Z is None:
                Z, V, prof = np.zeros_like(z), np.zeros_like(v), s.profile
        take = (z > 0) & (v > V)
        Z[take] = z[take]; V[take] = v[take]
    aoi = gpd.read_file(ROOT / "data/processed/aoi_utm44n.gpkg").to_crs(32644)
    inside = rasterize(((g, 1) for g in aoi.geometry), Z.shape, transform=prof["transform"], dtype="uint8").astype(bool)
    Z[~inside] = 0
    prof.update(count=1, dtype="uint8", nodata=0)
    with rasterio.open(ROOT / "data/processed/masterplan/mp2031_zones_20m.tif", "w", **prof) as o:
        o.write(Z, 1)
    n = inside.sum()
    rows = [{"zone": k, "name": Z3.NAMES.get(k, "not covered / not read"), "km2": (Z[inside] == k).sum() * 4e-4,
             "share_of_HMDA": (Z[inside] == k).sum() / n} for k in range(13)]
    S = pd.DataFrame(rows); S.to_csv(ROOT / "data/processed/masterplan/zone_shares.csv", index=False)
    print(f"{len(files)} sheets; covered {(Z[inside] > 0).mean():.1%} of HMDA"); print(S.round(3).to_string(index=False))
    pal = np.array([Z3.COL[k] for k in range(13)], np.uint8); img = pal[Z]; img[~inside] = (40, 40, 40)
    im = Image.fromarray(img); im.thumbnail((1800, 1800)); im.save(ROOT / "data/processed/masterplan/mp2031_zones.png")


if __name__ == "__main__":
    main()
