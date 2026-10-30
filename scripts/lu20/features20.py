"""53 physical features on the 20 m mosaic: experiments/res100/features_coarse.py (Ethan) without the
AlphaEarth bands. Computed in row strips with a halo; window filters are mask-aware, so cells outside
the tiles do not pull neighbourhood means towards zero."""
import json
import numpy as np
from scipy.ndimage import uniform_filter, maximum_filter
from common20 import *


def open_grid(year):
    G = W20 / f"grid_{year}"
    meta = json.loads((G / "meta.json").read_text())
    g = {k: np.load(G / f"{k}.npy", mmap_mode="r") for k in ["mean", "hw", "hmax", "valid"] + meta["labels"]}
    g["meta"] = meta
    return g


def nd(a, b):
    return (a - b) / (a + b + 1e-6)


def compute(g):
    """g: in-memory mean (12,h,w), hw, hmax, valid -> (names, dict name -> (h,w) float32)."""
    valid = g["valid"]; B = {b: g["mean"][i] for i, b in enumerate(BANDS)}
    vf = valid.astype(np.float32)

    def mmean(a, w):
        num = uniform_filter(np.where(valid, a, 0).astype(np.float32), w, mode="constant")
        den = uniform_filter(vf, w, mode="constant")
        return np.where(den > 1e-6, num / np.maximum(den, 1e-6), np.nan).astype(np.float32)

    cov, cnt, viirs, hw, hmax = B["ob_cov"], B["ob_cnt"], B["viirs"], g["hw"], g["hmax"]
    h = np.where(cov > 1e-3, hw / np.maximum(cov, 1e-3), 0).astype(np.float32)
    ndvi = nd(B["B8"], B["B4"]); ndbi = nd(B["B11"], B["B8"]); mndwi = nd(B["B3"], B["B11"])
    bsi = nd(B["B11"] + B["B4"], B["B8"] + B["B2"])
    F = {b: B[b] for b in BANDS[:7]}
    F.update(ob_cov=cov, ob_h=h, ob_hmax=hmax, ob_cnt=cnt, viirs=viirs, ndvi=ndvi, ndbi=ndbi, mndwi=mndwi, bsi=bsi)
    for w in CFG["win"]:
        mc, mcnt, mhw = mmean(cov, w), mmean(cnt, w), mmean(hw, w)
        F[f"cov_{w}"] = mc
        F[f"cnt_{w}"] = mcnt * 100
        F[f"bldg_area_{w}"] = np.where(mcnt > 1e-5, mc * 100 / np.maximum(mcnt, 1e-5), 0)
        F[f"bldg_h_{w}"] = np.where(mc > 1e-3, mhw / np.maximum(mc, 1e-3), 0)
        F[f"ndvi_{w}"] = mmean(ndvi, w); F[f"ndbi_{w}"] = mmean(ndbi, w)
        F[f"mndwi_{w}"] = mmean(mndwi, w); F[f"viirs_{w}"] = mmean(viirs, w)
    for w in CFG["hmax"]:
        F[f"hmax_{w}"] = maximum_filter(np.where(valid, hmax, -1e9), w, mode="nearest")
    for w in CFG["b8sd"]:
        m1 = mmean(B["B8"], w); m2 = mmean(B["B8"] ** 2, w)
        F[f"b8_sd_{w}"] = np.sqrt(np.maximum(m2 - m1 ** 2, 0))
    s = CFG["small"]
    m1 = mmean(h, s); m2 = mmean(h ** 2, s)
    F[f"h_sd_{s}"] = np.sqrt(np.maximum(m2 - m1 ** 2, 0))
    return list(F), F


def strips(ny):
    n = CFG["strip"]
    return [(r, min(r + n, ny)) for r in range(0, ny, n)]


def load_strip(grid, r0, r1):
    """Rows [r0, r1) plus a halo -> (dict, row offset of r0 inside the strip)."""
    a, b = max(0, r0 - HALO), min(grid["valid"].shape[0], r1 + HALO)
    return {"mean": np.array(grid["mean"][:, a:b]), "hw": np.array(grid["hw"][a:b]),
            "hmax": np.array(grid["hmax"][a:b]), "valid": np.array(grid["valid"][a:b])}, r0 - a


def extract(grid, flat):
    """Features at cells given by sorted flat indices (row * nx + col) -> (names, X float32 (n, F))."""
    ny, nx = grid["valid"].shape
    rr, cc = flat // nx, flat % nx
    X, names = None, None
    for r0, r1 in strips(ny):
        sel = np.nonzero((rr >= r0) & (rr < r1))[0]
        if not len(sel):
            continue
        gs, off = load_strip(grid, r0, r1)
        names, F = compute(gs)
        if X is None:
            X = np.empty((len(flat), len(names)), np.float32)
        y, x = rr[sel] - r0 + off, cc[sel]
        for j, n in enumerate(names):
            X[sel, j] = F[n][y, x]
    return names, X
