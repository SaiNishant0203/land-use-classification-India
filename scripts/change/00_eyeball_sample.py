"""
Eyeball check of the change definition (docs/archive/CHANGE_MODEL_PLAN_2026-11-02.md §2), 60 pixels to look at in
Google Earth Pro historical imagery.

Question: when the 20 m year map says undeveloped -> built but Open Buildings shows no new
building ("map-only" change), is that a plotted layout / construction site (real change that
Open Buildings cannot see yet) or classification noise?

Strata, drawn from the 333,600-pixel panel (data/processed/lu/transition_panel.parquet),
per period 2017->2020 and 2020->2023, at most one pixel per 4 km tile per period:
  map_only   20 per period  map undeveloped -> built (10 to res, 10 to non-res), Open Buildings
                            cover < 5% in both years and no cover gain within 70 m
  confirmed   5 per period  map undeveloped -> built and Open Buildings new building
                            (cover < 5% -> >= 20%, gain >= 0.10 within 70 m)   positive control
  stable      5 per period  map undeveloped in both years, no Open Buildings gain  negative control

Outputs (data/processed/change/):
  eyeball_points.kml  20 m map cell squares + pins, named E01..E60, shuffled (strata hidden)
  eyeball_form.csv    id, lat, lon, period, blank `label` and `notes` columns to fill in
  eyeball_key.csv     id -> stratum, map classes, Open Buildings values (keep closed while labelling)
"""
from pathlib import Path
import numpy as np, pandas as pd, rasterio
from pyproj import Transformer

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "processed" / "change"; OUT.mkdir(parents=True, exist_ok=True)
MAPS = ROOT / "outputs" / "lu20" / "maps"
SEED = 20261102
PERIODS = [(2017, 2020), (2020, 2023)]
NAMES = {1: "res", 2: "nonres", 3: "water", 4: "forest", 5: "open"}
N = {"map_only": 20, "confirmed": 5, "stable": 5}

d = pd.read_parquet(ROOT / "data" / "processed" / "lu" / "transition_panel.parquet")
xy = list(zip(d.x, d.y))
for y in (2017, 2020, 2023):
    with rasterio.open(MAPS / f"landuse_{y}_20m_year.tif") as r:
        d[f"m{y}"] = [v[0] for v in r.sample(xy)]
        T = r.transform                               # same grid for every year

rng = np.random.default_rng(SEED)
rows = []
for a, b in PERIODS:
    und_a = d[f"m{a}"].isin([4, 5])
    gain = d[f"cov_7_{b}"] - d[f"cov_7_{a}"]
    no_ob = (d[f"ob_cov_{a}"] < 0.05) & (d[f"ob_cov_{b}"] < 0.05) & (gain < 0.02)
    ob_new = (d[f"ob_cov_{a}"] < 0.05) & (d[f"ob_cov_{b}"] >= 0.20) & (gain >= 0.10)
    pools = {
        ("map_only", 1): und_a & (d[f"m{b}"] == 1) & no_ob,
        ("map_only", 2): und_a & (d[f"m{b}"] == 2) & no_ob,
        ("confirmed", 0): und_a & d[f"m{b}"].isin([1, 2]) & ob_new,
        ("stable", 0): und_a & d[f"m{b}"].isin([4, 5]) & no_ob,
    }
    used = set()                                      # one pixel per tile per period
    for (s, c), m in pools.items():
        k = N[s] // 2 if s == "map_only" else N[s]
        cand = d[m].sample(frac=1, random_state=int(rng.integers(1e9)))
        cand = cand[~cand.tile.isin(used)].drop_duplicates("tile").head(k)
        used |= set(cand.tile)
        print(f"{a}->{b} {s:9s} {NAMES.get(c, 'built'):6s}: pool {int(m.sum()):6d}, drew {len(cand)}")
        rows.append(cand.assign(stratum=s, period=f"{a}-{b}", y0=a, y1=b))

S = pd.concat(rows).sample(frac=1, random_state=SEED).reset_index(drop=True)
S["id"] = [f"E{i + 1:02d}" for i in range(len(S))]

# 20 m map cell containing each panel pixel, corners -> WGS84
col, row = (~T) * (S.x.values, S.y.values)
col, row = np.floor(col), np.floor(row)
x0, y0 = T * (col, row); x1, y1 = T * (col + 1, row + 1)
tr = Transformer.from_crs(32644, 4326, always_xy=True)
S["lon"], S["lat"] = tr.transform(S.x.values, S.y.values)
corners = [tr.transform(px, py) for px, py in ((x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0))]

pm = []
for i, r in S.iterrows():
    ring = " ".join(f"{cx[i]:.7f},{cy[i]:.7f},0" for cx, cy in corners)
    desc = (f"Period {r.y0} -> {r.y1}. In Google Earth Pro use the clock (historical imagery) and "
            f"compare the images nearest to {r.y0} and {r.y1}. Square = one 20 m map cell.")
    pm.append(f"""  <Placemark><name>{r.id}</name><description>{desc}</description><styleUrl>#c</styleUrl>
    <MultiGeometry><Point><coordinates>{r.lon:.7f},{r.lat:.7f},0</coordinates></Point>
    <Polygon><outerBoundaryIs><LinearRing><coordinates>{ring}</coordinates></LinearRing></outerBoundaryIs></Polygon>
    </MultiGeometry></Placemark>""")
kml = f"""<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2"><Document><name>Change eyeball check (60 cells)</name>
  <Style id="c"><LineStyle><color>ff00ffff</color><width>2</width></LineStyle>
    <PolyStyle><fill>0</fill></PolyStyle><IconStyle><scale>0.6</scale></IconStyle></Style>
{chr(10).join(pm)}
</Document></kml>
"""
(OUT / "eyeball_points.kml").write_text(kml, encoding="utf-8")

S[["id", "lat", "lon", "period"]].assign(label="", notes="").to_csv(OUT / "eyeball_form.csv", index=False)
key = S[["id", "stratum", "period", "tile", "x", "y"]].copy()
for i, (a, b) in enumerate(zip(S.y0, S.y1)):
    key.loc[i, "map_start"] = NAMES[S.loc[i, f"m{a}"]]
    key.loc[i, "map_end"] = NAMES[S.loc[i, f"m{b}"]]
    key.loc[i, "ob_cov_start"] = S.loc[i, f"ob_cov_{a}"]
    key.loc[i, "ob_cov_end"] = S.loc[i, f"ob_cov_{b}"]
    key.loc[i, "cov70m_gain"] = S.loc[i, f"cov_7_{b}"] - S.loc[i, f"cov_7_{a}"]
key.round(3).to_csv(OUT / "eyeball_key.csv", index=False)
print(f"wrote {len(S)} cells to {OUT}")
print(key.groupby(["stratum", "period"]).size())
