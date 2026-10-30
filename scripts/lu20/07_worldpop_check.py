"""
Internal plausibility check of the residential / non-residential split against WorldPop population.

Idea: people live in residential buildings. If the map's split is right, then in built-up zones
(1) population follows residential building volume and not non-residential volume, (2) a zone's
people per 1,000 m3 of building falls as the map's non-residential share rises, and (3) fitting
population = a * residential volume + b * non-residential volume gives b far below a.
WorldPop does not know which buildings are residential, so agreement with the split cannot be
copied from it. (It does share some inputs with our model: night lights and built-up extent.)

Built-up zones only (building cover >= 10%): over all zones the rural ones, with almost no
buildings or people, dominate every correlation.

Data: WorldPop Global Project, 100 m unconstrained population counts, 2017 and 2020
(Earth Engine WorldPop/GP/100m/pop; the series ends in 2020). Our 20 m maps from the year models
(outputs/lu20/maps/landuse_<y>_20m_year.tif) and Open Buildings cover x height from the 20 m grid.
Zones: 1 km squares at least 90% inside HMDA (2 km as a check). Intervals: 95%, bootstrap over
12 km blocks.

Usage: python 07_worldpop_check.py
Output: outputs/lu20/worldpop/ (worldpop_<y>.tif, zones_<y>_<km>km.csv, summary.csv, RESULTS_worldpop.md)
"""
import json, io, zipfile, os
import numpy as np, pandas as pd, rasterio, requests
from common20 import *

D = OUT / "worldpop"; D.mkdir(exist_ok=True)
YRS = [2017, 2020]
B = 1000
MIN_COVER = 0.10
BINS = [-1e-9, .2, .4, .6, .8, 1.0001]
LABELS = ["0-20%", "20-40%", "40-60%", "60-80%", "80-100%"]


def worldpop(year, meta):
    fp = D / f"worldpop_{year}.tif"
    if fp.exists():
        return fp
    import ee
    ee.Initialize(project=os.environ.get("EE_PROJECT", "exploringclass"))
    img = (ee.ImageCollection("WorldPop/GP/100m/pop").filter(ee.Filter.eq("country", "IND"))
           .filter(ee.Filter.eq("year", year)).first().select("population").unmask(0))
    nx, ny = meta["nx"] * CELL // 100, meta["ny"] * CELL // 100
    url = img.getDownloadURL({"crs": "EPSG:32644", "crs_transform": [100, 0, meta["minx"], 0, -100, meta["maxy"]],
                              "dimensions": f"{nx}x{ny}", "format": "GEO_TIFF"})
    r = requests.get(url, timeout=600); r.raise_for_status()
    data = r.content
    if data[:2] == b"PK":
        z = zipfile.ZipFile(io.BytesIO(data)); data = z.read(z.namelist()[0])
    fp.write_bytes(data)
    log(f"WorldPop {year}: downloaded {len(data) / 1e6:.1f} MB")
    return fp


def zones(year, km):
    meta = json.loads((W20 / f"grid_{year}" / "meta.json").read_text())
    with rasterio.open(OUT / "maps" / f"landuse_{year}_20m_year.tif") as s:
        cls = s.read(1)
    G = W20 / f"grid_{year}"
    cov = np.nan_to_num(np.load(G / "mean.npy", mmap_mode="r")[BANDS.index("ob_cov")])
    vol = np.nan_to_num(np.load(G / "hw.npy")) * CELL * CELL           # m3 of building per cell (cover x height x area)
    with rasterio.open(worldpop(year, meta)) as s:
        pop = s.read(1).astype(np.float64)
    pop[~np.isfinite(pop) | (pop < 0)] = 0
    k, kp = km * 1000 // CELL, km * 1000 // 100
    ny, nx = cls.shape[0] // k, cls.shape[1] // k
    blk = lambda a, n: a[:ny * n, :nx * n].reshape(ny, n, nx, n).sum((1, 3))
    out = pd.DataFrame({
        "pop": blk(pop, kp).ravel(),
        "inside": (blk((cls > 0).astype(np.float64), k) / (k * k)).ravel(),
        "res_km2": (blk((cls == 1).astype(np.float64), k) * CELL * CELL / 1e6).ravel(),
        "nonres_km2": (blk((cls == 2).astype(np.float64), k) * CELL * CELL / 1e6).ravel(),
        "vol_total": blk(vol, k).ravel(),
        "vol_res": blk(np.where(cls == 1, vol, 0), k).ravel(),
        "vol_nonres": blk(np.where(cls == 2, vol, 0), k).ravel(),
        "cover_share": (blk(cov.astype(np.float64), k) / (k * k)).ravel(),
    })
    r, c = np.divmod(np.arange(ny * nx), nx)
    x = meta["minx"] + (c + 0.5) * km * 1000; y = meta["maxy"] - (r + 0.5) * km * 1000
    out["block"] = np.floor(x / 12000).astype(int) * 1000 + np.floor(y / 12000).astype(int)
    out = out[out.inside >= 0.9].reset_index(drop=True)
    out.to_csv(D / f"zones_{year}_{km}km.csv", index=False)
    return out


def spearman(a, b):
    return pd.Series(np.asarray(a)).rank().corr(pd.Series(np.asarray(b)).rank())


def occupancy(d):
    """pop = a * vol_res + b * vol_nonres, no intercept -> people per 1,000 m3 of each class."""
    X = np.column_stack([d.vol_res.values, d.vol_nonres.values]) / 1000
    return np.linalg.lstsq(X, d["pop"].values, rcond=None)[0]


def binned(d):
    g = d.groupby(pd.cut(d.nonres_share, BINS, labels=LABELS), observed=False)
    return g["pop"].sum() / (g.vol_total.sum() / 1000), g.size()


def analyse(z):
    u = z[z.cover_share >= MIN_COVER].copy()
    u["nonres_share"] = u.vol_nonres / u.vol_total
    u["ppv"] = u["pop"] / (u.vol_total / 1000)
    ub = np.unique(u.block.values); idx = {b: np.nonzero(u.block.values == b)[0] for b in ub}
    rng = np.random.default_rng(0); occ, grad, tb = [], [], []
    for _ in range(B):
        d = u.iloc[np.concatenate([idx[b] for b in rng.choice(ub, len(ub))])]
        occ.append(occupancy(d)); grad.append(spearman(d.ppv, d.nonres_share))
        pb, _ = binned(d); tb.append(pb.iloc[-1] / pb.iloc[0])
    occ = np.array(occ)
    ci = lambda a: (float(np.nanpercentile(a, 2.5)), float(np.nanpercentile(a, 97.5)))
    a, b = occupancy(u); pb, nb = binned(u)
    return dict(n=len(u),
                corr={n: spearman(u["pop"], u[n]) for n in ["vol_total", "vol_res", "vol_nonres", "res_km2", "nonres_km2"]},
                a=(a, *ci(occ[:, 0])), b=(b, *ci(occ[:, 1])), ratio=(b / a, *ci(occ[:, 1] / occ[:, 0])),
                grad=(spearman(u.ppv, u.nonres_share), *ci(grad)), tb=(pb.iloc[-1] / pb.iloc[0], *ci(tb)),
                dens=pd.DataFrame({"zones": nb, "people_per_1000m3": pb}))


def main():
    rep = ["# WorldPop check of the residential / non-residential split (internal)\n",
           "Auto-generated by `scripts/lu20/07_worldpop_check.py`. WorldPop Global Project 100 m population "
           "(unconstrained) for 2017 and 2020, against our 20 m year-model maps and Open Buildings volume "
           f"(cover x height). Zones: 1 km squares at least 90% inside HMDA with at least {MIN_COVER:.0%} building "
           "cover (built-up zones); 2 km as a check. Intervals: 95%, bootstrap over 12 km blocks.\n",
           "**What a correct split predicts:** people live in residential buildings, so (1) population follows "
           "residential volume and not non-residential volume; (2) people per 1,000 m3 of building falls as the map's "
           "non-residential share rises; (3) fitting population = a x residential volume + b x non-residential volume "
           "gives b far below a.\n"]
    rows = []
    for yr in YRS:
        for km in (1, 2):
            r = analyse(zones(yr, km))
            rows.append({"year": yr, "zone": f"{km} km", "zones": r["n"], **{f"rho_{k}": v for k, v in r["corr"].items()},
                         "a_res": r["a"][0], "a_lo": r["a"][1], "a_hi": r["a"][2],
                         "b_nonres": r["b"][0], "b_lo": r["b"][1], "b_hi": r["b"][2],
                         "b_over_a": r["ratio"][0], "b_over_a_lo": r["ratio"][1], "b_over_a_hi": r["ratio"][2],
                         "rho_density_vs_share": r["grad"][0], "rho_lo": r["grad"][1], "rho_hi": r["grad"][2],
                         "top_over_bottom": r["tb"][0], "tb_lo": r["tb"][1], "tb_hi": r["tb"][2]})
            if km == 1:
                rep += [f"## {yr}, 1 km built-up zones (n = {r['n']:,})\n",
                        "| map quantity | Spearman with population |\n|---|---|\n" +
                        "\n".join(f"| {k} | {v:.3f} |" for k, v in r["corr"].items()) + "\n",
                        f"- People per 1,000 m3 implied by WorldPop: residential **{r['a'][0]:.2f}** "
                        f"[{r['a'][1]:.2f}, {r['a'][2]:.2f}], non-residential **{r['b'][0]:.2f}** "
                        f"[{r['b'][1]:.2f}, {r['b'][2]:.2f}]; non-res / res = {r['ratio'][0]:.2f} "
                        f"[{r['ratio'][1]:.2f}, {r['ratio'][2]:.2f}].",
                        f"- Spearman of people per 1,000 m3 with the non-residential share: {r['grad'][0]:+.3f} "
                        f"[{r['grad'][1]:+.3f}, {r['grad'][2]:+.3f}]. The most non-residential zones (80-100%) hold "
                        f"{r['tb'][0]:.2f} [{r['tb'][1]:.2f}, {r['tb'][2]:.2f}] times the people per 1,000 m3 of the "
                        "most residential zones (0-20%).\n",
                        "| non-res share of volume | zones | people per 1,000 m3 |\n|---|---|---|\n" +
                        "\n".join(f"| {i} | {int(v.zones)} | {v.people_per_1000m3:.2f} |" for i, v in r["dens"].iterrows()) + "\n"]
    t = pd.DataFrame(rows); t.to_csv(D / "summary.csv", index=False)
    rep += ["## All runs\n",
            "| year | zone | zones | rho res vol | rho non-res vol | people/1,000 m3 res | non-res | non-res / res [95%] |\n"
            "|---|---|---|---|---|---|---|---|\n" +
            "\n".join(f"| {r.year} | {r.zone} | {r.zones:,} | {r.rho_vol_res:.2f} | {r.rho_vol_nonres:.2f} | {r.a_res:.2f} | "
                      f"{r.b_nonres:.2f} | {r.b_over_a:.2f} [{r.b_over_a_lo:.2f}, {r.b_over_a_hi:.2f}] |" for _, r in t.iterrows()) + "\n",
            "## Caveats\n",
            "- WorldPop is a model, not a census: it spreads 2011-census counts with covariates that include night "
            "lights and built-up extent, which our model also uses. It has no residential / non-residential "
            "information, so agreement with the split is not inherited from it.\n",
            "- WorldPop counts where people live. Mixed-use buildings (shops below, homes above) are often mapped "
            "non-residential and do house people, and the map's non-residential precision is about 0.35, so b is "
            "not expected to be zero.\n",
            "- WorldPop ends in 2020, so the 2023 map is not checked here.\n",
            "- Zone totals only, not pixel accuracy; the hand-labelled sample stays the accuracy statement.\n"]
    (D / "RESULTS_worldpop.md").write_text("\n".join(rep), encoding="utf-8")
    pd.set_option("display.width", 250)
    log("\n" + t.round(3).to_string(index=False))


if __name__ == "__main__":
    main()
