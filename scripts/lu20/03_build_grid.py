"""
Aggregate one year's 10 m tiles (12 physical bands + that year's labels) to a 20 m mosaic of HMDA.
Adapted from experiments/res100/build_grid.py (Ethan): per cell, the mean of each band over valid
pixels, the mean of height x cover (for a cover-weighted height), the max of ob_hmax, and the count
of each label class 0..5. For 2023 it also counts the old labels made from 2026 OSM
(data/raw/lu/lab/), the control for the effect of dating the OSM.

Usage: python 03_build_grid.py <year>
Output: data/raw/lu/lu20/grid_<year>/{mean,hw,hmax,labc[,labc_osm2026],valid}.npy + meta.json
"""
import sys, json, time
import numpy as np, rasterio
from numpy.lib.format import open_memmap
from common20 import *


def main():
    year = int(sys.argv[1])
    T = tiles()
    G = W20 / f"grid_{year}"; G.mkdir(exist_ok=True)
    minx = min(b[0] for b in T.values()); maxx = max(b[2] for b in T.values())
    miny = min(b[1] for b in T.values()); maxy = max(b[3] for b in T.values())
    nx, ny, nb = int((maxx - minx) / CELL), int((maxy - miny) / CELL), len(BANDS)
    log(f"{year}: {len(T)} tiles, grid {ny} x {nx} cells")
    mm = lambda n, shape, dt: open_memmap(G / f"{n}.npy", mode="w+", dtype=dt, shape=shape)
    mean = mm("mean", (nb, ny, nx), np.float32); mean[:] = np.nan
    hw = mm("hw", (ny, nx), np.float32); hw[:] = np.nan
    hmax = mm("hmax", (ny, nx), np.float32); hmax[:] = np.nan
    valid = mm("valid", (ny, nx), np.bool_); valid[:] = False
    labs = {"labc": W20 / f"lab_{year}"}
    if year == 2023:
        labs["labc_osm2026"] = RAW / "lab"
    labc = {n: mm(n, (6, ny, nx), np.uint8) for n in labs}
    for a in labc.values():
        a[:] = 0
    sc = np.array([SCALE[b] for b in BANDS], np.float32)[:, None, None]
    blk = lambda z: z.reshape(z.shape[:-2] + (NT, K, NT, K)).sum((-3, -1))
    t0 = time.time()
    for n, (k, (x0, y0, x1, y1)) in enumerate(T.items(), 1):
        with rasterio.open(RAW / FEAT[year] / f"{k}.tif") as s:
            a = s.read(list(range(1, nb + 1)))
        ok = (a != -32768).all(0)
        f = a.astype(np.float32) / sc
        f[:, ~ok] = 0
        r0, c0 = int((maxy - y1) / CELL), int((x0 - minx) / CELL)
        n_ok = ok.reshape(NT, K, NT, K).sum((1, 3)).astype(np.float32)
        v = n_ok > 0; den = np.maximum(n_ok, 1)
        m = blk(f) / den; m[:, ~v] = np.nan
        hwm = blk(f[BANDS.index("ob_h")] * f[BANDS.index("ob_cov")]) / den; hwm[~v] = np.nan
        hx = f[BANDS.index("ob_hmax")].reshape(NT, K, NT, K).max((1, 3)); hx[~v] = np.nan
        sl = (slice(r0, r0 + NT), slice(c0, c0 + NT))
        mean[(slice(None),) + sl] = m; hw[sl] = hwm; hmax[sl] = hx; valid[sl] = v
        for name, folder in labs.items():
            with rasterio.open(folder / f"{k}.tif") as s:
                lab = s.read(1)
            for c in range(6):
                labc[name][(c,) + sl] = (lab.reshape(NT, K, NT, K) == c).sum((1, 3))
        if n % 100 == 0:
            log(f"  {n}/{len(T)} tiles ({time.time() - t0:.0f}s)")
    for a in [mean, hw, hmax, valid, *labc.values()]:
        a.flush()
    (G / "meta.json").write_text(json.dumps({"minx": minx, "maxy": maxy, "ny": ny, "nx": nx, "cell": CELL,
                                             "year": year, "labels": list(labs)}))
    (W20 / f"grid_{year}.done").write_text("ok")
    log(f"{year}: valid cells {int(valid.sum()):,}; {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
