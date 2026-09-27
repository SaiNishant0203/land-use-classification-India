"""
Existing land-cover / land-use PRODUCTS on the same 4 km / 10 m tile grid as the features.
Used for (a) the audit of existing models and (b) water/tree/open reference for labels.
They are never used as model features.

Bands (uint8, 255 = no data / outside product extent):
  dw      Dynamic World 2023 mode label (0 water .. 8 snow)
  wc      ESA WorldCover 2021 class (10 tree, 20 shrub, 30 grass, 40 crop, 50 built, 60 bare, 80 water, 90 wetland)
  jrc     JRC Global Surface Water occurrence 1984-2021 (%)
  ghsc    GHS-BUILT-C 2018 class (1-5 open, 11-15 residential, 21-25 non-residential)
  wri     WRI intra-urban land use V1 lulc (0 open, 1 nonres, 2 atomistic, 3 informal, 4 formal, 5 housing project, 6 road)
  ind     Global industrial land 2023 (0 non-built, 1 industrial, 2 other built)
Output: data/raw/lu/prod/<tile>.tif
"""
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from lu_common import ee_init, download_tile, LURAW, log
from shapely.geometry import box

PROD_BANDS = ["dw", "wc", "jrc", "ghsc", "wri", "ind"]


def product_stack(ee):
    pt = ee.Geometry.Point([78.47, 17.40])
    dw = (ee.ImageCollection("GOOGLE/DYNAMICWORLD/V1").filterDate("2023-01-01", "2024-01-01")
          .filterBounds(pt.buffer(80000)).select("label").mode())
    wc = ee.ImageCollection("ESA/WorldCover/v200").first().select("Map")
    jrc = ee.Image("JRC/GSW1_4/GlobalSurfaceWater").select("occurrence").unmask(0)
    ghsc = ee.Image("JRC/GHSL/P2023A/GHS_BUILT_C/2018").select("built_characteristics")
    wri = (ee.ImageCollection("projects/wri-datalab/cities/urban_land_use/V1")
           .filterBounds(pt).first().select("lulc"))
    ind = (ee.ImageCollection("projects/sat-io/open-datasets/INDUSTRIAL_LAND")
           .filterBounds(pt).filter(ee.Filter.eq("year", 2023)).first())
    ims = [dw, wc, jrc, ghsc, wri, ind]
    return ee.Image.cat([i.unmask(255, False).toUint8().rename(n) for i, n in zip(ims, PROD_BANDS)])


if __name__ == "__main__":
    ee = ee_init()
    tiles = json.loads((LURAW / "feat_2023" / "tiles.json").read_text())
    out = LURAW / "prod"; out.mkdir(exist_ok=True)
    img = product_stack(ee)
    with ThreadPoolExecutor(2) as ex:
        futs = {ex.submit(download_tile, ee, img, box(*b), out / f"{k}.tif"): k for k, b in tiles.items()}
        for i, f in enumerate(as_completed(futs), 1):
            try:
                f.result()
            except Exception as e:
                log(f"FAILED {futs[f]}: {e}")
            if i % 50 == 0:
                log(f"progress {i}/{len(futs)}")
    log("done")
