"""
Full binary logit of land-use change on the 3-AC trial sample, with every factor of
CHANGE_MODEL_PLAN.md §5c that we have (trial_cells_full.parquet from 04_more_factors.py), and the tests
that say which factors matter and how far the associations can be read as causes.

Factor groups (mechanisms, CHANGE_MODEL_PLAN.md §6):
  start      start class trees (vs open)
  access     ln distance to airport, ORR interchange, open metro station, HITEC/FD, old CBD, major road;
             major- and minor-road km in the 4 x 4 km window
  nbhd       res, non-res, water, tree shares in 1 km, land-use mix, ln distance to the dense city,
             ln night lights
  constr     slope, relief, elevation, ln distance to a lake, within 100 m of a lake, restricted land,
             GO 111 zone
  people     ln votes density (2018 booths), ln WorldPop density
  fixed      AC dummies (+ period dummy when pooled)

Tests
  1 Wald z per coefficient, cluster-robust by 4 km tile: is the factor's effect non-zero holding the others?
  2 Wald chi2 per group, cluster-robust: does the group as a whole matter? (+ LR test, which assumes
    independent cells and so is too optimistic; reported for comparison)
  3 Cross-validated AUC (5 folds, grouped by tile): the group alone, and the loss when it is dropped
    (unique predictive contribution)
  4 Size: odds ratio per SD and average marginal effect (change in the 3-year development
    probability for +1 SD, population-weighted, with the King-Zeng corrected constant)
  5 Collinearity: variance inflation factors
  6 Stability over time: all slopes interacted with the period (Chow-type Wald test), and the
    2017-20 model predicting 2020-23 (temporal transfer AUC)
  7 Spatial independence: Moran's I of the residuals (8 nearest sampled cells), permutation p
  8 Calibration: predicted vs observed rate by decile of predicted probability
  9 Causal-direction checks: roads added during the period (do roads follow development?), change in
    the neighbourhood in the previous period (contagion, 2020-23), GO 111 x 2020-23 (repeal in 2022)

Usage: python 05_full_logit.py
Output: outputs/change/trial/full/  (coefs.csv, groups.csv, effects.csv, vif.csv, checks.csv,
        calibration.csv, results.pkl)
"""
import warnings
from pathlib import Path
import numpy as np, pandas as pd, statsmodels.api as sm
from scipy.stats import chi2
from scipy.spatial import cKDTree
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import GroupKFold

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parents[2]
CH = ROOT / "data" / "processed" / "change"
OUT = ROOT / "outputs" / "change" / "trial" / "full"; OUT.mkdir(parents=True, exist_ok=True)
RNG = np.random.default_rng(20261105)

GROUPS = {
    "start": ["trees_t0"],
    "access": ["ln_d_airport", "ln_d_orr", "ln_d_metro", "ln_d_jobs", "ln_d_cbd", "ln_d_major_road", "major_km", "minor_km"],
    "nbhd": ["res_1km", "nonres_1km", "water_1km", "trees_1km", "lu_mix_1km", "ln_d_urban", "ln_viirs"],
    "constr": ["slope_deg", "relief_m", "elev_100m", "ln_d_lake", "near_lake", "restricted", "go111"],
    "people": ["ln_votes", "ln_wp"],
}
GNAME = {"start": "land at the start", "access": "access (distances, roads)", "nbhd": "neighbourhood (land use nearby)",
         "constr": "supply constraints (terrain, lakes, restricted land)", "people": "people (votes, WorldPop)"}
LABEL = {
    "trees_t0": "start class trees (vs open)", "ln_d_airport": "ln km to airport", "ln_d_orr": "ln km to ORR interchange",
    "ln_d_metro": "ln km to open metro station", "ln_d_jobs": "ln km to HITEC City / Financial District",
    "ln_d_cbd": "ln km to old CBD (Abids)", "ln_d_major_road": "ln km to major road",
    "major_km": "major-road km in 4 x 4 km (/10)", "minor_km": "minor-road km in 4 x 4 km (/100)",
    "res_1km": "residential share in 1 km", "nonres_1km": "non-residential share in 1 km",
    "water_1km": "water share in 1 km", "trees_1km": "tree share in 1 km", "lu_mix_1km": "land-use mix in 1 km (0-1)",
    "ln_d_urban": "ln km to the dense city (1 km built share >= 0.4)", "ln_viirs": "ln night lights (1 km)",
    "slope_deg": "slope (degrees)", "relief_m": "relief within 150 m (m)", "elev_100m": "elevation (100 m)",
    "ln_d_lake": "ln km to a lake >= 2 ha", "near_lake": "within 100 m of a lake", "restricted": "military, forest, protected or airport land",
    "go111": "GO 111 zone (10 km of Osman/Himayat Sagar)", "ln_votes": "ln votes per km2 (2018 booths)",
    "ln_wp": "ln WorldPop per km2", "ac51": "AC Rajendranagar", "ac52": "AC Serilingampally", "p2020": "period 2020-23",
    "road_gain": "road km added in 4 x 4 km during the period (/100)", "chg_prev_1km": "share of 1 km developed in 2017-20",
    "go111_x_p2020": "GO 111 zone x 2020-23 (after the 2022 repeal)"}


def prep(d):
    d = d.copy()
    for k in ["airport", "orr", "metro", "jobs", "cbd", "major_road", "urban", "lake"]:
        d[f"ln_d_{k}"] = np.log(d[f"d_{k}"] + 0.1)
    d["major_km"] = d.major_km_4km / 10; d["minor_km"] = d.minor_km_4km / 100
    d["road_gain"] = d.road_gain_4km / 100
    d["ln_viirs"] = np.log1p(d.viirs_1km.clip(lower=0)); d["elev_100m"] = d.elev_m / 100
    d["ln_votes"] = np.log1p(d.votes_kde1km); d["ln_wp"] = np.log1p(d.worldpop_1km)
    d["p2020"] = (d.t0 == 2020).astype(int); d["ac51"] = (d.ac == 51).astype(int); d["ac52"] = (d.ac == 52).astype(int)
    d["go111_x_p2020"] = d.go111 * d.p2020
    return d


def full(pooled=True):
    return sum(GROUPS.values(), []) + ["ac51", "ac52"] + (["p2020"] if pooled else [])


def fit(d, xs):
    X = sm.add_constant(d[xs].astype(float))
    r = sm.Logit(d.change, X).fit(disp=0, cov_type="cluster", cov_kwds={"groups": d.tile.values}, maxiter=300)
    tau = (d.w * d.change).sum() / d.w.sum(); yb = d.change.mean()
    return r, r.params["const"] - np.log(((1 - tau) / tau) * (yb / (1 - yb)))


def cv_auc(d, xs, k=5):
    p = np.zeros(len(d))
    if not xs:
        return 0.5
    for tr, te in GroupKFold(k).split(d, groups=d.tile):
        X = sm.add_constant(d[xs].astype(float), has_constant="add")
        p[te] = sm.Logit(d.change.iloc[tr], X.iloc[tr]).fit(disp=0, maxiter=300).predict(X.iloc[te])
    return roc_auc_score(d.change, p)


def wald(r, vs):
    """Cluster-robust Wald chi2 that all coefficients in vs are zero."""
    b = r.params[vs].values; V = r.cov_params().loc[vs, vs].values
    s = float(b @ np.linalg.pinv(V) @ b); return s, len(vs), chi2.sf(s, len(vs))


def pop_prob(r, const, X):
    """Development probability in the population (corrected constant)."""
    b = r.params.copy(); b["const"] = const
    return 1 / (1 + np.exp(-(sm.add_constant(X.astype(float), has_constant="add")[b.index] @ b)))


def vif(d, xs):
    X = d[xs].astype(float).values; X = (X - X.mean(0)) / X.std(0)
    C = np.corrcoef(X, rowvar=False); return pd.Series(np.diag(np.linalg.pinv(C)), index=xs)


def morans_i(d, resid, k=8, nperm=199):
    t = cKDTree(d[["x", "y"]].values); _, nb = t.query(d[["x", "y"]].values, k + 1); nb = nb[:, 1:]
    z = resid - resid.mean()
    I = (z[:, None] * z[nb]).sum() / (len(z) * k) / (z @ z / len(z))
    perm = [((zp := RNG.permutation(z))[:, None] * zp[nb]).sum() / (len(z) * k) / (z @ z / len(z)) for _ in range(nperm)]
    return I, (1 + sum(p >= I for p in perm)) / (nperm + 1), float(np.median(t.query(d[["x", "y"]].values, k + 1)[0][:, -1]))


def main():
    d = prep(pd.read_parquet(CH / "trial_cells_full.parquet"))
    n_all = len(d); d = d.dropna(subset=full(True)).reset_index(drop=True)
    print(f"{n_all - len(d)} cells without night lights / terrain (grid edge) dropped; {len(d):,} left")
    sets = {"2017-2020": d[d.t0 == 2017], "2020-2023": d[d.t0 == 2020], "pooled": d}
    coefs, groups, effects, checks, calib = [], [], [], [], []
    for nm, s in sets.items():
        xs = full(nm == "pooled"); r, c = fit(s, xs)
        auc_full = cv_auc(s, xs); sd = s[xs].std()
        for v in ["const"] + xs:
            coefs.append({"sample": nm, "var": v, "label": LABEL.get(v, v), "coef": c if v == "const" else r.params[v],
                          "se": r.bse[v], "z": r.tvalues[v], "p": r.pvalues[v],
                          "OR_per_SD": np.exp(r.params[v] * sd[v]) if v != "const" else np.nan})
        # average marginal effect of +1 SD on the population 3-year development probability
        X = s[xs]; p0 = pop_prob(r, c, X); wt = s.w / s.w.sum(); base = float((wt * p0).sum())
        for v in xs:
            binary = set(s[v].unique()) <= {0, 1}
            if binary:      # everyone 1 vs everyone 0
                X0_, X1 = X.copy(), X.copy(); X0_[v] = 0; X1[v] = 1; pa = pop_prob(r, c, X0_)
            else:           # everyone +1 SD
                X1 = X.copy(); X1[v] = X1[v] + sd[v]; pa = p0
            effects.append({"sample": nm, "var": v, "label": LABEL.get(v, v), "binary": binary, "share_1": s[v].mean() if binary else np.nan,
                            "AME_pp": 100 * float((wt * (pop_prob(r, c, X1) - pa)).sum()), "base_rate_pct": 100 * base})
        others = [x for x in xs if x not in sum(GROUPS.values(), [])]
        r0, _ = fit(s, others)
        for g, vs in GROUPS.items():
            st, df, p = wald(r, vs)
            rd_, _ = fit(s, [x for x in xs if x not in vs])
            lr = 2 * (r.llf - rd_.llf)
            groups.append({"sample": nm, "group": g, "name": GNAME[g], "k": df, "wald_chi2": st, "p_wald": p,
                           "LR": lr, "p_LR": chi2.sf(lr, df), "AUC_alone": cv_auc(s, vs + others),
                           "AUC_without": cv_auc(s, [x for x in xs if x not in vs]), "AUC_full": auc_full,
                           "AUC_fixed_only": cv_auc(s, others) if others else 0.5})
        groups.append({"sample": nm, "group": "all", "name": "full model", "k": len(xs) - len(others), "LR": 2 * (r.llf - r0.llf),
                       "p_LR": chi2.sf(2 * (r.llf - r0.llf), len(xs) - len(others)), "AUC_full": auc_full,
                       "McFadden_R2": r.prsquared, "n": len(s), "changers": int(s.change.sum())})
        if nm != "pooled":
            v = vif(s, xs); I, pI, dk = morans_i(s, ((s.change - r.predict()) / np.sqrt(r.predict() * (1 - r.predict()))).values)
            checks.append({"sample": nm, "check": "Moran's I of residuals (8 nearest)", "stat": I, "p": pI,
                           "note": f"median distance to the 8th neighbour {dk / 1000:.2f} km"})
            for k_, vv in v.items():
                checks.append({"sample": nm, "check": "VIF", "var": k_, "label": LABEL.get(k_, k_), "stat": vv})
        # calibration in the population (weighted), deciles of predicted probability
        q = pd.qcut(p0.rank(method="first"), 10, labels=False)
        for k_, g in s.assign(p=p0, q=q).groupby("q"):
            calib.append({"sample": nm, "decile": k_ + 1, "pred_pct": 100 * np.average(g.p, weights=g.w),
                          "obs_pct": 100 * np.average(g.change, weights=g.w), "n": len(g)})

    # stability: all slopes x period (pooled)
    xs = full(True); dd = d.copy(); inter = []
    for v in [x for x in xs if x not in ("p2020",)]:
        dd[f"{v}_x_p"] = dd[v] * dd.p2020; inter.append(f"{v}_x_p")
    ri, _ = fit(dd, xs + inter); st, df, p = wald(ri, inter)
    checks.append({"sample": "pooled", "check": "slopes differ between periods (Wald, all x period)", "stat": st, "df": df, "p": p})
    for v in inter:
        if ri.pvalues[v] < 0.05:
            checks.append({"sample": "pooled", "check": "slope differs between periods", "var": v[:-4],
                           "label": LABEL.get(v[:-4], v[:-4]), "stat": ri.params[v], "p": ri.pvalues[v]})
    # temporal transfer: fit on 2017-20, predict 2020-23
    a, b = sets["2017-2020"], sets["2020-2023"]; xs = full(False)
    ra = sm.Logit(a.change, sm.add_constant(a[xs].astype(float))).fit(disp=0, maxiter=300)
    checks.append({"sample": "2017-20 -> 2020-23", "check": "temporal transfer AUC (fit 2017-20, predict 2020-23)",
                   "stat": roc_auc_score(b.change, ra.predict(sm.add_constant(b[xs].astype(float)))),
                   "note": f"2020-23 own cross-validated AUC {cv_auc(b, xs):.3f}"})
    # causal-direction checks
    for nm, s, extra in [("pooled", d, ["road_gain"]), ("2020-2023", b, ["chg_prev_1km"]), ("pooled", d, ["go111_x_p2020"])]:
        x0 = full(nm == "pooled"); r1, _ = fit(s, x0 + extra); r0_, _ = fit(s, x0)
        for v in extra:
            checks.append({"sample": nm, "check": f"added: {LABEL[v]}", "var": v, "stat": r1.params[v], "z": r1.tvalues[v],
                           "p": r1.pvalues[v], "OR_per_SD": np.exp(r1.params[v] * s[v].std()),
                           "note": "; ".join(f"{LABEL[k]} {r0_.params[k]:+.2f} -> {r1.params[k]:+.2f}"
                                             for k in ("major_km", "minor_km", "res_1km", "go111") if k in x0)})
    C, Gp, E, K, Cal = map(pd.DataFrame, (coefs, groups, effects, checks, calib))
    for nm, t in (("coefs", C), ("groups", Gp), ("effects", E), ("checks", K), ("calibration", Cal)):
        t.to_csv(OUT / f"{nm}.csv", index=False)
    pd.to_pickle({"C": C, "G": Gp, "E": E, "K": K, "Cal": Cal, "LABEL": LABEL}, OUT / "results.pkl")
    pd.set_option("display.width", 250)
    print(Gp.round(3).to_string(index=False)); print(C[C["sample"] == "pooled"].round(3).to_string(index=False))
    print(K.round(3).to_string(index=False)); print(Cal.round(3).to_string(index=False))
    print(E[E["sample"] == "pooled"].round(3).to_string(index=False))


if __name__ == "__main__":
    main()
