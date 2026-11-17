"""
Read the zones of the HMDA Master Plan 2031 sheets onto our 20 m grid.

The zones are drawn as coloured hatching on white. Every strongly coloured pixel (saturation > 0.3) of the
sheet (reduced 2 x, about 6.4 m per pixel) is given the nearest reference colour (RGB distance < 45); the
reference colours were read off the legend swatches and the map itself (Bibinagar sheet). Roads, boundary
lines and labels have their own "ignore" colours. Votes are counted in 31 x 31 pixel windows (about 200 m)
and the zone with most votes wins, if the window has enough votes.

Only the sheet's own planning district is kept (its zones are in strong colours; the neighbours are faded):
solid patches of strong colour of at least 0.5 km2 that touch the SHRUG Census mandal (+300 m), within 5 km of it.
Where two sheets overlap, the one with more votes wins.

Zones (codes):
  1 residential (R1-R4, GDPZ)   2 peri-urban       3 commercial          4 manufacturing / work centres
  5 public, semi-public          6 multiple use     7 conservation (agriculture)
  8 protected green (forest, afforestation, recreation, open-space buffer around water bodies)
  9 bio-conservation (GO 111)    10 water bodies    11 special reservations (heritage, defence, others)
  12 settlements (existing villages)                0 none / not read

Usage: python scripts/masterplan/03_zones.py [sheet ...]   (needs 01_georef.py and 02_refine_roads.py)
Output: data/processed/masterplan/zones/<sheet>_20m.tif, check_<sheet>.png; mosaic with 04_mosaic.py
"""
import sys, json, time
from pathlib import Path
import numpy as np, pandas as pd, geopandas as gpd, rasterio
from PIL import Image
from scipy.ndimage import uniform_filter, binary_closing, binary_fill_holes, label
from scipy.spatial import cKDTree
from rasterio.features import rasterize
from rasterio.transform import from_origin
from affine import Affine

Image.MAX_IMAGE_PIXELS = None
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).parent))
import importlib.util as iu
_s = iu.spec_from_file_location("g1", Path(__file__).parent / "01_georef.py"); G1 = iu.module_from_spec(_s); _s.loader.exec_module(G1)
RAW = ROOT / "data/raw/masterplan_hmda2031"
OUT = ROOT / "data/processed/masterplan"; ZD = OUT / "zones"; ZD.mkdir(parents=True, exist_ok=True)
RED, WIN, MINV = 2, 31, 0.012
# 20 m grid of the land-use maps
GX0, GY1, NX, NY = 180000.0, 1984000.0, 5400, 5600
NAMES = {1: "residential", 2: "peri-urban", 3: "commercial", 4: "manufacturing", 5: "public / semi-public",
         6: "multiple use", 7: "conservation (agriculture)", 8: "protected green", 9: "bio-conservation (GO 111)",
         10: "water bodies", 11: "special reservations", 12: "settlements"}
REF = [  # (zone code or -1 = ignore, RGB)
    (1, (248, 168, 8)), (1, (248, 168, 24)), (1, (244, 171, 38)), (1, (231, 182, 95)), (1, (226, 184, 88)),
    (2, (232, 200, 40)), (2, (216, 200, 40)), (2, (216, 200, 56)),
    (3, (16, 90, 198)), (3, (12, 84, 204)),
    (4, (136, 24, 184)), (4, (104, 8, 136)), (4, (130, 66, 150)),
    (5, (216, 81, 64)), (5, (200, 75, 62)), (5, (194, 39, 42)),
    (6, (227, 132, 176)), (6, (209, 134, 171)),
    (7, (173, 201, 109)), (7, (180, 204, 108)),
    (8, (41, 109, 13)), (8, (36, 108, 12)), (8, (82, 109, 28)), (8, (124, 168, 90)), (8, (125, 172, 97)),
    (9, (139, 164, 74)), (9, (108, 156, 36)),
    (10, (113, 176, 186)), (10, (108, 156, 180)), (10, (80, 190, 230)),
    (11, (196, 169, 112)), (11, (166, 140, 89)), (11, (194, 169, 117)),
    (-1, (232, 8, 8)), (-1, (200, 20, 20)), (-1, (140, 20, 20)), (-1, (150, 110, 30)), (-1, (170, 120, 40)),
    (-1, (64, 208, 176)), (-1, (40, 190, 160)),
    # sampled on Bibinagar: HUDA boundary (teal), village / mandal boundary dots (brown), rural roads (dark red)
    (-1, (8, 232, 168)), (-1, (24, 216, 168)), (-1, (72, 200, 168)), (-1, (104, 200, 168)),
    (-1, (168, 120, 8)), (-1, (168, 104, 8)), (-1, (152, 104, 24)), (-1, (152, 120, 40)),
    (-1, (136, 8, 8)), (-1, (120, 24, 24)), (-1, (136, 24, 24)),
]
# Low-resolution copies are calibrated on their own legend swatches (the blur shifts every colour):
# swatch x range and row centres (full-resolution pixels), read off the enlarged legend.
LEGEND = {"Ibrahimpatnam_Manchal": {"x": (3643, 3677), "rows": {
    1: [484, 508, 532, 556, 923], 2: [620], 3: [660], 4: [699, 723], 5: [762, 787, 811], 6: [850, 875, 899],
    # 8 uses the forest swatch only: the recreation, open-space and afforestation swatches are dotted, so blurred they look like conservation
    8: [1090], 10: [1050], 11: [1129, 1153, 1202], 9: [1178], 7: [1241]}}}


def sheet_refs(sh, A_full):
    """(code, rgb) references from a sheet's own legend: the 4 most common saturated colours of each swatch."""
    L = LEGEND[sh]; x0, x1 = L["x"]; out = []
    for code, ys in L["rows"].items():
        for y in ys:
            b = A_full[y - 7:y + 7, x0:x1].reshape(-1, 3).astype(int)
            mx, mn = b.max(1), b.min(1); s = (mx - mn) / (mx + 1e-6); b = b[s > 0.15]
            if len(b) < 10:
                continue
            q = (b // 12) * 12 + 6; u, c = np.unique(q, axis=0, return_counts=True)
            for i in np.argsort(-c)[:4]:
                v = u[i]; sv = (v.max() - v.min()) / v.max()
                if sv >= 0.2:                            # drop the near-white tint of the swatch
                    out.append((code, tuple(v)))
    return out + [r for r in REF if r[0] == -1]


# zones whose colours also occur in thin lines need a denser window before they count
MIN_SHARE = {5: 0.02, 11: 0.03, 12: 0.10}
GREY = (12, (128, 128, 128))
COL = {0: (255, 255, 255), 1: (250, 170, 30), 2: (235, 220, 60), 3: (30, 90, 210), 4: (140, 40, 180), 5: (220, 60, 50),
       6: (240, 130, 190), 7: (180, 215, 110), 8: (30, 120, 30), 9: (110, 160, 40), 10: (90, 180, 230), 11: (170, 140, 90),
       12: (120, 120, 120)}
log = lambda *a: print(time.strftime("%H:%M:%S"), *a, flush=True)


def classify(fn, m_per_px):
    im = Image.open(fn).convert("RGB")
    refs, smin, dmax = REF, 0.3, 45
    if fn.stem in LEGEND:
        refs, smin, dmax = sheet_refs(fn.stem, np.asarray(im)), 0.15, 35
    red = RED if im.size[0] > 6000 else 1          # low-resolution copies are used as they are
    win = int(round((500 if fn.stem in LEGEND else 200) / (m_per_px * red))) | 1   # about 200 m (500 m on blurred copies: moire)
    a = np.asarray(im.reduce(red)).astype(np.float32)
    mx, mn = a.max(2), a.min(2); sat = (mx - mn) / (mx + 1e-6)
    codes = np.array([c for c, _ in refs]); t = cKDTree(np.array([rgb for _, rgb in refs], np.float32))
    strong = (sat > smin) & (mx > 40)
    d, i = t.query(a[strong], distance_upper_bound=dmax)
    lab = np.zeros(sat.shape, np.int8); lab[strong] = np.where(np.isfinite(d), codes[np.minimum(i, len(codes) - 1)], 0)
    grey = (sat < 0.05) & (mx > 110) & (mx < 145)          # settlement blocks; anti-aliased black lines are sparser
    lab[grey] = 12
    votes = np.stack([uniform_filter((lab == k).astype(np.float32), win) for k in range(1, 13)])
    ms = {**MIN_SHARE, **({5: 0.06} if fn.stem in LEGEND else {})}   # blurred red roads look like public / semi-public
    for k, m in ms.items():
        votes[k - 1][votes[k - 1] < m] = 0
    best = votes.argmax(0) + 1; vmax = votes.max(0)
    best[vmax < MINV] = 0
    best[:, int(0.855 * best.shape[1]):] = 0
    return best.astype(np.uint8), vmax, red


def main():
    shr = gpd.read_file(ROOT / "data/processed/change/shrid_hmda_census.gpkg", columns=["district_name", "subdistrict_name"]).to_crs(32644)
    gr = pd.read_csv(OUT / "georef_roads.csv").set_index("sheet")
    sheets = sys.argv[1:] or list(gr.index)
    gt = from_origin(GX0, GY1, 20, 20)
    cx = GX0 + (np.arange(NX) + 0.5) * 20; cy = GY1 - (np.arange(NY) + 0.5) * 20
    for sh in sheets:
        A = Affine(*json.loads(gr.loc[sh, "affine_full"]))            # full pixel -> UTM
        mpp = float(gr.loc[sh, "m_per_px"])
        z, v, red = classify(RAW / f"{sh}.jpeg", mpp)
        # the sheet's own zoned area: solid patches of strong colour (>= 0.5 km2) that touch the Census mandal.
        # The Census outline itself is only a guide: the planning district often differs from it (Faruqnagar,
        # Hatnura, Ghatkesar, Kisara, Yacharam), and clipping to it threw away real zones.
        ref = G1.reference(sh, shr)
        pin = rasterize([(ref.buffer(300), 1)], z.shape, transform=A * Affine.scale(red), dtype="uint8").astype(bool)
        px_m = mpp * red
        own = binary_fill_holes(binary_closing(z > 0, iterations=max(1, int(60 / px_m))))
        lab_, n_ = label(own)
        keep = np.zeros(n_ + 1, bool)
        sz = np.bincount(lab_.ravel(), minlength=n_ + 1); hit = np.bincount(lab_[pin], minlength=n_ + 1)
        keep[(sz * px_m ** 2 >= 0.5e6) & (hit > 0)] = True; keep[0] = False
        z = np.where(keep[lab_], z, 0).astype(np.uint8)
        poly = ref.buffer(5000)
        inside = rasterize([(poly, 1)], (NY, NX), transform=gt, dtype="uint8").astype(bool)
        rr, cc = np.nonzero(inside)
        Ai = ~A                                                         # UTM -> full pixel
        col, row = Ai * (cx[cc], cy[rr])
        c2 = (np.asarray(col) / red).astype(int); r2 = (np.asarray(row) / red).astype(int)
        ok = (c2 >= 0) & (c2 < z.shape[1]) & (r2 >= 0) & (r2 < z.shape[0])
        Z = np.zeros((NY, NX), np.uint8); V = np.zeros((NY, NX), np.float32)
        Z[rr[ok], cc[ok]] = z[r2[ok], c2[ok]]; V[rr[ok], cc[ok]] = v[r2[ok], c2[ok]]
        prof = dict(driver="GTiff", height=NY, width=NX, count=2, dtype="float32", crs="EPSG:32644", transform=gt, compress="deflate")
        with rasterio.open(ZD / f"{sh}_20m.tif", "w", **prof) as o:
            o.write(Z.astype(np.float32), 1); o.write(V, 2)
        rd = Z > 0; share = {NAMES[k]: (Z[rd] == k).mean() for k in NAMES}
        log(f"{sh}: zoned area {rd.sum() * 4e-4:.0f} km2 (Census mandal {ref.area / 1e6:.0f} km2); "
            + ", ".join(f"{k} {s:.0%}" for k, s in share.items() if s >= 0.02))
        # check picture: sheet (reduced) next to the zone colours, same pixels
        small = Image.open(RAW / f"{sh}.jpeg").convert("RGB").reduce(8)
        zz = np.array(Image.fromarray(z).resize(small.size, Image.NEAREST))
        pal = np.array([COL[k] for k in range(13)], np.uint8)
        both = np.concatenate([np.asarray(small), pal[zz]], 1)
        Image.fromarray(both).save(ZD / f"check_{sh}.png")


if __name__ == "__main__":
    main()
