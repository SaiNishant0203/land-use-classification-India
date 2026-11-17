"""
Georeference the 30 HMDA Master Plan 2031 district sheets (OpenCity JPEGs, 1:25,000, approved 2013).

The sheets have no coordinate ticks. Each sheet draws its own planning district (mandal) in strong colours
and the neighbours faded, so the zoned area is a clean shape. It is matched to the same mandal(s) from the
SHRUG Census 2011 village polygons (data/raw/shrug/shrid_hmda.gpkg, clipped to HMDA):

  1  zoned-area mask: saturation > 0.25, 15-px moving share > 0.35, opening (removes roads), holes filled,
     largest component, legend panel excluded
  2  similarity transform pixel -> UTM 44N (scale, rotation, shift), start from the area ratio and the
     centroids, then Nelder-Mead on the intersection-over-union of the two shapes
  3  quality: IoU, and the mean distance between the two outlines

Usage: python scripts/masterplan/01_georef.py [sheet ...]       (default: all sheets)
Output: data/processed/masterplan/georef.csv, georef_<sheet>.png (overlay for checking by eye)
"""
import sys, json, time
from pathlib import Path
import numpy as np, pandas as pd, geopandas as gpd
from PIL import Image
from scipy.ndimage import uniform_filter, binary_opening, binary_erosion, binary_fill_holes, label, distance_transform_edt
from scipy.optimize import minimize
from rasterio.features import rasterize
from affine import Affine

Image.MAX_IMAGE_PIXELS = None
ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data/raw/masterplan_hmda2031"
OUT = ROOT / "data/processed/masterplan"; OUT.mkdir(parents=True, exist_ok=True)
RED = 8                     # work on the sheet reduced 8 x (about 25 m per pixel at 1:25,000, 200 dpi)
# sheet -> (district, [SHRUG subdistrict names])
MANDALS = {
    "Bibinagar": ("nalgonda", ["bibinagar"]), "Bommalaramaram": ("nalgonda", ["bommalaramaram"]),
    "Buvanagiri": ("nalgonda", ["bhongir"]), "Choutuppal": ("nalgonda", ["choutuppal"]),
    "Pochampalli": ("nalgonda", ["pochampalle"]),
    "Chevella": ("rangareddy", ["chevella"]), "Ghatkesar": ("rangareddy", ["ghatkesar"]),
    "Hayathnagar": ("rangareddy", ["hayathnagar"]), "Ibrahimpatnam_Manchal": ("rangareddy", ["ibrahimpatnam", "manchal"]),
    "Kandukur": ("rangareddy", ["kandukur"]), "Kisara": ("rangareddy", ["keesara"]),
    "Maheshwaram": ("rangareddy", ["maheswaram"]), "Medchal_Qutubullapur": ("rangareddy", ["medchal", "qutubullapur"]),
    "Moinabad_Rajendranagar": ("rangareddy", ["moinabad", "rajendranagar"]), "Shahbad": ("rangareddy", ["shabad"]),
    "Shahmirpet": ("rangareddy", ["shamirpet"]), "Shamshabad": ("rangareddy", ["shamshabad"]),
    "Shankarpalli_Ramchandrapuram": ("rangareddy", ["shankarpalle"]), "Yacharam": ("rangareddy", ["yacharam"]),
    "Faruqnagar": ("mahbubnagar", ["farooqnagar"]), "Kothuru": ("mahbubnagar", ["kothur"]),
    "Hatnura": ("medak", ["hathnoora"]), "Jinnawaram_FPLU": ("medak", ["jinnaram"]), "Mulug": ("medak", ["mulug"]),
    "Narsapur": ("medak", ["narsapur"]), "Patancheruvu": ("medak", ["patancheru"]), "Sangareddy": ("medak", ["sangareddy"]),
    "Shivampet": ("medak", ["shivampet"]), "Tupran": ("medak", ["tupran"]), "Wargal": ("medak", ["wargal"]),
}
# Shankarpalli_Ramchandrapuram: ramachandrapuram is in Medak in SHRUG
EXTRA = {"Shankarpalli_Ramchandrapuram": [("medak", "ramachandrapuram")]}
log = lambda *a: print(time.strftime("%H:%M:%S"), *a, flush=True)


def zoned_mask(fn):
    """Zoned area at 4 x reduction (tuned on Bibinagar), returned at RED x."""
    im = Image.open(fn).convert("RGB")
    W, H = im.size
    a = np.asarray(im.reduce(4)).astype(np.float32) / 255
    mx, mn = a.max(2), a.min(2); sat = (mx - mn) / (mx + 1e-6)
    m = uniform_filter((sat > 0.25).astype(np.float32), 15) > 0.15
    m = binary_fill_holes(binary_opening(m, iterations=6))
    m[:, int(0.855 * m.shape[1]):] = False          # legend panel on the right
    lab, n = label(m)
    if n == 0:
        return None, (W, H)
    sz = np.bincount(lab.ravel()); sz[0] = 0
    m = lab == sz.argmax()
    k = RED // 4; h, w = (m.shape[0] // k) * k, (m.shape[1] // k) * k
    m = m[:h, :w].reshape(h // k, k, w // k, k).mean((1, 3)) > 0.5
    return m, (W, H)


def reference(sheet, shr):
    dist, subs = MANDALS[sheet]
    sel = shr[(shr.district_name == dist) & shr.subdistrict_name.isin(subs)]
    for dd, ss in EXTRA.get(sheet, []):
        sel = pd.concat([sel, shr[(shr.district_name == dd) & (shr.subdistrict_name == ss)]])
    return sel.geometry.union_all()


def transform(p, cx, cy):
    """pixel (col, row) of the reduced image -> UTM, similarity about the mask centroid (cx, cy)."""
    tx, ty, ls, th = p
    s = np.exp(ls)
    c, si = np.cos(th) * s, np.sin(th) * s
    # x = tx + c*(col-cx) + si*(row-cy) ; y = ty + si*(col-cx) - c*(row-cy)
    return Affine(c, si, tx - c * cx - si * cy, si, -c, ty - si * cx + c * cy)


def iou(p, mask, poly, cx, cy):
    A = transform(p, cx, cy)
    r = rasterize([(poly, 1)], out_shape=mask.shape, transform=A, dtype="uint8").astype(bool)
    inter = (r & mask).sum(); uni = (r | mask).sum()
    return inter / max(uni, 1)


def fit_one(sheet, shr):
    mask, (W, H) = zoned_mask(RAW / f"{sheet}.jpeg")
    if mask is None:
        return {"sheet": sheet, "ok": False, "note": "no zoned area found"}
    poly = reference(sheet, shr)
    rr, cc = np.nonzero(mask); cy, cx = rr.mean(), cc.mean()
    # priors: the sheets are north-up (north arrow) and printed 44 in wide at 1:25,000, so about
    # 25,000 * 0.0254 * 44 / width metres per full pixel; allow +-12 % scale and +-2 degrees rotation
    s_sheet = 25000 * 0.0254 * 44 / W * RED
    s_area = np.sqrt(poly.area / mask.sum())
    def f(q):
        pen = max(0, abs(np.degrees(q[3])) - 2) ** 2 + 50 * max(0, abs(q[2] - np.log(s_sheet)) - np.log(1.12)) ** 2
        return -iou(q, mask, poly, cx, cy) + pen
    best = None
    for s0 in (s_sheet, s_area):
        for dx, dy in ((0, 0), (1500, 0), (-1500, 0), (0, 1500), (0, -1500)):
            q0 = np.array([poly.centroid.x + dx, poly.centroid.y + dy, np.log(s0), 0.0])
            r = minimize(f, q0, method="Nelder-Mead", options={"xatol": 1e-4, "fatol": 1e-5, "maxiter": 800})
            if best is None or r.fun < best.fun:
                best = r
    p = best.x; A = transform(p, cx, cy)
    r = rasterize([(poly, 1)], out_shape=mask.shape, transform=A, dtype="uint8").astype(bool)
    # outline distance: mean distance (m) from the mask edge to the reference edge
    edge = lambda b: b & ~binary_erosion(b)
    de = distance_transform_edt(~edge(r)) * np.exp(p[2])
    out_d = float(de[edge(mask)].mean())
    # full-resolution pixel -> UTM: scale the reduced-image affine by RED
    Afull = A * Affine.scale(1 / RED)
    ov = np.zeros(mask.shape + (3,), np.uint8); ov[mask] = (255, 160, 0); ov[r & ~mask] = (0, 120, 255); ov[r & mask] = (60, 170, 60)
    Image.fromarray(ov).save(OUT / f"georef_{sheet}.png")
    res = {"sheet": sheet, "ok": True, "IoU": iou(best.x, mask, poly, cx, cy), "m_per_px_sheet": s_sheet / RED, "edge_dist_m": out_d, "m_per_px_full": np.exp(p[2]) / RED,
           "rotation_deg": float(np.degrees(p[3])), "width_px": W, "height_px": H,
           "affine_full": json.dumps(list(Afull)[:6])}
    log(f"{sheet}: IoU {res['IoU']:.3f}, outline distance {out_d:.0f} m, {res['m_per_px_full']:.2f} m/px, rotation {res['rotation_deg']:.2f} deg")
    return res


def main():
    shr = gpd.read_file(ROOT / "data/processed/change/shrid_hmda_census.gpkg", columns=["district_name", "subdistrict_name"]).to_crs(32644)
    sheets = sys.argv[1:] or sorted(MANDALS)
    rows = [fit_one(s, shr) for s in sheets]
    fn = OUT / "georef.csv"
    old = pd.read_csv(fn) if fn.exists() else pd.DataFrame()
    new = pd.DataFrame(rows)
    if len(old):
        new = pd.concat([old[~old.sheet.isin(new.sheet)], new], ignore_index=True)
    new.sort_values("sheet").to_csv(fn, index=False)
    print(new.round(3).to_string(index=False))


if __name__ == "__main__":
    main()
