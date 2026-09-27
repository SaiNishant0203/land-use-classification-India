"""
Download the 10 m base feature stack (lu_common.base_stack) for every 4 km tile of HMDA.
Tiles are ordered from the city centre outward so a usable core exists early.
Parallel requests (EE restricted mode tolerates a few). Resumable.

Output: data/raw/lu/feat_<year>/<tile>.tif  (76 int16 bands, see lu_common.BANDS)
"""
import sys, json
from concurrent.futures import ThreadPoolExecutor, as_completed
import numpy as np, geopandas as gpd
from lu_common import ee_init, base_stack, tile_grid, download_tile_parts, LURAW, PROC, UTM, log

YEAR = int(sys.argv[1]) if len(sys.argv) > 1 else 2023
WORKERS = 2
CENTRE = (231000, 1921000)       # Charminar, UTM 44N

ee = ee_init()
aoi = gpd.read_file(PROC / "aoi_utm44n.gpkg").to_crs(UTM).geometry.iloc[0]
tiles = tile_grid(aoi)
order = sorted(tiles, key=lambda k: np.hypot(tiles[k].centroid.x - CENTRE[0], tiles[k].centroid.y - CENTRE[1]))
out = LURAW / f"feat_{YEAR}"; out.mkdir(exist_ok=True)
(out / "tiles.json").write_text(json.dumps({k: list(tiles[k].bounds) for k in order}))
img = base_stack(ee, YEAR)
log(f"{len(order)} tiles, {sum((out / f'{k}.tif').exists() for k in order)} already done")
failed = []
with ThreadPoolExecutor(WORKERS) as ex:
    futs = {ex.submit(download_tile_parts, ee, img, tiles[k], out / f"{k}.tif"): k for k in order}
    for i, f in enumerate(as_completed(futs), 1):
        try:
            f.result()
        except Exception as e:
            failed.append(futs[f]); log(f"FAILED {futs[f]}: {e}")
        if i % 20 == 0:
            log(f"progress {i}/{len(order)}")
log(f"done; failed: {failed}")
