"""
Trial binary logit of land-use change (Florida Table 18 analogue) on the 3-AC trial sample from
02_trial_data.py. Question: does booth-level population (2018 votes polled) relate to where
undeveloped land got developed, beyond distances, roads and the built neighbourhood?

Models, per period and pooled (period dummy):
  M0  base: start class, log distances (airport, ORR interchange, metro, jobs centres, major road),
      road km in 4 x 4 km, built share in 1 km, AC dummies
  M1  M0 + log votes density (2018 booths, 1 km kernel)
  M2  M0 + log WorldPop density (start year)
  M3  M0 + both
  V, W  votes alone, WorldPop alone (the raw association, no controls)
Estimation: logit on the choice-based sample (slopes are consistent; the constant is corrected
with the sampling weights, King & Zeng 2001), standard errors clustered by 4 km tile.
Fit: McFadden R2, AIC, likelihood-ratio test against M0, and AUC under 5-fold cross-validation
grouped by 4 km tile (so neighbouring cells are never split between training and test).
Checks: votes kernel 2 km instead of 1 km; cells more than 1.5 km from the region edge; booth
alignment shifted (trial_cells_shift*.parquet if present).

Usage: python 03_trial_logit.py
Output: outputs/change/trial/TRIAL_RESULTS.md, coefs.csv, fit.csv, rates.csv
"""
import glob, warnings
from pathlib import Path
import numpy as np, pandas as pd, statsmodels.api as sm
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import GroupKFold

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parents[2]
CH = ROOT / "data" / "processed" / "change"
OUT = ROOT / "outputs" / "change" / "trial"; OUT.mkdir(parents=True, exist_ok=True)

BASE = ["trees_t0", "ln_d_airport", "ln_d_orr", "ln_d_metro", "ln_d_jobs", "ln_d_major_road", "road_km_4km", "built_1km"]
LABEL = {"trees_t0": "start class trees (vs open)", "ln_d_airport": "ln distance to airport (km)",
         "ln_d_orr": "ln distance to ORR interchange", "ln_d_metro": "ln distance to open metro station",
         "ln_d_jobs": "ln distance to HITEC City / Financial District", "ln_d_major_road": "ln distance to major road",
         "road_km_4km": "road km in 4 x 4 km window (/100)", "built_1km": "built share in 1 km window",
         "ln_votes": "ln votes per km2, 2018 booths (1 km kernel)", "ln_votes2": "ln votes per km2 (2 km kernel)",
         "ln_wp": "ln WorldPop people per km2 (start year)", "p2020": "period 2020-2023 (vs 2017-2020)",
         "ac51": "AC Rajendranagar (vs Maheshwaram)", "ac52": "AC Serilingampally (vs Maheshwaram)"}


def prep(d):
    d = d.copy()
    for k in ["airport", "orr", "metro", "jobs", "major_road"]:
        d[f"ln_d_{k}"] = np.log(d[f"d_{k}"] + 0.1)
    d["road_km_4km"] = d.road_km_4km / 100
    d["ln_votes"] = np.log1p(d.votes_kde1km); d["ln_votes2"] = np.log1p(d.votes_kde2km)
    d["ln_wp"] = np.log1p(d.worldpop_1km)
    d["p2020"] = (d.t0 == 2020).astype(int)
    d["ac51"] = (d.ac == 51).astype(int); d["ac52"] = (d.ac == 52).astype(int)
    return d


def fit(d, xs):
    X = sm.add_constant(d[xs].astype(float)); m = sm.Logit(d.change, X)
    r = m.fit(disp=0, cov_type="cluster", cov_kwds={"groups": d.tile.values}, maxiter=200)
    # King-Zeng prior correction of the constant: tau = population share of changers, ybar = sample share
    tau = (d.w * d.change).sum() / d.w.sum(); yb = d.change.mean()
    const = r.params["const"] - np.log(((1 - tau) / tau) * (yb / (1 - yb)))
    return r, const


def cv_auc(d, xs, k=5):
    p = np.zeros(len(d))
    for tr, te in GroupKFold(k).split(d, groups=d.tile):
        X = sm.add_constant(d[xs].astype(float))
        r = sm.Logit(d.change.iloc[tr], X.iloc[tr]).fit(disp=0, maxiter=200)
        p[te] = r.predict(X.iloc[te])
    return roc_auc_score(d.change, p)


def models(d, extra=()):
    fe = ["ac51", "ac52"] + list(extra)
    return {"M0 base": BASE + fe, "M1 + votes": BASE + fe + ["ln_votes"],
            "M2 + WorldPop": BASE + fe + ["ln_wp"], "M3 + both": BASE + fe + ["ln_votes", "ln_wp"],
            "V votes only": list(extra) + ["ln_votes"], "W WorldPop only": list(extra) + ["ln_wp"]}


def main():
    d = prep(pd.read_parquet(CH / "trial_cells.parquet"))
    sets = {"2017-2020": d[d.t0 == 2017], "2020-2023": d[d.t0 == 2020], "pooled": d}
    coefs, fits = [], []
    for nm, s in sets.items():
        M = models(s, ["p2020"] if nm == "pooled" else [])
        ll0 = None
        for mn, xs in M.items():
            r, c = fit(s, xs)
            if ll0 is None:
                ll0, k0 = r.llf, len(xs)
            nested = set(M["M0 base"]) <= set(xs)
            lr = 2 * (r.llf - ll0) if nested else np.nan; dfree = len(xs) - k0
            from scipy.stats import chi2
            sd = s[xs].std()
            fits.append({"sample": nm, "model": mn, "n": len(s), "changers": int(s.change.sum()),
                         "McFadden_R2": r.prsquared, "AIC": r.aic, "LR_vs_M0": lr,
                         "p_LR": chi2.sf(lr, dfree) if (dfree and nested) else np.nan, "AUC_cv": cv_auc(s, xs)})
            for v in ["const"] + xs:
                coefs.append({"sample": nm, "model": mn, "var": v, "coef": c if v == "const" else r.params[v],
                              "se": r.bse[v], "z": r.tvalues[v], "p": r.pvalues[v],
                              "OR_per_SD": np.exp(r.params[v] * sd[v]) if v != "const" else np.nan})
    # checks on the pooled sample with votes
    chk = []
    for nm, s, xs in [("votes kernel 2 km", d, models(d, ["p2020"])["M0 base"] + ["ln_votes2"]),
                      ("cells > 1.5 km from region edge", d[d.d_edge > 1.5], models(d, ["p2020"])["M1 + votes"]),
                      ("2020-2023 only (votes 2018 = before the period)", sets["2020-2023"], models(d)["M1 + votes"])]:
        r, _ = fit(s, xs); v = "ln_votes2" if "ln_votes2" in xs else "ln_votes"
        chk.append({"check": nm, "n": len(s), "coef": r.params[v], "z": r.tvalues[v], "p": r.pvalues[v]})
    for f in sorted(glob.glob(str(CH / "trial_cells_shift*.parquet"))):
        s = prep(pd.read_parquet(f)); r, _ = fit(s, models(s, ["p2020"])["M1 + votes"])
        chk.append({"check": f"booth alignment shifted ({Path(f).stem.split('_')[-1]})", "n": len(s),
                    "coef": r.params["ln_votes"], "z": r.tvalues["ln_votes"], "p": r.pvalues["ln_votes"]})

    # weighted change rate by votes and WorldPop quintile (population rates, from the sampling weights)
    rates = []
    for v, lab in (("votes_kde1km", "votes per km2 (2018 booths)"), ("worldpop_1km", "WorldPop per km2")):
        q = pd.qcut(d[v].rank(method="first"), 5, labels=[f"Q{i}" for i in range(1, 6)])
        for (per, qq), g in d.groupby(["period", q], observed=True):
            rates.append({"variable": lab, "period": per, "quintile": qq, "median_value": g[v].median(),
                          "change_rate_pct": 100 * (g.w * g.change).sum() / g.w.sum(), "n": len(g)})
    C, F, K, R = pd.DataFrame(coefs), pd.DataFrame(fits), pd.DataFrame(chk), pd.DataFrame(rates)
    C.to_csv(OUT / "coefs.csv", index=False); F.to_csv(OUT / "fit.csv", index=False)
    K.to_csv(OUT / "checks.csv", index=False); R.to_csv(OUT / "rates.csv", index=False)
    corr = d[["ln_votes", "ln_wp", "built_1km", "road_km_4km", "ln_d_jobs", "ln_d_orr"]].corr().round(2)
    print(F.round(3).to_string(index=False)); print(K.round(3).to_string(index=False)); print(corr)
    pd.to_pickle({"C": C, "F": F, "K": K, "R": R, "corr": corr, "LABEL": LABEL}, OUT / "results.pkl")


if __name__ == "__main__":
    main()
