"""Shared helpers for the pixel-wise land-use pipeline (scripts/lu/).

Design: Earth Engine only produces BASE layers at 10 m (no focal/texture work,
which is what blows the restricted-mode budget). Everything multi-scale is
computed locally from the downloaded tiles, so training pixels and wall-to-wall
inference go through exactly the same code.
"""
from pathlib import Path
import sys, time
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "overnight"))
from common import log, ee_init, UTM, PROC, RAW  # noqa: E402,F401

LU = PROC / "lu"; LU.mkdir(parents=True, exist_ok=True)
LURAW = RAW / "lu"; LURAW.mkdir(parents=True, exist_ok=True)
LUOUT = ROOT / "outputs" / "lu"; LUOUT.mkdir(parents=True, exist_ok=True)

TILE_M = 4000          # 4 km = 400 x 400 px x 76 int16 bands ~ 37 MB (EE cap is 50 MB)
SCALE = 10

S2_BANDS = ["B2", "B3", "B4", "B5", "B8", "B11", "B12"]
# GeoTIFF from getDownloadURL drops band names, so the order is fixed here
BANDS = S2_BANDS + ["ob_cov", "ob_h", "ob_hmax", "ob_cnt", "viirs"] + [f"A{i:02d}" for i in range(64)]


def base_stack(ee, year):
    """All inputs exist separately per year -> safe for change detection later."""
    s2 = (ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
          .filterDate(f"{year}-01-01", f"{year}-12-31")
          .linkCollection(ee.ImageCollection("GOOGLE/CLOUD_SCORE_PLUS/V1/S2_HARMONIZED"), ["cs_cdf"])
          .map(lambda im: im.updateMask(im.select("cs_cdf").gte(0.6)))
          .select(S2_BANDS).median())                      # reflectance x1e4, fits int16
    # the collection is tiled per UTM zone: filtering to Hyderabad makes first() a zone-44N
    # tile, so the mosaic gets the right native 0.5 m grid (an unfiltered first() does not)
    obc = (ee.ImageCollection("GOOGLE/Research/open-buildings-temporal/v1")
           .filterDate(f"{year}-01-01", f"{year}-12-31")
           .filterBounds(ee.Geometry.Point([78.47, 17.40])))
    ob = obc.mosaic().setDefaultProjection(obc.first().select("building_presence").projection())
    prj = ee.Projection(f"EPSG:{UTM}").atScale(SCALE)
    pres = ob.select("building_presence")
    bld = pres.gt(0.5)
    hgt = ob.select("building_height").updateMask(bld)
    agg = lambda im, red: im.reduceResolution(red, maxPixels=1024).reproject(prj)
    ob10 = ee.Image.cat([
        agg(bld.toFloat(), ee.Reducer.mean()).unmask(0).multiply(1000).rename("ob_cov"),     # building cover x1000
        agg(hgt, ee.Reducer.mean()).unmask(0).multiply(10).rename("ob_h"),                 # mean height dm
        agg(hgt, ee.Reducer.max()).unmask(0).multiply(10).rename("ob_hmax"),
        agg(ob.select("building_fractional_count"), ee.Reducer.sum()).unmask(0)
            .multiply(10000).rename("ob_cnt"),                                            # buildings x1e4
    ])
    emb = (ee.ImageCollection("GOOGLE/SATELLITE_EMBEDDING/V1/ANNUAL")
           .filterDate(f"{year}-01-01", f"{year}-12-31").mosaic()
           .multiply(1000))                                                               # [-1,1] -> int16
    # annual VIIRS is split: V21 covers 2013-2021, V22 covers 2022 on (same "average" band)
    viirs = (ee.ImageCollection("NOAA/VIIRS/DNB/ANNUAL_V21")
             .merge(ee.ImageCollection("NOAA/VIIRS/DNB/ANNUAL_V22"))
             .filterDate(f"{year}-01-01", f"{year}-12-31").first().select("average")
             .unmask(0).multiply(100).rename("viirs"))
    return ee.Image.cat([s2, ob10, viirs, emb]).toInt16()


def tile_grid(shape_utm):
    """4 km tiles covering the AOI (UTM), keyed 'x{col}_y{row}'."""
    from shapely.geometry import box
    minx, miny, maxx, maxy = shape_utm.bounds
    x0 = np.floor(minx / TILE_M) * TILE_M; y0 = np.floor(miny / TILE_M) * TILE_M
    out = {}
    for x in np.arange(x0, maxx, TILE_M):
        for y in np.arange(y0, maxy, TILE_M):
            b = box(x, y, x + TILE_M, y + TILE_M)
            if b.intersects(shape_utm):
                out[f"x{int(x/1000)}_y{int(y/1000)}"] = b
    return out


def download_tile_parts(ee, img, bbox_utm, fp, splits=((0, 7), (7, 12), (12, 76)), retries=8):
    """Download one tile in band groups and merge locally into a single file.

    A single 76-band request now trips Earth Engine's "User memory limit exceeded" in
    restricted mode; the same bands split in two go through fine.
    """
    import rasterio
    fp = Path(fp)
    if fp.exists() and fp.stat().st_size > 1000:
        return fp
    arrs, prof = [], None
    for a, b in splits:
        part = fp.with_suffix(f".b{a}_{b}.tif")
        download_tile(ee, img.select(list(range(a, b))), bbox_utm, part, retries=retries)
        with rasterio.open(part) as s:
            arrs.append(s.read())
            prof = s.profile
    import numpy as np
    stack = np.concatenate(arrs)
    prof.update(count=len(stack), compress="deflate", dtype=stack.dtype)
    tmp = fp.with_suffix(".part")
    with rasterio.open(tmp, "w", **prof) as d:
        d.write(stack)
    tmp.replace(fp)
    for a, b in splits:
        fp.with_suffix(f".b{a}_{b}.tif").unlink(missing_ok=True)
    return fp


def download_tile(ee, img, bbox_utm, fp, retries=8):
    """Download one UTM-aligned tile at 10 m. Resumable (skips existing files)."""
    import requests
    fp = Path(fp)
    if fp.exists() and fp.stat().st_size > 1000:
        return fp
    minx, miny, maxx, maxy = bbox_utm.bounds
    params = {"crs": f"EPSG:{UTM}", "format": "GEO_TIFF",
              "crs_transform": [SCALE, 0, minx, 0, -SCALE, maxy],
              "region": ee.Geometry.Rectangle([minx, miny, maxx, maxy], f"EPSG:{UTM}", False)}
    for k in range(retries):
        try:
            t0 = time.time()
            url = img.getDownloadURL(params)
            r = requests.get(url, timeout=900)
            if r.status_code != 200:
                raise RuntimeError(f"HTTP {r.status_code}: {r.text[:300]}")
            tmp = fp.with_suffix(".part"); tmp.write_bytes(r.content); tmp.replace(fp)
            log(f"  {fp.name}: {len(r.content)/1e6:.1f} MB in {time.time()-t0:.0f}s")
            return fp
        except Exception as e:
            log(f"  {fp.name} retry {k}: {str(e)[:200]}")
            if any(t in str(e) for t in ("Image.", "Collection.", "request size")):  # won't fix itself
                raise
            time.sleep(min(240, 20 * 2 ** k))
    raise RuntimeError(f"{fp.name} failed")
