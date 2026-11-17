"""
Are the HMDA findings the same everywhere, or driven by one part of the region?

Prof.'s instruction (11 Nov 2026): when the study region grows, retest every variable, and do not carry
conclusions from the small trial region to the whole region. 06_table18.py (REGION=hmda) already starts
from every candidate. This script then asks how consistent the result is across parts of HMDA:

  A  the HMDA final specification (table18_census) fitted separately in each subregion: estimate, t,
     and whether the sign agrees with the HMDA estimate
  B  backward elimination from every candidate, separately in each subregion: which variables survive
     where (|t| >= 1.96, fixed effects kept)

Subregions: the three trial ACs (50-52) vs the rest of HMDA; rings by distance to the old CBD
(< 20 km, 20-35 km, >= 35 km).

Usage: REGION=hmda [OUTCOME=persist] python 08_consistency.py
Output: outputs/change/hmda/consistency/  coefs_by_region.csv, survivors.csv, fit_by_region.csv, CONSISTENCY.md
"""
import os, sys
os.environ.setdefault("REGION", "hmda")
sys.argv = [sys.argv[0], "census"]          # 06 reads its mode from argv: all census candidates, nothing dropped
import importlib.util as iu
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path(__file__).resolve().parents[2]
_s = iu.spec_from_file_location("t18", ROOT / "scripts/change/06_table18.py"); T18 = iu.module_from_spec(_s); _s.loader.exec_module(T18)
OUT = T18.OUT.parent / "consistency"; OUT.mkdir(parents=True, exist_ok=True)
REGIONS = {
    "HMDA": lambda d: np.ones(len(d), bool),
    "trial ACs 50-52": lambda d: d.ac.isin([50, 51, 52]).values,
    "rest of HMDA": lambda d: ~d.ac.isin([50, 51, 52]).values,
    "CBD < 20 km": lambda d: (d.d_cbd < 20).values,
    "CBD 20-35 km": lambda d: d.d_cbd.between(20, 35, inclusive="left").values,
    "CBD >= 35 km": lambda d: (d.d_cbd >= 35).values,
}


def usable(s, xs):
    """Drop columns without variation in the subregion (e.g. a district dummy that is all 0)."""
    return [x for x in xs if s[x].nunique() > 1]


def eliminate(s, cand, fixed):
    xs = usable(s, cand); fx = [f for f in fixed if f in xs]
    while True:
        r, _ = T18.fit(s, xs)
        t = r.tvalues.drop(["const"] + fx).abs()
        if t.empty or t.min() >= 1.96:
            return xs, r
        xs.remove(t.idxmin())


def main():
    d = T18.prep(pd.read_parquet(T18.IN))
    cand = [v for v, _, _ in T18.SPEC if v not in T18.DROP]
    d = d.dropna(subset=cand).reset_index(drop=True)
    final = [v for v in pd.read_csv(T18.OUT / "table18.csv", index_col=0).index if v != "const"]
    print(f"HMDA final specification ({len(final)} variables): {final}")
    base, _ = T18.fit(d, final)
    rows, surv, fits = [], [], []
    for nm, f in REGIONS.items():
        s = d[f(d)].reset_index(drop=True)
        xs = usable(s, final); r, c = T18.fit(s, xs)
        for v in xs:
            rows.append({"region": nm, "var": v, "label": T18.LAB[v], "est": r.params[v], "t": r.tvalues[v],
                         "hmda_est": base.params[v], "same_sign": np.sign(r.params[v]) == np.sign(base.params[v]),
                         "significant": abs(r.tvalues[v]) >= 1.96})
        kept, re = eliminate(s, cand, T18.FIXED)
        for v in cand:
            surv.append({"region": nm, "var": v, "label": T18.LAB[v], "kept": v in kept,
                         "est": re.params.get(v, np.nan), "t": re.tvalues.get(v, np.nan)})
        fits.append({"region": nm, "cells": len(s), "changers": int(s.change.sum()), "rho2_final_spec": r.prsquared,
                     "AUC_cv_final_spec": T18.cv_auc(s, xs), "kept_own_elimination": len([v for v in kept if v not in T18.FIXED])})
        print(f"{nm}: {len(s):,} cells, {int(s.change.sum()):,} changes")
    C, S, F = pd.DataFrame(rows), pd.DataFrame(surv), pd.DataFrame(fits)
    C.to_csv(OUT / "coefs_by_region.csv", index=False); S.to_csv(OUT / "survivors.csv", index=False); F.to_csv(OUT / "fit_by_region.csv", index=False)

    regs = list(REGIONS)
    L = ["## A. HMDA final specification fitted in each subregion (estimate, t in brackets; * = sign differs from HMDA)", "",
         "| variable | " + " | ".join(regs) + " |", "|---|" + "---|" * len(regs)]
    for v in final:
        cells = []
        for g in regs:
            q = C[(C.region == g) & (C["var"] == v)]
            cells.append("--" if q.empty else f"{q.est.iloc[0]:.3f} ({q.t.iloc[0]:.1f}){'' if q.same_sign.iloc[0] else ' *'}")
        L.append(f"| {T18.LAB[v]} | " + " | ".join(cells) + " |")
    L += ["", "| | " + " | ".join(regs) + " |", "|---|" + "---|" * len(regs)]
    for k, lab, n in [("cells", "cells", 0), ("changers", "changes", 0), ("rho2_final_spec", "rho-squared", 3),
                      ("AUC_cv_final_spec", "AUC, cross-validated by tile", 3), ("kept_own_elimination", "variables kept by own elimination", 0)]:
        L.append(f"| {lab} | " + " | ".join(f"{x:,.{n}f}" for x in F[k]) + " |")
    L += ["", "## B. Backward elimination from every candidate, separately in each subregion (t of the kept variables)", "",
          "| variable | " + " | ".join(regs) + " |", "|---|" + "---|" * len(regs)]
    for v in cand:
        q = S[S["var"] == v].set_index("region")
        L.append(f"| {T18.LAB[v]} | " + " | ".join(f"{q.t[g]:.1f}" if q.kept[g] else "" for g in regs) + " |")
    (OUT / "CONSISTENCY.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))


if __name__ == "__main__":
    main()
