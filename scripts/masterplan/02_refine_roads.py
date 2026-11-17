"""
Refine the georeferencing of the master-plan sheets by matching their road lines to OSM.

01_georef.py fits each sheet to the Census mandal outline (accuracy roughly 0.5-1.5 km). Roads are far more
precise: the sheets draw national/state highways and major roads in red / dark red, which are extracted
(R > 110, G < 80, B < 80, R - G > 70) and matched to the OSM road network of 1 Jan 2021 (motorway ...
unclassified) plus the HMDA boundary (drawn in the same red), by chamfer matching: minimise the mean distance from each red pixel to the nearest OSM road
(capped at 250 m so that red zone hatching and roads missing from OSM do not dominate).

Transform: similarity (shift, scale, rotation), then a full affine as a check. Search: a 9 x 9 grid of shifts
(+-4 km) around the 01 fit at the sheet scale prior, then Nelder-Mead from the best few.

Usage: python scripts/masterplan/02_refine_roads.py [sheet ...]
Output: data/processed/masterplan/georef_roads.csv, roads_<sheet>.png (red pixels on OSM roads, for checking)
"""
import sys, json, time
from pathlib import Path
import numpy as np, pandas as pd, geopandas as gpd, pyogrio
from PIL import Image
from scipy.ndimage import distance_transform_edt
from scipy.optimize import minimize
from rasterio.features import rasterize
from rasterio.transform import from_origin

Image.MAX_IMAGE_PIXELS = None
ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data/raw/masterplan_hmda2031"
OUT = ROOT / "data/processed/masterplan"
RED = 4
X0, Y1, RES, NX, NY = 160000.0, 2004000.0, 20.0, 6400, 6600       # 20 m grid, HMDA + 20 km
CAP = 250.0
log = lambda *a: print(time.strftime("%H:%M:%S"), *a, flush=True)


def osm_distance():
    fn = OUT / "osm_road_hmda_distance_20m.npy"
    if fn.exists():
        return np.load(fn)
    gfn = OUT / "osm_roads_2021.gpkg"
    if not gfn.exists():
        x1, y0 = X0 + NX * RES, Y1 - NY * RES
        bbox = tuple(gpd.GeoSeries.from_xy([X0, x1], [y0, Y1], crs=32644).to_crs(4326).total_bounds)
        cl = ["motorway", "trunk", "primary", "secondary", "tertiary", "unclassified", "motorway_link", "trunk_link",
              "primary_link", "secondary_link", "tertiary_link"]
        q = ",".join(f"'{h}'" for h in cl)
        g = pyogrio.read_dataframe(ROOT / "data/raw/osm_snapshots/india-210101.osm.pbf", layer="lines", bbox=bbox,
                                   where=f"highway IN ({q})", columns=["highway"]).to_crs(32644)
        g.to_file(gfn); log(f"OSM roads: {len(g):,} lines")
    g = gpd.read_file(gfn)
    # the sheets draw the HMDA boundary in the same red as the roads: add it to the reference
    aoi = gpd.read_file(ROOT / "data/processed/aoi_utm44n.gpkg").to_crs(32644).boundary
    geoms = list(g.geometry) + list(aoi.geometry)
    r = rasterize(((geom, 1) for geom in geoms), (NY, NX), transform=from_origin(X0, Y1, RES, RES), dtype="uint8")
    d = (distance_transform_edt(r == 0) * RES).astype(np.float32)
    np.save(fn, d); return d


def red_pixels(fn):
    im = Image.open(fn).convert("RGB")
    red = RED if im.size[0] > 6000 else 1          # low-resolution copies (e.g. Ibrahimpatnam_Manchal, 4032 px wide)
    a = np.asarray(im.reduce(red)).astype(np.int16)
    R, G, B = a[..., 0], a[..., 1], a[..., 2]
    if red == 1:        # blurred low-resolution copy: roads come out lighter
        m = (R > 150) & (G < 120) & (B < 120) & (R - G > 80)
    else:
        m = (R > 110) & (G < 80) & (B < 80) & (R - G > 70)
    m[:, int(0.855 * m.shape[1]):] = False
    rr, cc = np.nonzero(m)
    return np.c_[cc, rr].astype(np.float64) * red + red / 2, m       # full-resolution pixel coordinates


def apply(p, px, c0):
    """similarity about the pixel centre c0: p = (tx, ty, log m/px, theta)."""
    tx, ty, ls, th = p; s = np.exp(ls); c, si = np.cos(th) * s, np.sin(th) * s
    dx, dy = px[:, 0] - c0[0], px[:, 1] - c0[1]
    return tx + c * dx + si * dy, ty + si * dx - c * dy


def cost(xy, D):
    c = ((xy[0] - X0) / RES).astype(int); r = ((Y1 - xy[1]) / RES).astype(int)
    ok = (c >= 0) & (c < NX) & (r >= 0) & (r < NY)
    d = np.full(len(c), CAP); d[ok] = np.minimum(D[r[ok], c[ok]], CAP)
    return d.mean(), (d < 40).mean()


def refine(sheet, g01, D):
    row = g01[g01.sheet == sheet].iloc[0]
    A = json.loads(row.affine_full)                     # x = a*col + b*row + c ; y = d*col + e*row + f
    px, m = red_pixels(RAW / f"{sheet}.jpeg")
    rng = np.random.default_rng(0)
    if len(px) > 60000:
        px = px[rng.choice(len(px), 60000, replace=False)]
    c0 = px.mean(0)
    x0 = A[0] * c0[0] + A[1] * c0[1] + A[2]; y0 = A[3] * c0[0] + A[4] * c0[1] + A[5]
    s_prior = row.m_per_px_sheet
    f = lambda p: cost(apply(p, px, c0), D)[0]
    start = f(np.array([x0, y0, np.log(row.m_per_px_full), np.arctan2(A[3], A[0])]))
    # exhaustive search over the shift (+-10 km, 250 m steps) at the true scale: every good fit lands on
    # 3.175 m/px (200 dpi at 1:25,000); 6.35 m/px (1:50,000) is tried as well. Then Nelder-Mead on all 4.
    sub = px[rng.choice(len(px), min(len(px), 15000), replace=False)]
    g = lambda p: cost(apply(p, sub, c0), D)[0]
    cands = []
    W = Image.open(RAW / f"{sheet}.jpeg").size[0]
    # 200 dpi at 1:25,000, 1:50,000, or the printed sheet widths (44, 48, 56 in) for low-resolution copies
    for s in ((3.175, 6.35) if W > 6000 else tuple(25000 * 0.0254 * w / W for w in (44, 48, 56))):
        span = 10000 if W > 6000 else 15000
        for dx in np.arange(-span, span + 1, 250):
            for dy in np.arange(-span, span + 1, 250):
                p = np.array([x0 + dx, y0 + dy, np.log(s), 0.0]); cands.append((g(p), p))
    cands.sort(key=lambda t: t[0])
    best = None
    for _, p in cands[:5]:
        simplex = np.array([p, p + [150, 0, 0, 0], p + [0, 150, 0, 0], p + [0, 0, 0.01, 0], p + [0, 0, 0, 0.005]])
        r = minimize(f, p, method="Nelder-Mead", options={"initial_simplex": simplex, "xatol": 0.5, "fatol": 0.01, "maxiter": 1500})
        if best is None or r.fun < best.fun:
            best = r
    p = best.x; mean_d, inl = cost(apply(p, px, c0), D)
    s, th = np.exp(p[2]), p[3]; c, si = np.cos(th) * s, np.sin(th) * s
    Afull = [c, si, p[0] - c * c0[0] - si * c0[1], si, -c, p[1] - si * c0[0] + c * c0[1]]
    # check picture: OSM distance < 40 m (grey) and the red pixels (red = within 40 m, blue = not)
    xy = apply(p, px, c0)
    res = {"sheet": sheet, "red_px": int(m.sum()), "cost_01": start, "cost_roads": mean_d, "inlier_share": inl,
           "m_per_px": s, "m_per_px_sheet": s_prior, "rotation_deg": float(np.degrees(th)),
           "shift_from_01_m": float(np.hypot(p[0] - x0, p[1] - y0)), "affine_full": json.dumps(Afull)}
    c_ = ((xy[0] - X0) / RES).astype(int); r_ = ((Y1 - xy[1]) / RES).astype(int)
    cmin, cmax, rmin, rmax = c_.min() - 50, c_.max() + 50, r_.min() - 50, r_.max() + 50
    sub = D[max(rmin, 0):rmax, max(cmin, 0):cmax]
    pic = np.full(sub.shape + (3,), 255, np.uint8); pic[sub < 30] = (170, 170, 170)
    ok = (r_ - max(rmin, 0) >= 0) & (r_ - max(rmin, 0) < sub.shape[0]) & (c_ - max(cmin, 0) >= 0) & (c_ - max(cmin, 0) < sub.shape[1])
    dd = np.minimum(D[np.clip(r_, 0, NY - 1), np.clip(c_, 0, NX - 1)], CAP)
    pic[r_[ok] - max(rmin, 0), c_[ok] - max(cmin, 0)] = np.where((dd[ok] < 40)[:, None], [[220, 0, 0]], [[0, 90, 255]])
    Image.fromarray(pic).save(OUT / f"roads_{sheet}.png")
    log(f"{sheet}: mean distance {start:.0f} -> {mean_d:.0f} m, within 40 m {inl:.0%}, {s:.3f} m/px (sheet prior {s_prior:.3f}), "
        f"rotation {res['rotation_deg']:.2f} deg, moved {res['shift_from_01_m']:.0f} m")
    return res


def main():
    D = osm_distance()
    g01 = pd.read_csv(OUT / "georef.csv")
    sheets = sys.argv[1:] or list(g01.sheet)
    rows = [refine(s, g01, D) for s in sheets]
    fn = OUT / "georef_roads.csv"
    old = pd.read_csv(fn) if fn.exists() else pd.DataFrame()
    new = pd.DataFrame(rows)
    if len(old):
        new = pd.concat([old[~old.sheet.isin(new.sheet)], new], ignore_index=True)
    new.sort_values("sheet").to_csv(fn, index=False)
    print(new.drop(columns=["affine_full"]).round(3).to_string(index=False))


if __name__ == "__main__":
    main()
