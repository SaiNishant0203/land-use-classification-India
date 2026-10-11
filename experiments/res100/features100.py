"""The 100 m analogue of lu_features.compute(): same feature families, computed on the 100 m mosaic.

At 10 m the neighbourhood windows were 70/150/310/610 m (7/15/31/61 px). At 100 m a cell already
spans 100 m, so the windows are 3/5/7 cells = 300/500/700 m. The 10 m features that look inside
a 70-150 m window (the finest context) have no 100 m counterpart: that is part of what the
experiment measures. Filters are mask-aware, so cells outside HMDA do not pull values to zero.
"""
import numpy as np
from scipy.ndimage import uniform_filter, maximum_filter
from common import *

WIN = [3, 5, 7]


def load():
    z = np.load(WORK / "grid100.npz")
    return {k: z[k] for k in z.files}


def nd(a, b):
    return (a - b) / (a + b + 1e-6)


def compute(g, aef=True):
    """Return (names, float32 array (F, ny, nx)); invalid cells hold NaN."""
    valid = g["valid"]; B = {b: g["mean"][i] for i, b in enumerate(BANDS)}
    vf = valid.astype(np.float32)

    def mmean(a, w):                                   # mask-aware window mean
        num = uniform_filter(np.where(valid, a, 0).astype(np.float32), w, mode="constant")
        den = uniform_filter(vf, w, mode="constant")
        return np.where(den > 1e-6, num / np.maximum(den, 1e-6), np.nan)

    cov = B["ob_cov"]; cnt = B["ob_cnt"]; viirs = B["viirs"]
    h = np.where(cov > 1e-3, g["hw"] / np.maximum(cov, 1e-3), 0)       # cover-weighted building height
    hmax = g["hmax"]
    ndvi = nd(B["B8"], B["B4"]); ndbi = nd(B["B11"], B["B8"]); mndwi = nd(B["B3"], B["B11"])
    bsi = nd(B["B11"] + B["B4"], B["B8"] + B["B2"])
    F = {b: B[b] for b in BANDS[:7]}
    F.update(ob_cov=cov, ob_h=h, ob_hmax=hmax, ob_cnt=cnt, viirs=viirs, ndvi=ndvi, ndbi=ndbi, mndwi=mndwi, bsi=bsi)
    if aef:
        for i in range(64):
            F[f"A{i:02d}"] = B[f"A{i:02d}"]
    hw = g["hw"]
    for w in WIN:
        mc, mcnt, mhw = mmean(cov, w), mmean(cnt, w), mmean(hw, w)
        F[f"cov_{w}"] = mc
        F[f"cnt_{w}"] = mcnt * 100
        F[f"bldg_area_{w}"] = np.where(mcnt > 1e-5, mc * 100 / np.maximum(mcnt, 1e-5), 0)
        F[f"bldg_h_{w}"] = np.where(mc > 1e-3, mhw / np.maximum(mc, 1e-3), 0)
        F[f"ndvi_{w}"] = mmean(ndvi, w); F[f"ndbi_{w}"] = mmean(ndbi, w)
        F[f"mndwi_{w}"] = mmean(mndwi, w); F[f"viirs_{w}"] = mmean(viirs, w)
    for w in (3, 5):
        F[f"hmax_{w}"] = maximum_filter(np.where(valid, hmax, -1e9), w, mode="nearest")
    for w in (3, 5):
        m1 = mmean(B["B8"], w); m2 = mmean(B["B8"] ** 2, w)
        F[f"b8_sd_{w}"] = np.sqrt(np.maximum(m2 - m1 ** 2, 0))
    m1 = mmean(h, 3); m2 = mmean(h ** 2, 3)
    F["h_sd_3"] = np.sqrt(np.maximum(m2 - m1 ** 2, 0))
    if aef:
        for i in range(64):
            F[f"A{i:02d}_3"] = mmean(B[f"A{i:02d}"], 3)
    names = list(F)
    arr = np.stack([F[n] for n in names]).astype(np.float32)
    arr[:, ~valid] = np.nan
    return names, arr


def is_aef(c):
    return c[0] == "A" and c[1:3].isdigit()


if __name__ == "__main__":
    import time; t = time.time()
    g = load(); names, arr = compute(g)
    log(f"{len(names)} features, {arr.shape}, {time.time() - t:.0f}s; "
        f"{sum(not is_aef(n) for n in names)} non-AlphaEarth")
