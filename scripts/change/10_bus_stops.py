"""
Does bus access explain where open land gets built?

Bus stops: 5,177 TGSRTC stops from the WRI India Transport Analytics Hub (shift-transport.org), saved as
data/raw/transit_shift/Hyderabad__amenities__bus_stops.geojson (11 Nov 2026). They are the CURRENT stops
(2023-24), not the stops at t0: some may have been added because an area developed, so the 2020-23 period is
the fairer test and the 2017-20 result is an upper bound.

Factors per cell: ln km to the nearest stop, stops within 1 km (/10).
Tests on the final specification of 06_table18.py census (same REGION / OUTCOME):
  1  final + bus factor(s), pooled and per period: estimate, t, odds ratio, change in rho2 and in
     cross-validated AUC
  2  backward elimination from every candidate plus the two bus factors (as 06_table18.py)

Usage: REGION=hmda [OUTCOME=persist] python 10_bus_stops.py
Output: <table18_census>/../bus_stops/  bus_tests.csv, BUS_STOPS.md
"""
import os, sys
os.environ.setdefault("REGION", "hmda")
sys.argv = [sys.argv[0], "census"]
import importlib.util as iu
from pathlib import Path
import numpy as np, pandas as pd, geopandas as gpd
from scipy.spatial import cKDTree

ROOT = Path(__file__).resolve().parents[2]
_s = iu.spec_from_file_location("t18", ROOT / "scripts/change/06_table18.py"); T18 = iu.module_from_spec(_s); _s.loader.exec_module(T18)
OUT = T18.OUT.parent / "bus_stops"; OUT.mkdir(parents=True, exist_ok=True)
STOPS = ROOT / "data/raw/transit_shift/Hyderabad__amenities__bus_stops.geojson"
BUS = {"ln_d_bus": "Ln(km to the nearest bus stop, current stops)", "bus_1km": "Bus stops within 1 km (/10)"}


def add_bus(d):
    s = gpd.read_file(STOPS).to_crs(32644)
    xy = np.c_[s.geometry.x, s.geometry.y]; t = cKDTree(xy)
    p = d[["x", "y"]].values
    d["d_bus"] = t.query(p)[0] / 1000
    d["ln_d_bus"] = np.log(d.d_bus + 0.1)
    d["bus_1km"] = np.array([len(n) for n in t.query_ball_point(p, 1000)]) / 10
    return d, len(s)


def eliminate(d, cand):
    xs = list(cand)
    while True:
        r, _ = T18.fit(d, xs)
        t = r.tvalues.drop(["const"] + T18.FIXED).abs()
        if t.min() >= 1.96:
            return xs, r
        xs.remove(t.idxmin())


def main():
    d = T18.prep(pd.read_parquet(T18.IN))
    cand = [v for v, _, _ in T18.SPEC if v not in T18.DROP]
    d = d.dropna(subset=cand).reset_index(drop=True)
    d, n_stops = add_bus(d)
    final = [v for v in pd.read_csv(T18.OUT / "table18.csv", index_col=0).index if v != "const"]
    print(f"{n_stops:,} stops; cells: median {d.d_bus.median():.2f} km to a stop, {(d.d_bus > 5).mean():.1%} more than 5 km away")
    print("mean km to a stop: change", round(d.loc[d.change == 1, "d_bus"].mean(), 2), "no change", round(d.loc[d.change == 0, "d_bus"].mean(), 2))
    print("correlations:", d[["ln_d_bus", "bus_1km", "ln_d_major_road", "ln_d_urban", "ln_d_cbd", "lu_mix_1km"]].corr().round(2).loc[["ln_d_bus", "bus_1km"]].to_string())
    rows = []
    sets = {"pooled": d, "2017-2020": d[d.t0 == 2017], "2020-2023": d[d.t0 == 2020]}
    for nm, s in sets.items():
        base = [x for x in final if not (nm != "pooled" and x == "p2020")]
        r0, _ = T18.fit(s, base); a0 = T18.cv_auc(s, base)
        for add in (["ln_d_bus"], ["bus_1km"], ["ln_d_bus", "bus_1km"]):
            r, _ = T18.fit(s, base + add); a = T18.cv_auc(s, base + add)
            for v in add:
                k = -np.log(2) if v == "ln_d_bus" else 1.0
                se = r.bse[v]
                rows.append({"sample": nm, "added": " + ".join(add), "var": v, "est": r.params[v], "t": r.tvalues[v],
                             "OR": np.exp(k * r.params[v]), "OR_lo": min(np.exp(k * (r.params[v] - 1.96 * se)), np.exp(k * (r.params[v] + 1.96 * se))),
                             "OR_hi": max(np.exp(k * (r.params[v] - 1.96 * se)), np.exp(k * (r.params[v] + 1.96 * se))),
                             "OR_unit": "half as far" if v == "ln_d_bus" else "+10 stops", "rho2_gain": r.prsquared - r0.prsquared,
                             "AUC_base": a0, "AUC_gain": a - a0})
    R = pd.DataFrame(rows); R.to_csv(OUT / "bus_tests.csv", index=False)
    kept, re = eliminate(d, cand + list(BUS))
    L = [f"Bus stops: {n_stops:,} (current, TGSRTC via shift-transport.org). Median distance of a sampled cell to a stop "
         f"{d.d_bus.median():.2f} km; {(d.d_bus > 5).mean():.1%} of cells more than 5 km away.", "",
         "## 1. Added to the final specification", "",
         "| sample | added | factor | estimate | t | odds ratio [95%] | rho2 gain | AUC gain (base) |", "|---|---|---|---|---|---|---|---|"]
    for _, r in R.iterrows():
        L.append(f"| {r['sample']} | {r.added} | {BUS[r['var']]} | {r.est:.3f} | {r.t:.2f} | {r.OR:.2f} [{r.OR_lo:.2f}, {r.OR_hi:.2f}] per {r.OR_unit} | "
                 f"{r.rho2_gain:.4f} | {r.AUC_gain:+.4f} ({r.AUC_base:.3f}) |")
    L += ["", "## 2. Backward elimination from every candidate plus the bus factors", ""]
    for v in BUS:
        L.append(f"- {BUS[v]}: " + (f"**kept**, estimate {re.params[v]:.3f}, t {re.tvalues[v]:.2f}" if v in kept else "eliminated"))
    L.append(f"- kept overall: {len([v for v in kept if v not in T18.FIXED])} variables; rho2 {re.prsquared:.3f}")
    (OUT / "BUS_STOPS.md").write_text("\n".join(L) + "\n", encoding="utf-8"); print("\n".join(L))


if __name__ == "__main__":
    main()
