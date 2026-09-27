"""
Extra Sentinel-2 bands (B6, B7, B8A) needed only by BigEarthNet-style models, which take
10 bands: B02 B03 B04 B05 B06 B07 B08 B8A B11 B12. Same cloud-masked 2023 median as
lu_common.base_stack so every model sees the same imagery.
Output: data/raw/lu/s2x_2023/<tile>.tif  (int16: B6, B7, B8A)
"""
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from shapely.geometry import box
from lu_common import ee_init, download_tile, LURAW, log


def s2_extra(ee, year=2023):
    return (ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
            .filterDate(f"{year}-01-01", f"{year}-12-31")
            .linkCollection(ee.ImageCollection("GOOGLE/CLOUD_SCORE_PLUS/V1/S2_HARMONIZED"), ["cs_cdf"])
            .map(lambda im: im.updateMask(im.select("cs_cdf").gte(0.6)))
            .select(["B6", "B7", "B8A"]).median().toInt16())


if __name__ == "__main__":
    ee = ee_init()
    tiles = json.loads((LURAW / "feat_2023" / "tiles.json").read_text())
    out = LURAW / "s2x_2023"; out.mkdir(exist_ok=True)
    img = s2_extra(ee)
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
