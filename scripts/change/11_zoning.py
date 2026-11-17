"""
Does master-plan zoning explain where open land gets built?

Zoning: HMDA Master Plan 2031 (approved 2013, before both periods), read from the 30 district sheets onto the
20 m grid by scripts/masterplan/ (data/processed/masterplan/mp2031_zones_20m.tif). It covers the HMDA area
outside the erstwhile HUDA core; cells outside the covered area get their own dummy.

Zone dummies (base: conservation (agriculture)):
  z_res      residential (R1-R4, GDPZ) and settlements     z_periurban  peri-urban
  z_mixed    commercial and multiple use (incl. the ORR growth corridor)
  z_manuf    manufacturing / work centres                  z_public     public and semi-public
  z_green    protected green, water bodies, special reservations
  z_go111    bio-conservation (GO 111)                     z_none       not covered / not read

Tests, same as 10_bus_stops.py: added to the final specification of 06_table18.py census (pooled and per
period: estimate, t, odds ratio, rho2 and AUC gain), and backward elimination from every candidate plus the
zone dummies. Also: development rate by zone (population scale, from the sampling weights).

Usage: REGION=hmda [OUTCOME=persist] python 11_zoning.py
Output: <table18_census>/../zoning/  zoning_tests.csv, rates_by_zone.csv, ZONING.md
"""
import os, sys
os.environ.setdefault("REGION", "hmda")
sys.argv = [sys.argv[0], "census"]
import importlib.util as iu
from pathlib import Path
import numpy as np, pandas as pd, rasterio
from scipy.stats import chi2

ROOT = Path(__file__).resolve().parents[2]
_s = iu.spec_from_file_location("t18", ROOT / "scripts/change/06_table18.py"); T18 = iu.module_from_spec(_s); _s.loader.exec_module(T18)
OUT = T18.OUT.parent / "zoning"; OUT.mkdir(parents=True, exist_ok=True)
ZONES = {"z_res": [1, 12], "z_periurban": [2], "z_mixed": [3, 6], "z_manuf": [4], "z_public": [5],
         "z_green": [8, 10, 11], "z_go111": [9], "z_none": [0]}
LAB = {"z_res": "residential zone", "z_periurban": "peri-urban zone", "z_mixed": "commercial / multiple-use zone",
       "z_manuf": "manufacturing zone", "z_public": "public / semi-public zone", "z_green": "protected green / water / special",
       "z_go111": "GO 111 bio-conservation zone", "z_none": "not covered by the 2031 sheets"}


def add_zones(d):
    with rasterio.open(ROOT / "data/processed/masterplan/mp2031_zones_20m.tif") as s:
        z = s.read(1); T = s.transform
    c = ((d.x.values - T.c) / T.a).astype(int); r = ((d.y.values - T.f) / T.e).astype(int)
    d["zone"] = z[r, c]
    for k, codes in ZONES.items():
        d[k] = d.zone.isin(codes).astype(int)
    return d


def eliminate(d, cand, keep):
    xs = list(cand)
    while True:
        r, _ = T18.fit(d, xs)
        t = r.tvalues.drop(["const"] + keep).abs()
        if t.min() >= 1.96:
            return xs, r
        xs.remove(t.idxmin())


def main():
    d = T18.prep(pd.read_parquet(T18.IN))
    cand = [v for v, _, _ in T18.SPEC if v not in T18.DROP]
    d = d.dropna(subset=cand).reset_index(drop=True)
    d = add_zones(d)
    zv = list(ZONES)
    final = [v for v in pd.read_csv(T18.OUT / "table18.csv", index_col=0).index if v != "const"]
    # development rate by zone (population scale)
    rates = []
    for k in zv + ["base"]:
        m = (d[zv].sum(1) == 0) if k == "base" else (d[k] == 1)
        s = d[m]
        for nm, x in (("2017-2020", s[s.t0 == 2017]), ("2020-2023", s[s.t0 == 2020])):
            rates.append({"zone": "conservation (agriculture), base" if k == "base" else LAB[k], "period": nm, "cells": len(x),
                          "changes": int(x.change.sum()), "rate_pct": 100 * np.average(x.change, weights=x.w)})
    R = pd.DataFrame(rates); R.to_csv(OUT / "rates_by_zone.csv", index=False)
    rows = []
    for nm, s in {"pooled": d, "2017-2020": d[d.t0 == 2017], "2020-2023": d[d.t0 == 2020]}.items():
        base = [x for x in final if not (nm != "pooled" and x == "p2020")]
        zz = [z for z in zv if s[z].sum() > 30]
        r0, _ = T18.fit(s, base); a0 = T18.cv_auc(s, base)
        r1, _ = T18.fit(s, base + zz); a1 = T18.cv_auc(s, base + zz)
        b = r1.params[zz].values; V = r1.cov_params().loc[zz, zz].values; w = float(b @ np.linalg.pinv(V) @ b)
        for v in zz:
            se = r1.bse[v]
            rows.append({"sample": nm, "var": v, "label": LAB[v], "share": s[v].mean(), "est": r1.params[v], "t": r1.tvalues[v],
                         "OR": np.exp(r1.params[v]), "OR_lo": np.exp(r1.params[v] - 1.96 * se), "OR_hi": np.exp(r1.params[v] + 1.96 * se),
                         "rho2_gain": r1.prsquared - r0.prsquared, "AUC_base": a0, "AUC_gain": a1 - a0,
                         "group_wald": w, "group_df": len(zz), "group_p": chi2.sf(w, len(zz))})
    C = pd.DataFrame(rows); C.to_csv(OUT / "zoning_tests.csv", index=False)
    kept, re = eliminate(d, cand + [z for z in zv if d[z].sum() > 30], T18.FIXED)
    L = ["Zoning: HMDA Master Plan 2031 (approved 2013), read from all 30 district sheets; base = conservation (agriculture).", "",
         "## 1. Development rate by zone (% of open land per 3 years, population scale)", "",
         "| zone | 2017-20 cells | changes | rate | 2020-23 cells | changes | rate |", "|---|---|---|---|---|---|---|"]
    for z in R.zone.unique():
        a = R[(R.zone == z) & (R.period == "2017-2020")].iloc[0]; b = R[(R.zone == z) & (R.period == "2020-2023")].iloc[0]
        L.append(f"| {z} | {a.cells:,} | {a.changes:,} | {a.rate_pct:.2f}% | {b.cells:,} | {b.changes:,} | {b.rate_pct:.2f}% |")
    L += ["", "## 2. Zone dummies added to the final specification", "",
          "| sample | zone | share of cells | estimate | t | odds ratio [95%] |", "|---|---|---|---|---|---|"]
    for _, r in C.iterrows():
        L.append(f"| {r['sample']} | {r.label} | {r.share:.1%} | {r.est:.3f} | {r.t:.2f} | {r.OR:.2f} [{r.OR_lo:.2f}, {r.OR_hi:.2f}] |")
    L += ["", "| sample | zones jointly (robust Wald) | rho2 gain | AUC gain (base) |", "|---|---|---|---|"]
    for nm, g in C.groupby("sample", sort=False):
        r = g.iloc[0]
        L.append(f"| {nm} | chi2 {r.group_wald:.1f} on {r.group_df} df, p = {r.group_p:.2g} | {r.rho2_gain:.4f} | {r.AUC_gain:+.4f} ({r.AUC_base:.3f}) |")
    L += ["", "## 3. Backward elimination from every candidate plus the zone dummies", ""]
    for v in zv:
        if v in d and d[v].sum() > 30:
            L.append(f"- {LAB[v]}: " + (f"**kept**, estimate {re.params[v]:.3f}, t {re.tvalues[v]:.2f}" if v in kept else "eliminated"))
    L.append(f"- kept overall: {len([v for v in kept if v not in T18.FIXED])} variables; rho2 {re.prsquared:.3f}, AUC {T18.cv_auc(d, kept):.3f}")
    (OUT / "ZONING.md").write_text("\n".join(L) + "\n", encoding="utf-8"); print("\n".join(L))


if __name__ == "__main__":
    main()
