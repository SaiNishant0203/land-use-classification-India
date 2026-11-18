"""Do the Earth Engine factors survive a control for Dynamic World 'built' / 'trees' probability in t0-1?
(If a factor only proxies 'Dynamic World already sees this cell as built', it is a map-error detector, not a driver.)"""
import sys, pandas as pd
sys.path.insert(0, "experiments/feature_tests"); import harness as H
F = pd.read_parquet("experiments/feature_tests/feat_ee.parquet").merge(pd.read_parquet("experiments/feature_tests/feat_ee_built.parquet"), on=["period", "x", "y"])
CTRL = ["dw_built", "dw_trees"]
rows = []
for rule in H.RULES:
    m, d, final = H.base_data(rule); d = d.merge(F, on=["period", "x", "y"]).dropna(subset=list(F.columns[3:]))
    rc = H.ll_fit(d, final + CTRL)
    rows.append({"rule": rule, "factor": "CONTROL dw_built, dw_trees", "coef (t)": f"built {rc.params.dw_built:+.2f} ({rc.tvalues.dw_built:+.1f}), trees {rc.params.dw_trees:+.2f} ({rc.tvalues.dw_trees:+.1f})",
                 "d_AUC_cv vs base": round(H.cv_auc(d, final + CTRL) - H.cv_auc(d, final), 4)})
    a0 = H.cv_auc(d, final + CTRL); t0 = H.transfer_auc(d, final + CTRL)
    for x in ["dw_crops", "dw_bare", "dw_shrub", "dw_grass", "ndvi_amp", "ndvi_dry", "ln_hand", "wet_yrs_250m"]:
        r = H.ll_fit(d, final + CTRL + [x]); per = []
        for y in (2017, 2020):
            rp = H.ll_fit(d[d.t0 == y], [v for v in final if v != "p2020"] + CTRL + [x]); per.append(f"{rp.params[x]:+.2f} ({rp.tvalues[x]:+.1f})")
        rows.append({"rule": rule, "factor": x, "coef (t)": f"{r.params[x]:+.3f} ({r.tvalues[x]:+.1f})", "17-20 | 20-23": " | ".join(per),
                     "d_AUC_cv vs base+control": round(H.cv_auc(d, final + CTRL + [x]) - a0, 4),
                     "d_AUC_transfer vs base+control": round(H.transfer_auc(d, final + CTRL + [x]) - t0, 4)})
    print(rule, "cells", len(d), "changes", int(d.change.sum()), flush=True)
R = pd.DataFrame(rows); R.to_csv("experiments/feature_tests/ee_control.csv", index=False); print(R.to_string())
