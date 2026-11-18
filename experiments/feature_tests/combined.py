"""Combined block of the candidates that passed one by one, and a swap of straight-line for network distances."""
import sys, pandas as pd
sys.path.insert(0, "experiments/feature_tests")
import harness as H
F = pd.read_parquet("experiments/feature_tests/feat_local.parquet")
for f in ("feat_udise", "feat_network"):
    F = F.merge(pd.read_parquet(f"experiments/feature_tests/{f}.parquet"), on=["period", "x", "y"])
G = {"block: network time + settlement (both periods)": ["ln_tt_cbd", "ln_tt_orr", "ln_d_govsch", "ps_1km"],
     "block + lagged momentum (2020-23 only)": ["ln_tt_cbd", "ln_tt_orr", "ln_d_govsch", "ps_1km", "lag_chg_pct"]}
res = pd.concat([H.test(r, F, G) for r in H.RULES])
res.to_csv("experiments/feature_tests/combined.csv", index=False)
# swap: replace ln_d_cbd / ln_d_orr by network times (same number of parameters)
import numpy as np
for rule in H.RULES:
    m, d, final = H.base_data(rule); d = d.merge(F, on=["period", "x", "y"])
    sw = [{"ln_d_cbd": "ln_tt_cbd", "ln_d_orr": "ln_tt_orr"}.get(v, v) for v in final]
    for nm, xs in (("straight-line", final), ("network", sw)):
        r = H.ll_fit(d, xs)
        print(rule, nm, "rho2 %.4f AIC %.0f AUCcv %.4f transfer %.4f" % (H.rho2(d, r), r.aic, H.cv_auc(d, xs), H.transfer_auc(d, xs)),
              {v: f"{r.params[v]:+.3f} ({r.tvalues[v]:+.1f})" for v in xs if "cbd" in v or "orr" in v})
