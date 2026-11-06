"""
Hyderabad analogue of Table 18 in the reference report (UCF/FDOT Final Report, §7.2.1: "Binary Logit
Model of Land Use Change (Base: No Change)"), on the 3-AC trial sample.

Like Table 18:
  - one binary logit, change vs no change, for land that is vacant at t-1 (here: undeveloped 20 m cells)
  - variables grouped under headers with their base category; neighbourhood land use as % by area
  - final specification keeps only significant variables (backward elimination from all candidates,
    dropping the least significant one at a time until every |t| >= 1.96; t from cluster-robust
    standard errors by 4 km tile). Constituency and period dummies are design variables and always kept.
Added to Table 18: the same specification per period, fit statistics, and the joint test that the
eliminated variables don't matter.

The constant is corrected for the choice-based sample (King & Zeng 2001; the t stat is that of the
corrected constant over its standard error, since the correction is a known shift).

Usage: python 06_table18.py
Output: outputs/change/trial/table18/  table18.csv, elimination.csv, fit.csv, TABLE18.md
"""
import sys, warnings
from pathlib import Path
import numpy as np, pandas as pd, statsmodels.api as sm
from scipy.stats import chi2
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import GroupKFold

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parents[2]
CH = ROOT / "data" / "processed" / "change"
# census: add the Economic Census 2013 / Census 2011 / SECC factors (07_census_factors.py)
# florida: census, with job mass entering as in Table 18 (job density): road mileage and distance to the dense
#          city are left out of the candidates, because they are near-duplicates of jobs within 5 km
#          (r = 0.89 and -0.85) and flip its sign. The census run (with them) is the check.
FLORIDA = "florida" in sys.argv
CENSUS = "census" in sys.argv or FLORIDA
DROP = ["road_10km", "ln_d_urban"] if FLORIDA else []
OUT = ROOT / "outputs" / "change" / "trial" / ("table18_florida" if FLORIDA else "table18_census" if CENSUS else "table18")
OUT.mkdir(parents=True, exist_ok=True)
IN = CH / ("trial_cells_census.parquet" if CENSUS else "trial_cells_full.parquet")

# (variable, label, header) in table order
SPEC = [
    ("trees_t0", "Tree cover (vs open land)", "Land cover of the cell at t-1 (Base: open land)"),
    ("res_pct", "Residential", "Land use within 1 km (% by area) (Base: open land)"),
    ("nonres_pct", "Non-residential", "Land use within 1 km (% by area) (Base: open land)"),
    ("water_pct", "Water", "Land use within 1 km (% by area) (Base: open land)"),
    ("trees_pct", "Trees", "Land use within 1 km (% by area) (Base: open land)"),
    ("lu_mix_1km", "Land-use mix (entropy, 0-1)", "Land use within 1 km (% by area) (Base: open land)"),
    ("ln_d_urban", "Ln(km to the dense city, 1 km built share >= 40%)", "Urban form"),
    ("ln_viirs", "Ln(night lights within 1 km)", "Urban form"),
    ("ln_d_airport", "Ln(km to the airport)", "Accessibility"),
    ("ln_d_jobs", "Ln(km to HITEC City / Financial District)", "Accessibility"),
    ("ln_d_cbd", "Ln(km to the old CBD)", "Accessibility"),
    ("ln_d_orr", "Ln(km to the nearest ORR interchange)", "Accessibility"),
    ("ln_d_metro", "Ln(km to the nearest open metro station)", "Accessibility"),
    ("ln_d_major_road", "Ln(km to the nearest major road)", "Accessibility"),
    ("road_10km", "Road mileage in the 4 km x 4 km window (10 km)", "Accessibility"),
    ("slope_deg", "Slope (degrees)", "Supply constraints"),
    ("relief_m", "Relief within 150 m (m)", "Supply constraints"),
    ("elev_100m", "Elevation (100 m)", "Supply constraints"),
    ("ln_d_lake", "Ln(km to a lake >= 2 ha)", "Supply constraints"),
    ("near_lake", "Within 100 m of a lake", "Supply constraints"),
    ("restricted", "Military, forest, protected or airport land", "Supply constraints"),
    ("go111", "GO 111 zone (within 10 km of Osman / Himayat Sagar)", "Supply constraints"),
    ("ln_votes", "Ln(votes polled per km2, 2018 booths)", "Population"),
    ("ln_wp", "Ln(WorldPop people per km2)", "Population"),
] + ([
    ("ln_jobs_5km", "Ln(workers within ~5 km)", "Jobs, Economic Census 2013"),
    ("ln_jobdens_vill", "Ln(workers per km2 in the village / town)", "Jobs, Economic Census 2013"),
    ("it_pct_5km", "Software / IT services (% of jobs within ~5 km)", "Jobs, Economic Census 2013"),
    ("manuf_pct_5km", "Manufacturing (% of jobs within ~5 km)", "Jobs, Economic Census 2013"),
    ("large_pct_5km", "Establishments with 100+ workers (% of jobs within ~5 km)", "Jobs, Economic Census 2013"),
    ("ln_popdens_vill", "Ln(people per km2 in the village / town)", "Village / town, Census 2011 and SECC 2011-12"),
    ("scst_pct", "SC / ST (% of people)", "Village / town, Census 2011 and SECC 2011-12"),
    ("lit_pct", "Literacy rate (% of people aged 7+)", "Village / town, Census 2011 and SECC 2011-12"),
    ("agri_pct", "Agricultural workers (% of workers)", "Village / town, Census 2011 and SECC 2011-12"),
    ("veh23_pct", "Households with a two- or three-wheeler (%)", "Village / town, Census 2011 and SECC 2011-12"),
    ("veh4_pct", "Households with a four-wheeler (%)", "Village / town, Census 2011 and SECC 2011-12"),
    ("in_ghmc", "Inside GHMC (village values are city-wide averages)", "Village / town, Census 2011 and SECC 2011-12"),
] if CENSUS else []) + [
    ("ac51", "Rajendranagar", "Assembly constituency (Base: Maheshwaram)"),
    ("ac52", "Serilingampally", "Assembly constituency (Base: Maheshwaram)"),
    ("p2020", "2020-2023", "Period (Base: 2017-2020)"),
]
LAB = {v: l for v, l, _ in SPEC}; HEAD = {v: h for v, _, h in SPEC}
FIXED = ["ac51", "ac52", "p2020"]


def prep(d):
    d = d.copy()
    for k in ["airport", "orr", "metro", "jobs", "cbd", "major_road", "urban", "lake"]:
        d[f"ln_d_{k}"] = np.log(d[f"d_{k}"] + 0.1)
    for k in ["res", "nonres", "water", "trees"]:
        d[f"{k}_pct"] = 100 * d[f"{k}_1km"]
    d["road_10km"] = (d.major_km_4km + d.minor_km_4km) / 10
    d["ln_viirs"] = np.log1p(d.viirs_1km.clip(lower=0)); d["elev_100m"] = d.elev_m / 100
    d["ln_votes"] = np.log1p(d.votes_kde1km); d["ln_wp"] = np.log1p(d.worldpop_1km)
    d["p2020"] = (d.t0 == 2020).astype(int); d["ac51"] = (d.ac == 51).astype(int); d["ac52"] = (d.ac == 52).astype(int)
    if CENSUS:
        d["ln_jobs_5km"] = np.log1p(d.jobs_5km); d["ln_jobdens_vill"] = np.log1p(d.jobdens_vill)
        d["ln_popdens_vill"] = np.log1p(d.popdens_vill)
        for a, b in (("it_share_5km", "it_pct_5km"), ("manuf_share_5km", "manuf_pct_5km"), ("large_share_5km", "large_pct_5km"),
                     ("scst_share", "scst_pct"), ("lit_rate", "lit_pct"), ("agri_share", "agri_pct"),
                     ("veh23_share", "veh23_pct"), ("veh4_share", "veh4_pct")):
            d[b] = 100 * d[a]
        # SECC has no vehicle data for a few villages: AC median (count reported in the log)
        for v in ("veh23_pct", "veh4_pct"):
            print(f"{v}: {d[v].isna().sum()} cells without SECC data, filled with the AC median")
            d[v] = d[v].fillna(d.groupby("ac")[v].transform("median"))
    return d


def fit(d, xs):
    X = sm.add_constant(d[xs].astype(float), has_constant="add")
    r = sm.Logit(d.change, X).fit(disp=0, cov_type="cluster", cov_kwds={"groups": d.tile.values}, maxiter=300)
    tau = (d.w * d.change).sum() / d.w.sum(); yb = d.change.mean()
    return r, r.params["const"] - np.log(((1 - tau) / tau) * (yb / (1 - yb)))


def cv_auc(d, xs):
    p = np.zeros(len(d))
    for tr, te in GroupKFold(5).split(d, groups=d.tile):
        X = sm.add_constant(d[xs].astype(float), has_constant="add")
        p[te] = sm.Logit(d.change.iloc[tr], X.iloc[tr]).fit(disp=0, maxiter=300).predict(X.iloc[te])
    return roc_auc_score(d.change, p)


def main():
    d = prep(pd.read_parquet(IN))
    cand = [v for v, _, _ in SPEC if v not in DROP]
    d = d.dropna(subset=cand).reset_index(drop=True)
    xs, steps = list(cand), []
    while True:
        r, _ = fit(d, xs)
        t = r.tvalues.drop(["const"] + FIXED).abs()
        if t.min() >= 1.96:
            break
        v = t.idxmin(); steps.append({"step": len(steps) + 1, "dropped": v, "label": LAB[v], "t": r.tvalues[v],
                                      "coef": r.params[v]}); xs.remove(v)
    final = xs
    dropped = [s["dropped"] for s in steps]
    rf, _ = fit(d, cand)
    b = rf.params[dropped].values; V = rf.cov_params().loc[dropped, dropped].values
    w = float(b @ np.linalg.pinv(V) @ b)

    sets = {"pooled": d, "2017-2020": d[d.t0 == 2017], "2020-2023": d[d.t0 == 2020]}
    rows, fits = {}, []
    for nm, s in sets.items():
        xx = [x for x in final if not (nm != "pooled" and x == "p2020")]
        r, c = fit(s, xx)
        rows[nm] = pd.DataFrame({"est": r.params, "t": r.tvalues}); rows[nm].loc["const", ["est", "t"]] = [c, c / r.bse["const"]]
        r0 = sm.Logit(s.change, np.ones((len(s), 1))).fit(disp=0)
        k = len(xx) + 1
        fits.append({"sample": nm, "cells": len(s), "changers": int(s.change.sum()), "parameters": k,
                     "LL_constant": r0.llf, "LL_final": r.llf, "LR_vs_constant": 2 * (r.llf - r0.llf),
                     "rho2": 1 - r.llf / r0.llf, "adj_rho2": 1 - (r.llf - k) / r0.llf, "AIC": r.aic, "BIC": r.bic,
                     "AUC_cv": cv_auc(s, xx)})
    T = pd.concat(rows, axis=1); T.columns = [f"{a}_{b}" for a, b in T.columns]
    order = ["const"] + [v for v in cand if v in final]
    T = T.loc[order]; T.insert(0, "label", ["Constant"] + [LAB[v] for v in order[1:]])
    T.insert(0, "header", [""] + [HEAD[v] for v in order[1:]])
    F = pd.DataFrame(fits); E = pd.DataFrame(steps)
    T.to_csv(OUT / "table18.csv"); E.to_csv(OUT / "elimination.csv", index=False); F.to_csv(OUT / "fit.csv", index=False)

    # markdown in the layout of Table 18
    L = ["| Variable | Estimate | t stat | 2017-20 est. | t | 2020-23 est. | t |", "|---|---|---|---|---|---|---|"]
    last = None
    f = lambda x, n=3: "--" if pd.isna(x) else f"{x:.{n}f}"
    for v, row in T.iterrows():
        if row.header and row.header != last:
            L.append(f"| ***{row.header}*** | | | | | | |"); last = row.header
        L.append(f"| {row.label} | {f(row.pooled_est)} | {f(row.pooled_t, 2)} | {f(row['2017-2020_est'])} | "
                 f"{f(row['2017-2020_t'], 2)} | {f(row['2020-2023_est'])} | {f(row['2020-2023_t'], 2)} |")
    L += ["", "| | pooled | 2017-20 | 2020-23 |", "|---|---|---|---|"]
    for k, lab, n in [("cells", "cells", 0), ("changers", "changes", 0), ("parameters", "parameters", 0),
                      ("LL_constant", "log-likelihood, constant only", 1), ("LL_final", "log-likelihood at convergence", 1),
                      ("rho2", "rho-squared (vs constant only)", 3), ("adj_rho2", "adjusted rho-squared", 3),
                      ("AUC_cv", "AUC, 5-fold cross-validated by 4 km tile", 3)]:
        L.append(f"| {lab} | " + " | ".join(f"{x:,.{n}f}" for x in F[k]) + " |")
    L += ["", f"Eliminated jointly: robust Wald chi2 = {w:.1f} on {len(dropped)} df, p = {chi2.sf(w, len(dropped)):.2f}",
          "", "| step | eliminated | t when eliminated |", "|---|---|---|"]
    L += [f"| {s['step']} | {s['label']} | {s['t']:.2f} |" for s in steps]
    (OUT / "TABLE18.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L)); print(F.round(4).to_string(index=False))


if __name__ == "__main__":
    main()
