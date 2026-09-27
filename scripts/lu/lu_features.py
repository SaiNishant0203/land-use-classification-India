"""
Per-pixel feature engineering on the 10 m tile grid. One function for training samples
and wall-to-wall prediction, so both see identical features.

A tile is processed with a PAD-pixel margin assembled from its 8 neighbours (zeros where a
neighbour does not exist), so neighbourhood features have no seams at tile edges.
"""
import json
import numpy as np, rasterio
from scipy.ndimage import uniform_filter, maximum_filter
from lu_common import LURAW, BANDS

PAD = 40
TS = 400
WINDOWS = [7, 15, 31, 61]           # 70 m, 150 m, 310 m, 610 m square windows
_TILES = None


def tiles():
    global _TILES
    if _TILES is None:
        _TILES = json.loads((LURAW / "feat_2023" / "tiles.json").read_text())
    return _TILES


def neighbour_key(key, dx, dy):
    x, y = key[1:].split("_y")
    return f"x{int(x) + 4 * dx}_y{int(y) + 4 * dy}"


def read_padded(key, folder="feat_2023", nb=len(BANDS)):
    """(bands, TS+2*PAD, TS+2*PAD) int16 array centred on tile `key`."""
    big = np.zeros((nb, 3 * TS, 3 * TS), np.int16)
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            fp = LURAW / folder / f"{neighbour_key(key, dx, dy)}.tif"
            if fp.exists():
                with rasterio.open(fp) as s:
                    a = s.read()
                r0 = (1 - dy) * TS; c0 = (dx + 1) * TS          # north is up: +dy tile sits above
                big[:, r0:r0 + TS, c0:c0 + TS] = a[:, :TS, :TS]
    return big[:, TS - PAD:2 * TS + PAD, TS - PAD:2 * TS + PAD]


def nd(a, b):
    return (a - b) / (a + b + 1e-6)


def compute(key, folder="feat_2023"):
    """Return (names, float32 array (F, TS, TS)) for tile `key`."""
    raw = read_padded(key, folder=folder).astype(np.float32)
    B = {n: raw[i] for i, n in enumerate(BANDS)}
    s2 = {b: B[b] / 1e4 for b in ["B2", "B3", "B4", "B5", "B8", "B11", "B12"]}
    cov = B["ob_cov"] / 1000; h = B["ob_h"] / 10; hmax = B["ob_hmax"] / 10
    cnt = B["ob_cnt"] / 1e4; viirs = B["viirs"] / 100
    ndvi = nd(s2["B8"], s2["B4"]); ndbi = nd(s2["B11"], s2["B8"]); mndwi = nd(s2["B3"], s2["B11"])
    bsi = nd(s2["B11"] + s2["B4"], s2["B8"] + s2["B2"])

    feats = {**{k: v for k, v in s2.items()}, "ob_cov": cov, "ob_h": h, "ob_hmax": hmax,
             "ob_cnt": cnt, "viirs": viirs, "ndvi": ndvi, "ndbi": ndbi, "mndwi": mndwi, "bsi": bsi}
    for i in range(64):
        feats[f"A{i:02d}"] = B[f"A{i:02d}"] / 1000
    hw = h * cov                                        # height weighted by building cover
    for w in WINDOWS:
        m = lambda a: uniform_filter(a, w, mode="nearest")
        mc, mcnt, mhw = m(cov), m(cnt), m(hw)
        feats[f"cov_{w}"] = mc
        feats[f"cnt_{w}"] = mcnt * 100                  # buildings per hectare-ish scale
        feats[f"bldg_area_{w}"] = np.where(mcnt > 1e-5, mc * 100 / np.maximum(mcnt, 1e-5), 0)  # m2 per building
        feats[f"bldg_h_{w}"] = np.where(mc > 1e-3, mhw / np.maximum(mc, 1e-3), 0)            # mean building height
        feats[f"ndvi_{w}"] = m(ndvi); feats[f"ndbi_{w}"] = m(ndbi)
        feats[f"mndwi_{w}"] = m(mndwi); feats[f"viirs_{w}"] = m(viirs)
    for w in (15, 31):
        feats[f"hmax_{w}"] = maximum_filter(hmax, w, mode="nearest")
    for w in (7, 15):
        m1 = uniform_filter(s2["B8"], w); m2 = uniform_filter(s2["B8"] ** 2, w)
        feats[f"b8_sd_{w}"] = np.sqrt(np.maximum(m2 - m1 ** 2, 0))
    m1 = uniform_filter(h, 15); m2 = uniform_filter(h ** 2, 15)
    feats["h_sd_15"] = np.sqrt(np.maximum(m2 - m1 ** 2, 0))
    for i in range(64):
        feats[f"A{i:02d}_15"] = uniform_filter(feats[f"A{i:02d}"], 15, mode="nearest")
    names = list(feats)
    arr = np.stack([feats[n][PAD:PAD + TS, PAD:PAD + TS] for n in names]).astype(np.float32)
    return names, arr
