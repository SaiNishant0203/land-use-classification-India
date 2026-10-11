"""Aggregate every 10 m tile (feat_2023, lab) to one coarse mosaic of HMDA (cell size = LU_CELL).

Per cell (K x K pixels): mean of each band over valid pixels, the mean of h*cov (for a
cover-weighted height), the max of ob_hmax, and the count of each OSM label class (0..5).
Arrays are written as memory-mapped .npy files in work/r<CELL>/ so large grids need not fit in RAM.
"""
import json, time
import numpy as np, rasterio
from numpy.lib.format import open_memmap
from common import *

T = json.loads((DATA / "feat_2023" / "tiles.json").read_text())
minx = min(b[0] for b in T.values()); maxx = max(b[2] for b in T.values())
miny = min(b[1] for b in T.values()); maxy = max(b[3] for b in T.values())
nx, ny = int((maxx - minx) / CELL), int((maxy - miny) / CELL)
nb = len(BANDS)
log(f"{CELL} m: {len(T)} tiles, grid {ny} x {nx} cells, origin x={minx} ymax={maxy}")

mm = lambda name, shape, dt, fill: open_memmap(WORK / f"{name}.npy", mode="w+", dtype=dt, shape=shape)
mean = mm("mean", (nb, ny, nx), np.float32, np.nan); mean[:] = np.nan
hw = mm("hw", (ny, nx), np.float32, np.nan); hw[:] = np.nan
hmax = mm("hmax", (ny, nx), np.float32, np.nan); hmax[:] = np.nan
labc = mm("labc", (6, ny, nx), np.uint8, 0)
valid = mm("valid", (ny, nx), np.bool_, False)
sc = np.array([SCALE[b] for b in BANDS], np.float32)[:, None, None]

t0 = time.time()
for n, (k, (x0, y0, x1, y1)) in enumerate(T.items(), 1):
    with rasterio.open(DATA / "feat_2023" / f"{k}.tif") as s:
        a = s.read()
    with rasterio.open(DATA / "lab" / f"{k}.tif") as s:
        lab = s.read(1)
    ok = (a != -32768).all(0)                                   # (400, 400) pixel validity
    f = a.astype(np.float32) / sc
    f[:, ~ok] = 0
    r0, c0 = int((maxy - y1) / CELL), int((x0 - minx) / CELL)
    n_ok = ok.reshape(NT, K, NT, K).sum((1, 3)).astype(np.float32)          # valid pixels per cell
    v = n_ok > 0
    den = np.maximum(n_ok, 1)
    blk = lambda z: z.reshape(z.shape[:-2] + (NT, K, NT, K)).sum((-3, -1))
    m = blk(f) / den
    m[:, ~v] = np.nan
    h = f[BANDS.index("ob_h")] * f[BANDS.index("ob_cov")]
    hwm = blk(h) / den; hwm[~v] = np.nan
    hx = f[BANDS.index("ob_hmax")].reshape(NT, K, NT, K).max((1, 3)); hx[~v] = np.nan
    sl = (slice(r0, r0 + NT), slice(c0, c0 + NT))
    mean[(slice(None),) + sl] = m
    hw[sl] = hwm; hmax[sl] = hx; valid[sl] = v
    for c in range(6):
        labc[(c,) + sl] = (lab.reshape(NT, K, NT, K) == c).sum((1, 3))
    if n % 50 == 0:
        log(f"  {n}/{len(T)} tiles ({time.time() - t0:.0f}s)")

for a in (mean, hw, hmax, labc, valid):
    a.flush()
(WORK / "meta.json").write_text(json.dumps({"minx": minx, "maxy": maxy, "ny": ny, "nx": nx, "cell": CELL}))
log(f"saved. valid cells {int(valid.sum()):,} of {valid.size:,}; build time {time.time() - t0:.0f}s")
