"""
Trial dataset for the land-use change choice model, 3 assembly constituencies (ACs) with
booth-wise votes from Form 20 (2018 assembly election): 50 Maheshwaram, 51 Rajendranagar,
52 Serilingampally. CHANGE_MODEL_PLAN.md has the design; this is the small trial of it.

Region: 20 m cells inside HMDA whose nearest 2017 polling station (all Telangana stations) is in one
of the three ACs (a Voronoi stand-in for the AC boundaries).

Outcome, per period (2017->2020, 2020->2023), among cells undeveloped at the start
(final map trees/open and Open Buildings cover < 5%):
  1 = confirmed development: map built at the end AND Open Buildings cover >= 20% at the end AND
      3x3-cell cover gain >= 0.10
  0 = still undeveloped by both sources (map trees/open, cover < 5%, gain < 0.02)
  cells where the two sources disagree are left out (counted in the log).

Sample (choice-based, CHANGE_MODEL_PLAN.md §3): at most one cell per 200 m block for each outcome;
all changers (cap CAP_1) plus non-changers up to N_PER_PERIOD cells per period. Sampling weights
(population share / sample share) are stored for weighted estimation and the intercept correction.

Booth population: total votes polled per booth, 2018 (01_form20_ocr.py). Booths are placed on the
2017 polling-station coordinates (Rudkin scrape of psleci.nic.in, April 2017). The booth list was
renumbered between 2017 and 2018 (e.g. Rajendranagar 317 -> 441 booths) and no 2018 list with names
is openly available, so 2018 booth k is placed at 2017 booth round(k * N2017 / N2018): booth numbers
run in geographic order, so this puts each 2018 booth at or near its locality. SHIFT (env) moves the
alignment by a number of 2017 booths, for the sensitivity check. Surface: Gaussian kernel density of
votes (votes per km2) with sigma 1 km and 2 km.

Factors, all measured at the start year of the period (CHANGE_MODEL_PLAN.md §4):
  distances (km) to airport, nearest ORR interchange, nearest open metro station, HITEC/Financial
  District, old CBD, nearest major road (20_proximity.py); all-road km in the 4 x 4 km window (OSM
  Geofabrik snapshot at the start year); built share (final map) and Open Buildings cover in the
  1 km window; WorldPop people per km2 (1 km window); start class trees vs open; AC.

Usage: python 02_trial_data.py            (env SHIFT=<n> for the alignment sensitivity)
       REGION=hmda python 02_trial_data.py   (all of HMDA: no booth votes, larger sample, district per cell)
Output: data/processed/change/trial_cells.parquet (one row per sampled cell and period)
        data/processed/change/hmda_cells.parquet (REGION=hmda)
"""
import os, sys, json, time
from pathlib import Path
import numpy as np, pandas as pd, geopandas as gpd, rasterio, pyogrio
from rasterio.features import rasterize
from rasterio.transform import from_origin
from scipy.spatial import cKDTree
from scipy.ndimage import uniform_filter, maximum_filter
from pyproj import Transformer

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "lu"))
import importlib.util as iu
_s = iu.spec_from_file_location("px", ROOT / "scripts/lu/20_proximity.py"); px = iu.module_from_spec(_s); _s.loader.exec_module(px)

CH = ROOT / "data" / "processed" / "change"
G = ROOT / "data" / "raw" / "lu" / "lu20"
MAPS = ROOT / "outputs" / "lu20" / "maps_final"
ACS = {50: "Maheshwaram", 51: "Rajendranagar", 52: "Serilingampally"}
PERIODS = [(2017, 2020), (2020, 2023)]
SNAP = {2017: "india-180101.osm.pbf", 2020: "india-210101.osm.pbf"}       # OSM as of 1 Jan of the next year
ROADS = ["motorway", "trunk", "primary", "secondary", "tertiary", "unclassified", "residential", "living_street",
         "motorway_link", "trunk_link", "primary_link", "secondary_link", "tertiary_link"]
N_PER_PERIOD, CAP_1, BLOCK = 10000, 4000, 10          # BLOCK cells = 200 m
SHIFT = int(os.environ.get("SHIFT", "0"))
SEED = 20261105
REGION = os.environ.get("REGION", "trial")     # trial: ACs 50-52 with booth votes; hmda: all of HMDA, no votes
HMDA = REGION == "hmda"
OUTCOME = os.environ.get("OUTCOME", "both")   # both: map + Open Buildings agree (#45); persist: map built in t1-1 and t1 (#53)
PERSIST = OUTCOME == "persist"
TAG = ("hmda" if HMDA else "trial") + ("_persist" if PERSIST else "")
if HMDA:
    N_PER_PERIOD, CAP_1 = 60000, 30000       # HMDA is 6.6 x the trial area
CELL = 20
log = lambda *a: print(time.strftime("%H:%M:%S"), *a, flush=True)


def booths(need_votes=True):
    """2017 polling stations (all Telangana) and 2018 votes placed on them."""
    h = ["State", "District", "AC", "Latitude", "Longitude", "PSNumber", "PSName", "WebURL"]
    r = pd.read_csv(ROOT / "data/raw/voter/rudkin/telangana.csv", header=None, names=h, engine="python", on_bad_lines="skip")
    r["ac"] = r.WebURL.str.extract(r"A=(\d+)")[0].astype(int)
    r = r.drop_duplicates(["ac", "PSNumber"]).dropna(subset=["Latitude", "Longitude"])
    r = r[(r.Latitude.between(15, 20)) & (r.Longitude.between(77, 82))]
    r["x"], r["y"] = Transformer.from_crs(4326, 32644, always_xy=True).transform(r.Longitude.values, r.Latitude.values)
    r = r.reset_index(drop=True)
    if not need_votes:
        return r, None
    v = pd.read_csv(CH / "form20_2018.csv")
    out = []
    for ac in ACS:
        b17 = r[r.ac == ac].sort_values("PSNumber").reset_index(drop=True)
        b18 = v[v.ac == ac].set_index("booth").total
        n18 = int(b18.index.max()); n17 = len(b17)
        b18 = b18.reindex(range(1, n18 + 1)).fillna(b18.median())            # unread booths: AC median
        k17 = np.clip(np.round((np.arange(1, n18 + 1) - 0.5) * n17 / n18 + 0.5).astype(int) + SHIFT, 1, n17) - 1
        out.append(pd.DataFrame({"ac": ac, "booth18": np.arange(1, n18 + 1), "votes": b18.values,
                                 "x": b17.x.values[k17], "y": b17.y.values[k17]}))
        log(f"AC {ac}: {n18} booths 2018 on {n17} stations 2017 ({b17[['x', 'y']].drop_duplicates().shape[0]} distinct "
            f"locations), {b18.sum():,.0f} votes")
    return r, pd.concat(out, ignore_index=True)


def kde(bx, by, w, X, Y, sigma):
    """Gaussian kernel density of booth votes at points X, Y (votes per km2)."""
    t = cKDTree(np.c_[bx, by]); out = np.zeros(len(X))
    for i, nb in enumerate(t.query_ball_point(np.c_[X, Y], 4 * sigma)):
        if nb:
            d2 = (bx[nb] - X[i]) ** 2 + (by[nb] - Y[i]) ** 2
            out[i] = (w[nb] * np.exp(-d2 / (2 * sigma ** 2))).sum() / (2 * np.pi * (sigma / 1000) ** 2)
    return out


def main():
    allb, vb = booths(need_votes=not HMDA)
    meta = json.loads((G / "grid_2020" / "meta.json").read_text())
    X0, Y1 = meta["minx"], meta["maxy"]
    if HMDA:
        r0, r1, c0, c1 = 0, meta["ny"], 0, meta["nx"]
    else:
        reg = allb[allb.ac.isin(ACS)]
        pad = 6000
        c0 = int((reg.x.min() - pad - X0) // CELL); c1 = int((reg.x.max() + pad - X0) // CELL)
        r0 = int((Y1 - reg.y.max() - pad) // CELL); r1 = int((Y1 - reg.y.min() + pad) // CELL)
        c0, r0 = max(c0, 0), max(r0, 0); c1, r1 = min(c1, meta["nx"]), min(r1, meta["ny"])
    ny, nx = r1 - r0, c1 - c0
    tr = from_origin(X0 + c0 * CELL, Y1 - r0 * CELL, CELL, CELL)
    cx = X0 + (np.arange(c0, c1) + 0.5) * CELL; cy = Y1 - (np.arange(r0, r1) + 0.5) * CELL
    XX, YY = np.meshgrid(cx, cy)
    log(f"window rows {r0}-{r1}, cols {c0}-{c1} ({ny} x {nx} cells)")

    # region: nearest 2017 station is in one of the ACs, inside HMDA
    _, k = cKDTree(np.c_[allb.x, allb.y]).query(np.c_[XX.ravel(), YY.ravel()], workers=8)
    kk = k.reshape(ny, nx); del k
    ac_of = allb.ac.values[kk]
    aoi = gpd.read_file(ROOT / "data/processed/aoi_utm44n.gpkg").to_crs(32644)
    inside = rasterize(((g, 1) for g in aoi.geometry), (ny, nx), transform=tr, dtype="uint8").astype(bool)
    if HMDA:
        region = inside
        log(f"region {region.sum():,} cells = {region.sum() * CELL ** 2 / 1e6:.0f} km2 (all of HMDA)")
    else:
        region = np.isin(ac_of, list(ACS)) & inside
        log(f"region {region.sum():,} cells = {region.sum() * CELL ** 2 / 1e6:.0f} km2; "
            + ", ".join(f"{ACS[a]} {(ac_of[region] == a).sum() * CELL ** 2 / 1e6:.0f} km2" for a in ACS))

    def rd(y):
        with rasterio.open(MAPS / f"landuse_{y}_20m.tif") as s:
            return s.read(1, window=((r0, r1), (c0, c1)))

    def cov(y):
        a = np.array(np.load(G / f"grid_{y}" / "mean.npy", mmap_mode="r")[7, r0:r1, c0:c1], dtype=np.float32)
        # outside HMDA the grid is NaN, and uniform_filter carries a NaN along the whole row: 0 there (HMDA run only,
        # the trial window has no NaN rows, so the trial is unchanged)
        return np.nan_to_num(a, nan=0.0) if HMDA else a

    P = px.Prox(years=("2017", "2020"))
    wp = {}
    for y in (2017, 2020):
        with rasterio.open(ROOT / f"outputs/lu20/worldpop/worldpop_{y}.tif") as s:
            a = s.read(1).astype(np.float32); a[~np.isfinite(a) | (a < 0)] = 0
        wp[y] = uniform_filter(a, 11, mode="constant") * 100          # people per km2 in an 1.1 km window (100 m cells)
    rng = np.random.default_rng(SEED)
    rows = []
    for a, b in PERIODS:
        ma, mb, ca, cb = rd(a), rd(b), cov(a), cov(b)
        c3a, c3b = uniform_filter(ca, 3), uniform_filter(cb, 3)
        und = region & np.isin(ma, [4, 5]) & (ca < 0.05)
        if PERSIST:     # built in the last two years of the period; unchanged = undeveloped in both, and no
                        # new building in Open Buildings either (#53)
            mp = rd(b - 1)
            y1 = und & np.isin(mp, [1, 2]) & np.isin(mb, [1, 2])
            y0 = und & np.isin(mp, [4, 5]) & np.isin(mb, [4, 5]) & ~((cb >= 0.20) & (c3b - c3a >= 0.10))
        else:
            y1 = und & np.isin(mb, [1, 2]) & (cb >= 0.20) & (c3b - c3a >= 0.10)
            y0 = und & np.isin(mb, [4, 5]) & (cb < 0.05) & (c3b - c3a < 0.02)
        log(f"{a}->{b}: undeveloped at start {und.sum():,}; confirmed change {y1.sum():,} ({y1.sum() / und.sum():.2%}); "
            f"still undeveloped {y0.sum():,}; sources disagree, left out {(und & ~y0 & ~y1).sum():,}")

        # one cell per 200 m block for each outcome, random within the block
        blk = (np.arange(ny)[:, None] // BLOCK) * (nx // BLOCK + 1) + np.arange(nx)[None, :] // BLOCK
        pick = {}
        for lab, m in ((1, y1), (0, y0)):
            idx = np.flatnonzero(m.ravel()); idx = rng.permutation(idx)
            _, first = np.unique(blk.ravel()[idx], return_index=True)
            pick[lab] = idx[first]
        n1 = min(len(pick[1]), CAP_1); s1 = rng.choice(pick[1], n1, replace=False)
        n0 = min(len(pick[0]), N_PER_PERIOD - n1); s0 = rng.choice(pick[0], n0, replace=False)
        idx = np.r_[s1, s0]; lab = np.r_[np.ones(n1, int), np.zeros(n0, int)]
        pop1, pop0 = y1.sum(), y0.sum()
        w = np.where(lab == 1, (pop1 / (pop1 + pop0)) / (n1 / len(idx)), (pop0 / (pop1 + pop0)) / (n0 / len(idx)))
        rr, cc = np.unravel_index(idx, (ny, nx))
        X, Y = cx[cc], cy[rr]
        d = pd.DataFrame({"period": f"{a}-{b}", "t0": a, "x": X, "y": Y, "change": lab, "w": w,
                          "ac": ac_of[rr, cc], "trees_t0": (ma[rr, cc] == 4).astype(int)})
        d["district"] = allb.District.str.strip().values[kk[rr, cc]]     # pre-2016 district of the nearest station
        d["tile"] = ((X - X0) // 4000).astype(int) * 1000 + ((Y1 - Y) // 4000).astype(int)

        dist = P.at(X, Y)
        d["d_airport"] = dist.d_airport_rgia; d["d_orr"] = dist.d_orr_access; d["d_metro"] = dist[f"d_metro_{a}"]
        d["d_jobs"] = dist.d_employment; d["d_cbd"] = dist.d_cbd_abids; d["d_major_road"] = dist[f"d_major_road_{a}"]

        built = np.isin(ma, [1, 2]).astype(np.float32)
        d["built_1km"] = uniform_filter(built, 51, mode="constant")[rr, cc]
        d["obcov_1km"] = uniform_filter(ca, 51, mode="constant")[rr, cc]
        bbox = tuple(gpd.GeoSeries.from_xy([cx[0], cx[-1]], [cy[-1], cy[0]], crs=32644).to_crs(4326).total_bounds)
        q = ",".join(f"'{h}'" for h in ROADS)
        t = time.time()
        rl = pyogrio.read_dataframe(ROOT / "data/raw/osm_snapshots" / SNAP[a], layer="lines", bbox=bbox,
                                    where=f"highway IN ({q})", columns=["highway"]).to_crs(32644)
        road = rasterize(((g, 1) for g in rl.geometry), (ny, nx), transform=tr, dtype="uint8")
        d["road_km_4km"] = (uniform_filter(road.astype(np.float32), 201, mode="constant") * 201 ** 2 * CELL / 1000)[rr, cc]
        log(f"  roads {SNAP[a]}: {len(rl):,} lines, {road.sum() * CELL / 1000:,.0f} km in the window ({time.time() - t:.0f}s)")

        wr = ((Y1 - Y) // 100).astype(int); wc = ((X - X0) // 100).astype(int)
        d["worldpop_1km"] = wp[a][wr, wc]
        if not HMDA:        # booth votes exist for the three trial ACs only
            # votes come from the three ACs only, so the density is too low near the region edge
            out_b = allb[~allb.ac.isin(ACS)]
            d["d_edge"] = cKDTree(np.c_[out_b.x, out_b.y]).query(np.c_[X, Y])[0] / 1000
            for sg in (1000, 2000):
                d[f"votes_kde{sg // 1000}km"] = kde(vb.x.values, vb.y.values, vb.votes.values, X, Y, sg)
        rows.append(d)
        log(f"  sample: {n1:,} changers, {n0:,} non-changers")
    out = pd.concat(rows, ignore_index=True)
    fn = CH / (f"{TAG}_cells.parquet" if SHIFT == 0 else f"{TAG}_cells_shift{SHIFT}.parquet")
    out.to_parquet(fn)
    log(f"wrote {fn} ({len(out):,} rows)")


if __name__ == "__main__":
    main()
