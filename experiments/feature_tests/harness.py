"""
Test a candidate factor against the final HMDA Table 18 specification, under both change rules.

For each rule (strict = OUTCOME both, persistence = OUTCOME persist) the base model is the final
specification already estimated by scripts/change/06_table18.py census (outputs/change/<rule>/table18_census/
table18.csv). The candidate is added to it and we report, using the same estimator as 06 (binary logit,
cluster-robust SE by 4 km tile, King-Zeng constant):

  coef, t (pooled), coef / t per period   -> significance and sign stability
  robust Wald chi2 for the added block     -> joint test when a candidate has several columns
  d_rho2                                   -> added in-sample fit
  d_AUC_cv                                 -> added out-of-sample fit, 5-fold by 4 km tile (same folds as base)
  d_AUC_transfer                           -> fit on 2017-20, score on 2020-23 (temporal validity)

Candidates are columns merged onto the samples by (period, x, y). A candidate measured only for one period
(e.g. a lagged outcome) is tested on that period only.

Usage (from the repo root):  python experiments/feature_tests/harness.py <features.parquet> [col ...]
"""
import importlib.util, os, sys, warnings
from pathlib import Path
import numpy as np, pandas as pd, statsmodels.api as sm
from scipy.stats import chi2
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import GroupKFold

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parents[2]
RULES = {"strict": ("both", "hmda"), "persist": ("persist", "hmda_persist")}


def load_06(outcome):
    """Import scripts/change/06_table18.py with REGION=hmda, OUTCOME=<outcome>, census mode."""
    os.environ["REGION"], os.environ["OUTCOME"] = "hmda", outcome
    argv = sys.argv; sys.argv = ["06_table18.py", "census"]
    spec = importlib.util.spec_from_file_location(f"t18_{outcome}", ROOT / "scripts/change/06_table18.py")
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    sys.argv = argv
    return m


def base_data(rule):
    outcome, tag = RULES[rule]
    m = load_06(outcome)
    import contextlib, io
    with contextlib.redirect_stdout(io.StringIO()):
        d = m.prep(pd.read_parquet(m.IN))
    final = [v for v in pd.read_csv(ROOT / f"outputs/change/{tag}/table18_census/table18.csv", index_col=0).index
             if v != "const"]
    d = d.dropna(subset=final).reset_index(drop=True)
    return m, d, final


def ll_fit(d, xs):
    X = sm.add_constant(d[xs].astype(float), has_constant="add")
    return sm.Logit(d.change, X).fit(disp=0, cov_type="cluster", cov_kwds={"groups": d.tile.values}, maxiter=300)


def cv_auc(d, xs):
    p = np.zeros(len(d)); X = sm.add_constant(d[xs].astype(float), has_constant="add")
    for tr, te in GroupKFold(5).split(d, groups=d.tile):
        p[te] = sm.Logit(d.change.iloc[tr], X.iloc[tr]).fit(disp=0, maxiter=300).predict(X.iloc[te])
    return roc_auc_score(d.change, p)


def transfer_auc(d, xs):
    a, b = d[d.t0 == 2017], d[d.t0 == 2020]
    xs = [x for x in xs if x != "p2020"]
    Xa = sm.add_constant(a[xs].astype(float), has_constant="add"); Xb = sm.add_constant(b[xs].astype(float), has_constant="add")
    return roc_auc_score(b.change, sm.Logit(a.change, Xa).fit(disp=0, maxiter=300).predict(Xb))


def rho2(d, r):
    return 1 - r.llf / sm.Logit(d.change, np.ones((len(d), 1))).fit(disp=0).llf


def test(rule, feats, groups):
    """groups: {name: [columns]} candidate blocks to add one block at a time."""
    m, d, final = base_data(rule)
    d = d.merge(feats, on=["period", "x", "y"], how="left")
    out = []
    for name, cols in groups.items():
        s = d.dropna(subset=cols)
        one_period = s.t0.nunique() == 1
        xs = [x for x in final if not (one_period and x == "p2020")]
        r0, r1 = ll_fit(s, xs), ll_fit(s, xs + cols)
        b = r1.params[cols].values; V = r1.cov_params().loc[cols, cols].values
        w = float(b @ np.linalg.pinv(V) @ b)
        row = {"rule": rule, "candidate": name, "cells": len(s), "changes": int(s.change.sum()),
               "periods": "2020-23 only" if one_period and s.t0.iloc[0] == 2020 else ("2017-20 only" if one_period else "both"),
               "wald_chi2": round(w, 1), "df": len(cols), "p": chi2.sf(w, len(cols)),
               "d_rho2": rho2(s, r1) - rho2(s, r0),
               "d_AUC_cv": cv_auc(s, xs + cols) - cv_auc(s, xs)}
        if not one_period:
            row["d_AUC_transfer"] = transfer_auc(s, xs + cols) - transfer_auc(s, xs)
        for c in cols:
            row[f"{c}: coef (t)"] = f"{r1.params[c]:+.3f} ({r1.tvalues[c]:+.1f})"
            if not one_period:
                per = []
                for y in (2017, 2020):
                    rp = ll_fit(s[s.t0 == y], [x for x in xs if x != "p2020"] + cols)
                    per.append(f"{rp.params[c]:+.3f} ({rp.tvalues[c]:+.1f})")
                row[f"{c}: 17-20 | 20-23"] = " | ".join(per)
        out.append(row)
        print({k: (round(v, 4) if isinstance(v, float) else v) for k, v in row.items()}, flush=True)
    return pd.DataFrame(out)


if __name__ == "__main__":
    f = pd.read_parquet(sys.argv[1]); cols = sys.argv[2:] or [c for c in f.columns if c not in ("period", "x", "y")]
    res = pd.concat([test(r, f, {c: [c] for c in cols}) for r in RULES])
    print(res.to_string())
