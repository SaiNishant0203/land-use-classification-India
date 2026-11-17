"""
Land-use transition (choice) models for one period y0 -> y1, for pixels undeveloped at y0.

    python 22_choice_models.py 2017 2023      (also 2017 2020, 2020 2023)


  A  Binary logit: developed by 2023 (yes / no)
  B  Multinomial logit (MNL): stays undeveloped / becomes residential / becomes non-residential
  C  LightGBM + SHAP / partial dependence: non-linear distance-decay curves
  D  Context classification: the MNL re-estimated separately for low / medium / high
     surrounding density (2017 building cover within 610 m), and for core / middle / periphery
     rings by distance to the old CBD
  E  Robustness: development thresholds, 2023 road network (endogenous) vs 2017, metro 2020

Distances enter as ln(km + 0.1) and every continuous variable is standardised, so a coefficient
is the change in log-odds per 1 SD. Standard errors are clustered by 4 km tile (spatial
autocorrelation). Predictive skill is reported with 12 km spatial-block cross-validation.

Main specification drops the metro distance: it is collinear with the CBD distance (VIF ~9)
and was not robust in earlier work; it is reported as a robustness column instead.

Input:  data/processed/lu/transition_panel.parquet (21_transition_data.py), via period(y0, y1)
Output: outputs/lu/choice_<y0>_<y1>/  (tables, figures, REPORT.md)
"""
import numpy as np, pandas as pd, statsmodels.api as sm, lightgbm as lgb
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
from sklearn.model_selection import GroupKFold
from sklearn.metrics import roc_auc_score
from lu_common import LU, LUOUT, log

import sys, importlib.util as iu
_s = iu.spec_from_file_location("td", LU.parents[2] / "scripts/lu/21_transition_data.py")
td = iu.module_from_spec(_s); _s.loader.exec_module(td)

OUT = None
DIST = ["d_employment", "d_cbd_abids", "d_airport_rgia", "d_orr_access", "d_major_road_t0"]
CTRL = ["cov_61_t0", "cov_15_t0", "ndvi_15_t0", "viirs_61_t0", "forest_t0"]
LABEL = {"d_employment": "dist. to HITEC City / Financial District", "d_cbd_abids": "dist. to old CBD (Abids)",
         "d_airport_rgia": "dist. to airport", "d_orr_access": "dist. to ORR interchange",
         "d_major_road_t0": "dist. to major road (start-year network)", "d_metro_t0": "dist. to metro station (open at start)",
         "d_major_road_t1": "dist. to major road (end-year network, endogenous)", "d_metro_2020": "dist. to metro station (open 2020)",
         "cov_61_t0": "building cover within 610 m (start)", "cov_15_t0": "building cover within 150 m (start)",
         "ndvi_15_t0": "NDVI within 150 m (start)", "viirs_61_t0": "night lights within 610 m (start)",
         "forest_t0": "start class = forest/trees"}


def prep(D, dist=DIST):
    d = D[D.undeveloped_t0].copy()
    d["forest_t0"] = (d.start_class_t0 == 4).astype(float)
    X = pd.DataFrame(index=d.index)
    for c in dist:
        X[c] = np.log(d[c] + 0.1)
    for c in CTRL:
        X[c] = d[c]
    mu, sd = X.mean(), X.std().replace(0, 1)
    Z = (X - mu) / sd
    Z.loc[:, "forest_t0"] = d["forest_t0"]                 # keep the dummy as 0/1
    return d, Z, mu, sd


def table(fit, names, eq=None):
    p = fit.params if eq is None else fit.params[eq]
    b = fit.bse if eq is None else fit.bse[eq]
    pv = fit.pvalues if eq is None else fit.pvalues[eq]
    t = pd.DataFrame({"coef": p, "se": b, "p": pv, "odds_ratio": np.exp(p)})
    t["sig"] = pd.cut(t.p, [-1, 0.001, 0.01, 0.05, 1], labels=["***", "**", "*", ""])
    t.index = ["const"] + [LABEL.get(n, n) for n in names]
    return t


def fit_logit(y, Z, groups):
    X = sm.add_constant(Z)
    try:
        return sm.Logit(y, X).fit(disp=False, maxiter=300, cov_type="cluster", cov_kwds={"groups": groups})
    except Exception:
        return sm.Logit(y, X).fit(disp=False, maxiter=300)


def fit_mnl(y, Z, groups):
    X = sm.add_constant(Z)
    try:
        return sm.MNLogit(y, X).fit(disp=False, maxiter=500, method="bfgs",
                                    cov_type="cluster", cov_kwds={"groups": groups}), "cluster(tile)"
    except Exception as e:
        log(f"  MNL clustered SE failed ({str(e)[:80]}); using default SE")
        return sm.MNLogit(y, X).fit(disp=False, maxiter=500, method="bfgs"), "default (not clustered)"


def spatial_auc(d, Z, y, make):
    oof = np.zeros(len(y))
    for tr, te in GroupKFold(min(5, d.block12.nunique())).split(Z, y, d.block12):
        oof[te] = make().fit(Z.iloc[tr], y[tr]).predict_proba(Z.iloc[te])[:, 1]
    return roc_auc_score(y, oof)


class SkLogit:
    def fit(self, X, y):
        self.m = sm.Logit(y, sm.add_constant(X, has_constant="add")).fit(disp=False, maxiter=300); return self
    def predict_proba(self, X):
        p = self.m.predict(sm.add_constant(X, has_constant="add")); return np.c_[1 - p, p]


def curves(mnl, Z, mu, sd, var, km):
    """MNL predicted probabilities along one distance, other variables at their sample means."""
    base = Z.mean().to_frame().T
    rows = []
    for k in km:
        z = base.copy(); z[var] = (np.log(k + 0.1) - mu[var]) / sd[var]
        p = mnl.predict(sm.add_constant(z, has_constant="add"))
        rows.append([k, *np.asarray(p)[0]])
    return pd.DataFrame(rows, columns=["km", "p_none", "p_res", "p_nonres"])


def main(y0=2017, y1=2023):
    import os
    global OUT
    dry = os.environ.get("DRY")
    OUT = LUOUT / (f"choice_{y0}_{y1}" + ("_dryrun" if dry else "")); OUT.mkdir(exist_ok=True)
    D = td.period(pd.read_parquet(LU / ("transition_panel_dryrun.parquet" if dry else "transition_panel.parquet")), y0, y1)
    d, Z, mu, sd = prep(D)
    y3 = d.outcome.values; yb = (y3 > 0).astype(int)
    g = d.tile.values
    md = [f"# Land-use transition models, HMDA {y0} → {y1}\n",
          "*Auto-generated by `scripts/lu/22_choice_models.py`.*\n",
          f"- Sample: {len(D):,} random 10 m pixels; **{len(d):,} undeveloped in {y0}** are modelled.",
          f"- Outcome among them: stays undeveloped {np.mean(y3 == 0):.1%}, becomes residential "
          f"{np.mean(y3 == 1):.2%}, becomes non-residential {np.mean(y3 == 2):.2%}.",
          "- Development is read from Open Buildings 2.5D building cover; the function of new "
          f"development comes from the 53-feature physical model applied to {y1} inputs.",
          "- Distances enter as standardised ln(km + 0.1): a negative coefficient means **closer → more likely**.",
          "- Standard errors are clustered by 4 km tile.\n"]

    # A: binary logit
    A = fit_logit(yb, Z, g)
    tA = table(A, list(Z.columns)); tA.to_csv(OUT / "A_binary_logit.csv")
    aucA = spatial_auc(d, Z, yb, SkLogit)
    aucG = spatial_auc(d, Z, yb, lambda: lgb.LGBMClassifier(n_estimators=300, learning_rate=0.05,
                                                             num_leaves=31, verbose=-1, n_jobs=14))
    log(f"A: n={len(d)}, McFadden R2={A.prsquared:.3f}, spatial-CV AUC logit {aucA:.3f} / LightGBM {aucG:.3f}")
    md += [f"## A. Binary logit: developed by {y1}\n",
           f"McFadden pseudo-R² {A.prsquared:.3f}. Spatial-block CV AUC: logit **{aucA:.3f}**, LightGBM **{aucG:.3f}**.\n",
           tA.round(3).to_markdown(), "\n"]

    # B: MNL
    B, se_kind = fit_mnl(y3, Z, g)
    cols = list(Z.columns)
    tB1, tB2 = table(B, cols, 0), table(B, cols, 1)
    tB = pd.concat({"residential vs none": tB1, "non-residential vs none": tB2}, axis=1)
    tB.to_csv(OUT / "B_mnl.csv")
    log(f"B: MNL McFadden R2={B.prsquared:.3f}, SE {se_kind}")
    md += ["## B. Multinomial logit: none / residential / non-residential\n",
           f"McFadden pseudo-R² {B.prsquared:.3f}; standard errors {se_kind}.\n",
           tB.xs("coef", axis=1, level=1).join(tB.xs("sig", axis=1, level=1), rsuffix=" sig").round(3).to_markdown(), "\n"]

    # B curves: probability vs distance
    km = np.r_[0.5, 1, 2, 3, 5, 7.5, 10, 15, 20, 30, 40]
    fig, ax = plt.subplots(1, 3, figsize=(14, 4))
    for a, v in zip(ax, ["d_employment", "d_orr_access", "d_major_road_t0"]):
        cv = curves(B, Z, mu, sd, v, km if v == "d_employment" else km[km <= 15])
        cv.to_csv(OUT / f"B_curve_{v}.csv", index=False)
        a.plot(cv.km, 100 * cv.p_res, "o-", color="#e8a33d", label="→ residential")
        a.plot(cv.km, 100 * cv.p_nonres, "o-", color="#c0392b", label="→ non-residential")
        a.set_xscale("log"); a.set_xlabel(LABEL[v] + " (km)"); a.set_ylabel(f"probability {y0}→{y1} (%)")
        a.grid(alpha=.3)
    ax[0].legend(); fig.suptitle(f"MNL: probability an undeveloped pixel is developed by {y1}, other variables at means")
    fig.tight_layout(); fig.savefig(OUT / "B_probability_curves.png", dpi=150); plt.close(fig)
    md += ["![curves](B_probability_curves.png)\n"]

    # C: LightGBM + SHAP dependence (multiclass)
    Xraw = d[DIST + ["cov_61_t0", "cov_15_t0", "ndvi_15_t0", "viirs_61_t0"]].copy()
    Xraw["forest_t0"] = (d.start_class_t0 == 4).astype(int)
    gbm = lgb.LGBMClassifier(n_estimators=300, learning_rate=0.05, num_leaves=31, class_weight="balanced",
                             verbose=-1, n_jobs=14).fit(Xraw, y3)
    sub = Xraw.sample(min(20000, len(Xraw)), random_state=0)
    sh = gbm.booster_.predict(sub, pred_contrib=True).reshape(len(sub), 3, Xraw.shape[1] + 1)[:, :, :-1]
    imp = pd.DataFrame(np.abs(sh).mean(0).T, index=Xraw.columns, columns=["none", "residential", "non_res"])
    imp.sort_values("non_res", ascending=False).to_csv(OUT / "C_shap_importance.csv")
    fig, ax = plt.subplots(2, 3, figsize=(14, 7.5)); ax.ravel()[-1].axis("off")
    for a, v in zip(ax.ravel(), DIST):
        for k, col, nm in ((1, "#e8a33d", "residential"), (2, "#c0392b", "non-res")):
            a.scatter(sub[v], sh[:, k, Xraw.columns.get_loc(v)], s=2, alpha=.25, color=col, label=nm)
        a.set_xscale("log"); a.axhline(0, color="k", lw=.5); a.set_xlabel(LABEL[v] + " (km)")
        a.set_ylabel("SHAP (log-odds)")
    ax[0, 0].legend(markerscale=6)
    fig.suptitle("LightGBM: effect of each distance on becoming residential / non-residential (SHAP)")
    fig.tight_layout(); fig.savefig(OUT / "C_shap_distance_decay.png", dpi=150); plt.close(fig)
    md += ["## C. LightGBM + SHAP (non-linear distance decay)\n",
           "Mean |SHAP| per class:\n", imp.sort_values("non_res", ascending=False).round(3).to_markdown(), "\n",
           "![shap](C_shap_distance_decay.png)\n"]

    # D: context classification
    md += ["## D. Context classification: separate MNLs by context\n"]
    ctx = {"density": pd.qcut(d.cov_61_t0.rank(method="first"), 3, labels=["low", "medium", "high"]),
           "ring": pd.cut(d.d_cbd_abids, [0, 10, 25, 1e9], labels=["core <10 km", "middle 10-25 km", "periphery >25 km"])}
    for nm, seg in ctx.items():
        res = {}
        for lv in seg.cat.categories:
            m = (seg == lv).values
            if (y3[m] == 2).sum() < 30 or (y3[m] == 1).sum() < 30:
                log(f"  D {nm}={lv}: too few events, skipped"); continue
            f, _ = fit_mnl(y3[m], Z[m].drop(columns=["cov_61_t0"]), g[m])
            t = table(f, [c for c in cols if c != "cov_61_t0"], 1)
            res[f"{lv} (n={m.sum():,}, nonres={int((y3[m] == 2).sum())})"] = t.coef.round(3).astype(str) + t.sig.astype(str)
        if res:
            T = pd.DataFrame(res); T.to_csv(OUT / f"D_context_{nm}_nonres.csv")
            md += [f"**By {nm}**: coefficients for *non-residential vs none*.\n", T.to_markdown(), "\n"]

    # E: robustness
    rob = []
    for nm, f in {"developed = cover >=10%": lambda D: (D.ob_cov_t1 >= 0.10) & (D.cov_7_t1 >= 0.05),
                  "developed = cover >=30%": lambda D: (D.ob_cov_t1 >= 0.30) & (D.cov_7_t1 >= 0.15)}.items():
        yy = f(d).astype(int).values
        r = fit_logit(yy, Z, g)
        rob.append(pd.Series(r.params[1:len(DIST) + 1].values, index=DIST, name=nm))
    if y0 == 2017 and (D.sisdp_class > 0).mean() > 0.5:      # independent start state from NRSC SIS-DP 2016-19
        D2 = D.copy(); D2["undeveloped_t0"] = D2.sisdp_class.isin([4, 5]) & (D2.ob_cov_t0 < 0.05)
        d2, Z2, _, _ = prep(D2)
        r = fit_logit((d2.outcome.values > 0).astype(int), Z2, d2.tile.values)
        rob.append(pd.Series(r.params[1:len(DIST) + 1].values, index=DIST, name="start = SIS-DP 2016-19 open/forest"))
    for nm, dist in {"end-year roads (endogenous)": [c if c != "d_major_road_t0" else "d_major_road_t1" for c in DIST],
                     "+ metro (open at start)": DIST + ["d_metro_t0"],
                     "+ metro (open by 2020)": DIST + ["d_metro_2020"]}.items():
        d2, Z2, _, _ = prep(D, dist)
        r = fit_logit((d2.outcome.values > 0).astype(int), Z2, d2.tile.values)
        idx = ["d_major_road_t0" if c == "d_major_road_t1" else c for c in dist]
        rob.append(pd.Series(r.params[1:len(dist) + 1].values, index=idx, name=nm))
    R = pd.concat([pd.Series(A.params[1:len(DIST) + 1].values, index=DIST, name="main"), *rob], axis=1)
    R.index = [LABEL.get(i, i) for i in R.index]
    R.to_csv(OUT / "E_robustness.csv")
    md += ["## E. Robustness (binary logit distance coefficients)\n", R.round(3).to_markdown(), "\n"]
    (OUT / "REPORT.md").write_text("\n".join(md), encoding="utf-8")
    log(f"wrote {OUT / 'REPORT.md'}")


if __name__ == "__main__":
    main(*[int(a) for a in sys.argv[1:3]]) if len(sys.argv) > 2 else main()
