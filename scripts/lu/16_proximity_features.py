"""
Do proximity (distance) features help the land-use CLASSIFIER, and what does it learn from them?

Feature sets, all trained on the same 120k-pixel subsample and scored the same two ways as
15_feature_analysis.py (12 km spatial-block CV on the OSM-derived labels; stratum-weighted
macro-F1 on the hand-labelled pixels):
  physical (53)                  the current default
  + major-road distance          one local distance
  + all proximity                landmarks, ORR interchanges, metro, major roads (10 distances)
  + x, y coordinates             CONTROL: if this gains as much as proximity, the model is
                                 learning "where on the map", not "near what"
  proximity only / x, y only     how far location alone goes
  all 181 (+ proximity)          the same question with AlphaEarth included

Then, for "physical + all proximity": SHAP per class for every feature, and how the
contribution of each distance changes with the distance (dependence curves).

Outputs: outputs/lu/proximity_features/
  cv.csv, handlabel.csv, shap_by_class.csv, shap_dependence.csv, shap_dependence.png
"""
import time
import numpy as np, pandas as pd, lightgbm as lgb, geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy.stats import spearmanr
from sklearn.model_selection import GroupKFold
from lu_common import LU, LUOUT, UTM, ROOT, log
import importlib.util as iu


def _mod(name, file):
    s = iu.spec_from_file_location(name, ROOT / "scripts" / "lu" / file)
    m = iu.module_from_spec(s); s.loader.exec_module(m)
    return m


fa = _mod("fa", "15_feature_analysis.py")
px = _mod("px", "20_proximity.py")
eh = fa.eh

OUT = LUOUT / "proximity_features"; OUT.mkdir(exist_ok=True)
CLASSES, CNAME = fa.CLASSES, fa.CNAME
PROX = ["d_employment", "d_hitec_cyber_towers", "d_financial_district", "d_cbd_abids", "d_charminar",
        "d_secunderabad", "d_airport_rgia", "d_orr_access", "d_metro_2020", "d_major_road_2023"]
XY = ["x", "y"]
BASE = "physical (53)"


def family(c):
    return "Proximity" if c.startswith("d_") else "Coordinates" if c in XY else fa.family(c)


def feature_sets(cols):
    phys = [c for c in cols if not fa.family(c).startswith("AlphaEarth")]
    return {
        BASE: phys,
        "physical + major-road distance": phys + ["d_major_road_2023"],
        "physical + all proximity": phys + PROX,
        "physical + x, y coordinates": phys + XY,
        "proximity only": PROX,
        "x, y only": XY,
        "all 181": cols,
        "all 181 + all proximity": cols + PROX,
    }


def hand_labels(cols, P):
    V = fa.validation_features(cols)
    g = gpd.read_file(LU / "validation_points.gpkg", layer="validation_pixels").to_crs(UTM)
    c = g.geometry.centroid
    V = V.merge(pd.DataFrame({"pid": g.pid, "x": c.x, "y": c.y}), on="pid")
    V = pd.concat([V, P.at(V.x.values, V.y.values)[PROX]], axis=1)
    return V[(V.confidence.fillna(3) <= 2) & V.true_class.notna()].reset_index(drop=True)


def paired_diff(ref, pred, base, strata, W, B=1000, seed=0):
    """95% interval of macro-F1(pred) - macro-F1(base), same within-stratum resample for both."""
    rng = np.random.default_rng(seed)
    idx_by = [np.nonzero(strata == h)[0] for h in np.unique(strata)]
    d = []
    for _ in range(B):
        ii = np.concatenate([rng.choice(ix, len(ix)) for ix in idx_by])
        d.append(eh.weighted(ref[ii], pred[ii], strata[ii], W)[0]["macro_F1"]
                 - eh.weighted(ref[ii], base[ii], strata[ii], W)[0]["macro_F1"])
    return tuple(np.percentile(d, [2.5, 97.5]))


def shap_report(m, fcols, sub):
    X = sub.loc[sub.groupby("label").sample(n=4000, random_state=0).index, fcols]
    K, Fn = len(CLASSES), len(fcols)
    sv = m.booster_.predict(X, pred_contrib=True).reshape(len(X), K, Fn + 1)[:, :, :Fn]
    mabs = np.abs(sv).mean(0)                                   # (K, F)
    t = pd.DataFrame(mabs.T, index=fcols, columns=[CNAME[c] for c in CLASSES])
    t["total"] = t.sum(1)
    for k, c in enumerate(CLASSES):                             # sign: does a larger value push towards the class?
        t[f"dir_{CNAME[c]}"] = [spearmanr(X.iloc[:, j], sv[:, k, j]).statistic if sv[:, k, j].std() > 0 else 0
                                for j in range(Fn)]
    t.insert(0, "family", [family(f) for f in fcols])
    t = t.sort_values("total", ascending=False)
    t.insert(1, "rank", range(1, Fn + 1))
    t.to_csv(OUT / "shap_by_class.csv")
    fam = t.groupby("family")[[CNAME[c] for c in CLASSES] + ["total"]].sum()
    log("share of total |SHAP| by family and class (%):\n"
        + (100 * fam / fam.sum()).round(1).sort_values("total", ascending=False).to_string())
    log("proximity features, rank among %d and mean |SHAP|:\n" % Fn
        + t[t.family == "Proximity"][["rank"] + [CNAME[c] for c in CLASSES] + ["total"]].round(3).to_string())

    show = ["d_major_road_2023", "d_employment", "d_orr_access", "d_cbd_abids", "d_metro_2020", "d_airport_rgia"]
    rows = []
    for f in show:
        j = fcols.index(f); v = X[f].values
        edges = np.unique(np.quantile(v, np.linspace(0, 1, 21)))
        b = np.clip(np.digitize(v, edges[1:-1]), 0, len(edges) - 2)
        mid = pd.Series(v).groupby(b).median()
        for k in (0, 1):
            med = pd.Series(sv[:, k, j]).groupby(b).median()
            rows += [{"feature": f, "class": CNAME[CLASSES[k]], "km": mid[i], "median_shap": med[i]} for i in med.index]
    d = pd.DataFrame(rows)
    d.to_csv(OUT / "shap_dependence.csv", index=False)
    dependence_plot(d)


def dependence_plot(d):
    from matplotlib.ticker import FixedLocator, NullLocator, FuncFormatter
    fig, ax = plt.subplots(2, 3, figsize=(15, 8))
    for a, (f, g) in zip(ax.ravel(), d.groupby("feature", sort=False)):
        for c, col in (("residential", "#c98a1e"), ("non_res", "#b23a2c")):
            h = g[g["class"] == c]
            a.plot(h.km, h.median_shap, "o-", color=col, ms=3, label=c.replace("non_res", "non-residential"))
        a.axhline(0, color="grey", lw=0.8); a.set_xscale("log")
        ticks = [t for t in (0.05, 0.1, 0.2, 0.5, 1, 2, 5, 10, 20, 50) if g.km.min() * 0.8 <= t <= g.km.max() * 1.25]
        a.xaxis.set_major_locator(FixedLocator(ticks)); a.xaxis.set_minor_locator(NullLocator())
        a.xaxis.set_major_formatter(FuncFormatter(lambda t, _: f"{t:g}"))
        a.set_xlabel(f"{f} (km, log scale)"); a.set_ylabel("SHAP (log-odds pushed towards the class)")
        a.grid(alpha=0.3)
    ax[0, 0].legend()
    fig.suptitle("How each distance moves the prediction (physical + all proximity model)")
    fig.tight_layout(); fig.savefig(OUT / "shap_dependence.png", dpi=130); plt.close(fig)


def main():
    t0 = time.time()
    s, cols = fa.load()
    P = px.Prox(years=("2023",))
    sub = s.groupby("label").sample(n=fa.N_SUB // 5, random_state=2).reset_index(drop=True)   # same subsample as 15
    sub = pd.concat([sub, P.at(sub.x.values, sub.y.values)[PROX]], axis=1)
    y = sub.label.values
    folds = list(GroupKFold(n_splits=5).split(sub, y, sub.block))
    V = hand_labels(cols, P)
    W = pd.read_csv(LU / "validation_strata.csv", index_col=0)["weight"].to_dict()
    ref, st = V.true_class.astype(int).values, V.stratum.values
    log(f"{len(sub)} training px in {sub.block.nunique()} blocks; {len(V)} hand-labelled px "
        f"({(ref == 2).sum()} non-residential)")

    cv_rows, hl_rows, preds = [], [], {}
    for name, fc in feature_sets(cols).items():
        oof = np.zeros(len(sub), int)
        for tr, te in folds:
            oof[te] = lgb.LGBMClassifier(**fa.PARAMS).fit(sub.iloc[tr][fc], y[tr]).predict(sub.iloc[te][fc])
        cv_rows.append({"feature_set": name, "n_features": len(fc), **fa.metrics(y, oof)})
        m = lgb.LGBMClassifier(**fa.PARAMS).fit(sub[fc], y)
        preds[name] = m.predict(V[fc])
        r, _ = eh.weighted(ref, preds[name], st, W)
        lo, hi = eh.bootstrap(ref, preds[name], st, W, B=500)
        dlo, dhi = (0.0, 0.0) if name == BASE else paired_diff(ref, preds[name], preds[BASE], st, W)
        hl_rows.append({"feature_set": name, "n_features": len(fc), "macro_F1": r["macro_F1"], "lo": lo, "hi": hi,
                        "diff_vs_physical": r["macro_F1"] - hl_rows[0]["macro_F1"] if hl_rows else 0.0,
                        "diff_lo": dlo, "diff_hi": dhi, **{f"F1_{CNAME[c]}": r[f"F1_{c}"] for c in CLASSES}})
        log(f"{name:32s} n={len(fc):3d}  CV {cv_rows[-1]['macro_f1']:.3f}  hand {r['macro_F1']:.3f} "
            f"[{lo:.2f}-{hi:.2f}]  diff {hl_rows[-1]['diff_vs_physical']:+.3f} [{dlo:+.3f},{dhi:+.3f}]  "
            f"({(time.time() - t0) / 60:.0f} min)")
        pd.DataFrame(cv_rows).to_csv(OUT / "cv.csv", index=False)
        pd.DataFrame(hl_rows).to_csv(OUT / "handlabel.csv", index=False)
        if name == "physical + all proximity":
            shap_report(m, fc, sub)


if __name__ == "__main__":
    main()
