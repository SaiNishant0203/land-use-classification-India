"""Aggregate every 10 m tile (feat_2023, lab) to one 100 m mosaic of HMDA.

Per 100 m cell (10 x 10 pixels): mean of each band over valid pixels, the mean of h*cov (for a
cover-weighted height), the max of ob_hmax, and the count of each OSM label class (0..5).
Output: work/grid100.npz
"""
import json, time
import numpy as np, rasterio
from common import *

T = json.loads((DATA / "feat_2023" / "tiles.json").read_text())
minx = min(b[0] for b in T.values()); maxx = max(b[2] for b in T.values())
miny = min(b[1] for b in T.values()); maxy = max(b[3] for b in T.values())
nx, ny = int((maxx - minx) / CELL), int((maxy - miny) / CELL)
nb = len(BANDS)
log(f"{len(T)} tiles, grid {ny} x {nx} cells of {CELL} m, origin x={minx} ymax={maxy}")

mean = np.full((nb, ny, nx), np.nan, np.float32)
hw = np.full((ny, nx), np.nan, np.float32)          # mean of (h * cov)
hmax = np.full((ny, nx), np.nan, np.float32)
labc = np.zeros((6, ny, nx), np.uint8)              # OSM label counts per class
valid = np.zeros((ny, nx), bool)
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
    n_ok = ok.reshape(40, K, 40, K).sum((1, 3)).astype(np.float32)          # valid pixels per cell
    v = n_ok > 0
    den = np.maximum(n_ok, 1)
    blk = lambda z: z.reshape(z.shape[:-2] + (40, K, 40, K)).sum((-3, -1))
    m = blk(f) / den
    m[:, ~v] = np.nan
    h = f[BANDS.index("ob_h")] * f[BANDS.index("ob_cov")]
    hwm = blk(h) / den; hwm[~v] = np.nan
    hx = f[BANDS.index("ob_hmax")].reshape(40, K, 40, K).max((1, 3)); hx[~v] = np.nan
    sl = (slice(r0, r0 + 40), slice(c0, c0 + 40))
    mean[(slice(None),) + sl] = m
    hw[sl] = hwm; hmax[sl] = hx; valid[sl] = v
    for c in range(6):
        labc[(c,) + sl] = (lab.reshape(40, K, 40, K) == c).sum((1, 3))
    if n % 50 == 0:
        log(f"  {n}/{len(T)} tiles ({time.time() - t0:.0f}s)")

np.savez_compressed(WORK / "grid100.npz", mean=mean, hw=hw, hmax=hmax, labc=labc, valid=valid,
                    origin=np.array([minx, maxy]), bands=np.array(BANDS))
log(f"saved. valid cells {valid.sum():,} of {valid.size:,}; build time {time.time() - t0:.0f}s")
