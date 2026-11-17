"""
How much does each group of factors add, beyond "new building happens next to existing building"?

With 120,000 cells almost anything passes |t| >= 1.96, so the t-values of 06_table18.py say little about
importance. This script reports fit (rho-squared, AUC cross-validated by 4 km tile) for nested models built
one group at a time, plus each group's contribution when it is the last one added (drop-one), on the final
specification of 06_table18.py census.

Usage: REGION=hmda [OUTCOME=persist] python 09_added_value.py
Output: <table18_census>/../added_value/ added_value.csv, ADDED_VALUE.md
"""
import os, sys
os.environ.setdefault("REGION", "hmda")
sys.argv = [sys.argv[0], "census"]
import importlib.util as iu
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path(__file__).resolve().parents[2]
_s = iu.spec_from_file_location("t18", ROOT / "scripts/change/06_table18.py"); T18 = iu.module_from_spec(_s); _s.loader.exec_module(T18)
OUT = T18.OUT.parent / "added_value"; OUT.mkdir(parents=True, exist_ok=True)

GROUPS = [   # (name, variables); only those in the final specification are used
    ("distance to the dense city", ["ln_d_urban"]),
    ("land use within 1 km, from our map (shares, mix)", ["res_pct", "nonres_pct", "water_pct", "trees_pct", "lu_mix_1km", "ln_viirs"]),
    ("tree cover on the cell", ["trees_t0"]),
    ("accessibility (CBD, HITEC, airport, ORR, metro, major road, road km)",
     ["ln_d_cbd", "ln_d_jobs", "ln_d_airport", "ln_d_orr", "ln_d_metro", "ln_d_major_road", "road_10km"]),
    ("supply constraints (terrain, lakes, restricted, GO 111)",
     ["slope_deg", "relief_m", "elev_100m", "ln_d_lake", "near_lake", "restricted", "go111"]),
    ("jobs and census (EC 2013, Census 2011, SECC, WorldPop)",
     ["ln_jobs_5km", "ln_jobdens_vill", "it_pct_5km", "manuf_pct_5km", "large_pct_5km", "ln_popdens_vill", "scst_pct",
      "lit_pct", "agri_pct", "veh23_pct", "veh4_pct", "in_ghmc", "ln_wp"]),
]


def main():
    d = T18.prep(pd.read_parquet(T18.IN))
    cand = [v for v, _, _ in T18.SPEC if v not in T18.DROP]
    d = d.dropna(subset=cand).reset_index(drop=True)
    final = [v for v in pd.read_csv(T18.OUT / "table18.csv", index_col=0).index if v != "const"]
    fx = [v for v in T18.FIXED if v in final]
    G = [(g, [v for v in vs if v in final]) for g, vs in GROUPS]
    G = [(g, vs) for g, vs in G if vs]
    rows = []
    def score(xs):
        r, _ = T18.fit(d, xs); return r.prsquared, T18.cv_auc(d, xs)
    xs = list(fx); r2, auc = score(xs)
    rows.append({"step": "period and district dummies", "kind": "nested", "vars": ", ".join(fx), "rho2": r2, "AUC": auc})
    for g, vs in G:
        xs += vs; r2, auc = score(xs)
        rows.append({"step": f"+ {g}", "kind": "nested", "vars": ", ".join(vs), "rho2": r2, "AUC": auc})
    full_r2, full_auc = r2, auc
    for g, vs in G:
        r2, auc = score([x for x in xs if x not in vs])
        rows.append({"step": f"final without {g}", "kind": "drop-one", "vars": ", ".join(vs), "rho2": r2, "AUC": auc,
                     "rho2_loss": full_r2 - r2, "AUC_loss": full_auc - auc})
    near = GROUPS[0][1] + GROUPS[1][1]          # everything that says "near existing development", from our map
    nd = [x for x in xs if x not in near]
    r2, auc = score(nd)
    rows.append({"step": "final without distance to the dense city AND our-map land use", "kind": "drop-one",
                 "vars": "", "rho2": r2, "AUC": auc, "rho2_loss": full_r2 - r2, "AUC_loss": full_auc - auc})
    A = pd.DataFrame(rows); A.to_csv(OUT / "added_value.csv", index=False)
    L = ["| model | rho-squared | AUC (cross-validated) | loss when left out (rho2 / AUC) |", "|---|---|---|---|"]
    for _, r in A.iterrows():
        loss = "" if r.kind == "nested" else f"{r.rho2_loss:.3f} / {r.AUC_loss:.3f}"
        L.append(f"| {r.step} | {r.rho2:.3f} | {r.AUC:.3f} | {loss} |")
    (OUT / "ADDED_VALUE.md").write_text("\n".join(L) + "\n", encoding="utf-8"); print("\n".join(L))


if __name__ == "__main__":
    main()
