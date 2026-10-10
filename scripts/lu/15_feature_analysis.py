"""
Feature analysis for the 181-feature LightGBM model.

1. Legend: per-class mean |SHAP| of every feature (and of each feature family), plus the sign of
   its effect (does a higher value push towards or away from the class?).
2. Redundancy: Spearman correlation clusters (|rho| >= 0.9).
3. Reduced / combined feature sets, compared under the SAME spatial CV (12 km blocks,
   GroupKFold) and on the hand-labelled pixels (stratum-weighted, as 07_eval_handlabels.py).
   - family drop-outs
   - AlphaEarth 128 -> PCA (fit on the training fold only)
   - correlation-pruned set
   - top-K by gain importance (ranked inside each training fold, so no selection leakage)

A stratified 120k-pixel subsample is used for speed; the ALL baseline is re-run on the same
subsample so every row of the table is comparable.

Outputs (outputs/lu/features/):
  feature_catalogue.csv      every feature: family, source, window, formula
  shap_by_class.csv          mean |SHAP| per feature x class, + direction
  shap_family_by_class.csv   same, summed by family
  corr_clusters.csv          redundancy clusters
  reduced_sets_cv.csv        spatial-CV macro-F1 / per-class F1 per feature set
  reduced_sets_handlabel.csv hand-label macro-F1 per feature set
"""
import json, pickle, time
import numpy as np, pandas as pd, lightgbm as lgb, geopandas as gpd
from scipy.stats import spearmanr
from scipy.cluster.hierarchy import linkage, fcluster
from scipy.spatial.distance import squareform
from sklearn.decomposition import PCA
from sklearn.model_selection import GroupKFold
from sklearn.metrics import f1_score
from lu_common import LU, LURAW, LUOUT, UTM, log
import lu_features as F
import importlib.util as iu

_s = iu.spec_from_file_location("eh", LU.parents[2] / "scripts/lu/07_eval_handlabels.py")
eh = iu.module_from_spec(_s); _s.loader.exec_module(eh)

OUT = LUOUT / "features"; OUT.mkdir(exist_ok=True)
CLASSES = [1, 2, 3, 4, 5]
CNAME = {1: "residential", 2: "non_res", 3: "water", 4: "forest", 5: "open"}
N_SUB = 120_000
PARAMS = dict(n_estimators=400, learning_rate=0.05, num_leaves=63, subsample=0.8, subsample_freq=1,
              colsample_bytree=0.6, class_weight="balanced", n_jobs=14, verbose=-1)


def family(c):
    if c in ("B2", "B3", "B4", "B5", "B8", "B11", "B12"):
        return "S2 bands"
    if c in ("ndvi", "ndbi", "mndwi", "bsi"):
        return "S2 indices (pixel)"
    if c.startswith(("ndvi_", "ndbi_", "mndwi_")):
        return "S2 indices (neighbourhood mean)"
    if c.startswith("b8_sd"):
        return "S2 texture"
    if c in ("ob_cov", "ob_h", "ob_hmax", "ob_cnt"):
        return "Buildings (pixel)"
    if c.startswith(("cov_", "cnt_", "bldg_area_", "bldg_h_", "hmax_", "h_sd")):
        return "Buildings (neighbourhood)"
    if c.startswith("viirs"):
        return "Night lights"
    if c.startswith("A") and c.endswith("_15"):
        return "AlphaEarth (150 m mean)"
    if c.startswith("A"):
        return "AlphaEarth (pixel)"
    return "other"


DESC = {
    "B2": "blue", "B3": "green", "B4": "red", "B5": "red-edge 1 (20 m)", "B8": "near-infrared",
    "B11": "short-wave IR 1 (20 m)", "B12": "short-wave IR 2 (20 m)",
    "ndvi": "(B8-B4)/(B8+B4) vegetation", "ndbi": "(B11-B8)/(B11+B8) built-up",
    "mndwi": "(B3-B11)/(B3+B11) water", "bsi": "((B11+B4)-(B8+B2))/((B11+B4)+(B8+B2)) bare soil",
    "ob_cov": "share of pixel covered by buildings", "ob_h": "mean building height (m)",
    "ob_hmax": "max building height (m)", "ob_cnt": "number of buildings in pixel",
    "viirs": "night-time light radiance",
    "cov": "mean building cover", "cnt": "buildings per window (x100)", "bldg_area": "mean building footprint (m2)",
    "bldg_h": "cover-weighted mean building height (m)", "hmax": "max building height in window",
    "h_sd": "std-dev of building height", "b8_sd": "std-dev of NIR (texture)",
}
WIN = {"7": "70 m", "15": "150 m", "31": "310 m", "61": "610 m"}


def catalogue(cols):
    rows = []
    for c in cols:
        base, _, w = c.rpartition("_") if c.rsplit("_", 1)[-1] in WIN else (c, "", "")
        if c.startswith("A") and c[1:3].isdigit():
            d = f"AlphaEarth embedding dimension {int(c[1:3])}" + (" averaged over 150 m" if c.endswith("_15") else "")
        elif base in ("hmax", "h_sd", "b8_sd"):
            d = DESC[base] + f" over {WIN[w]} window"
        else:
            d = DESC.get(base or c, "") + (f", mean over {WIN[w]} window" if w else "")
        rows.append({"feature": c, "family": family(c), "window": WIN.get(w, "pixel"), "description": d})
    return pd.DataFrame(rows)


def load():
    s = pd.read_parquet(LU / "samples.parquet")
    meta = {"label", "tile", "x", "y", "row", "col"} | {c for c in s if c.startswith("p_")}
    cols = [c for c in s.columns if c not in meta]
    tx = s.tile.str.extract(r"x(\d+)_y(\d+)").astype(int)
    s["block"] = (tx[0] // 12).astype(str) + "_" + (tx[1] // 12).astype(str)
    return s, cols


def shap_legend(s, cols):
    m, mcols = pickle.load(open(LU / "model_all_2023.pkl", "rb"))
    assert list(mcols) == cols
    sub = s.loc[s.groupby("label").sample(n=4000, random_state=0).index]
    X = sub[cols]
    contrib = m.booster_.predict(X, pred_contrib=True)          # (n, K*(F+1))
    K, Fn = len(CLASSES), len(cols)
    contrib = contrib.reshape(len(X), K, Fn + 1)[:, :, :Fn]
    rows = []
    for k, c in enumerate(CLASSES):
        sv = contrib[:, k, :]
        mabs = np.abs(sv).mean(0)
        # direction: rank correlation between feature value and its SHAP for this class
        dirn = [spearmanr(X.iloc[:, j], sv[:, j]).statistic if np.std(sv[:, j]) > 0 else 0 for j in range(Fn)]
        for j, f in enumerate(cols):
            rows.append({"feature": f, "class": CNAME[c], "mean_abs_shap": mabs[j], "direction": dirn[j]})
    sh = pd.DataFrame(rows)
    wide = sh.pivot(index="feature", columns="class", values="mean_abs_shap")[[CNAME[c] for c in CLASSES]]
    dirw = sh.pivot(index="feature", columns="class", values="direction")[[CNAME[c] for c in CLASSES]].add_prefix("dir_")
    wide["total"] = wide.sum(1)
    out = wide.join(dirw).sort_values("total", ascending=False)
    out.insert(0, "family", [family(f) for f in out.index])
    out.to_csv(OUT / "shap_by_class.csv")
    fam = out.groupby("family")[[CNAME[c] for c in CLASSES] + ["total"]].sum().sort_values("total", ascending=False)
    fam["n_features"] = out.groupby("family").size()
    fam.to_csv(OUT / "shap_family_by_class.csv")
    log("SHAP by family and class:\n" + fam.round(3).to_string())
    return out


def corr_clusters(s, cols, shap):
    sub = s.sample(20000, random_state=1)[cols]
    rho = spearmanr(sub).statistic
    rho = np.nan_to_num(rho)
    dist = 1 - np.abs(rho)
    np.fill_diagonal(dist, 0)
    Z = linkage(squareform(dist, checks=False), "average")
    cl = fcluster(Z, t=0.1, criterion="distance")           # |rho| >= ~0.9 inside a cluster
    df = pd.DataFrame({"feature": cols, "cluster": cl, "family": [family(c) for c in cols],
                       "shap_total": shap.loc[cols, "total"].values})
    df["keep"] = df.groupby("cluster").shap_total.transform("max") == df.shap_total
    df.sort_values(["cluster", "shap_total"], ascending=[True, False]).to_csv(OUT / "corr_clusters.csv", index=False)
    kept = df[df.keep].feature.tolist()
    log(f"correlation pruning: {len(cols)} -> {len(kept)} features "
        f"({df.cluster.nunique()} clusters at |rho|>=0.9)")
    return kept


class Pipe:
    """Feature-set definition applied inside a fold: column list and optional AlphaEarth PCA."""
    def __init__(self, cols, pca=None, topk=None):
        self.cols, self.pca, self.topk = cols, pca, topk

    def fit(self, X, y, full_cols):
        self.p = {}
        cols = list(self.cols)
        Xt = X[cols].copy()
        if self.pca:
            for grp, k in self.pca.items():
                g = [c for c in full_cols if family(c) == grp]
                self.p[grp] = PCA(k, random_state=0).fit(X[g])
            Xt = self._pca(X, Xt, full_cols)
        if self.topk:
            m = lgb.LGBMClassifier(**PARAMS).fit(Xt, y)
            imp = pd.Series(m.booster_.feature_importance("gain"), index=Xt.columns)
            self.sel = imp.sort_values(ascending=False).index[:self.topk].tolist()
            Xt = Xt[self.sel]
        self.m = lgb.LGBMClassifier(**PARAMS).fit(Xt, y)
        self.n_features = Xt.shape[1]
        return self

    def _pca(self, X, Xt, full_cols):
        for grp, p in self.p.items():
            g = [c for c in full_cols if family(c) == grp]
            z = p.transform(X[g])
            tag = "Ap" if grp == "AlphaEarth (pixel)" else "An"
            for i in range(z.shape[1]):
                Xt[f"{tag}_pc{i}"] = z[:, i]
        return Xt

    def transform(self, X, full_cols):
        Xt = X[list(self.cols)].copy()
        if self.pca:
            Xt = self._pca(X, Xt, full_cols)
        if self.topk:
            Xt = Xt[self.sel]
        return Xt

    def predict(self, X, full_cols):
        return self.m.predict(self.transform(X, full_cols))


def feature_sets(cols, pruned):
    fam = {c: family(c) for c in cols}
    no = lambda *fs: [c for c in cols if fam[c] not in fs]
    aef = ("AlphaEarth (pixel)", "AlphaEarth (150 m mean)")
    return {
        "ALL (181)": Pipe(cols),
        "- AlphaEarth 150 m mean": Pipe(no("AlphaEarth (150 m mean)")),
        "- all AlphaEarth": Pipe(no(*aef)),
        "- buildings (pixel+nbhd)": Pipe(no("Buildings (pixel)", "Buildings (neighbourhood)")),
        "- S2 neighbourhood + texture": Pipe(no("S2 indices (neighbourhood mean)", "S2 texture")),
        "- night lights": Pipe(no("Night lights")),
        "AlphaEarth -> PCA 16+8": Pipe(no(*aef), pca={"AlphaEarth (pixel)": 16, "AlphaEarth (150 m mean)": 8}),
        "correlation-pruned": Pipe(pruned),
        "top-60 by gain": Pipe(cols, topk=60),
        "top-30 by gain": Pipe(cols, topk=30),
        "top-15 by gain": Pipe(cols, topk=15),
        "pruned, AEF -> PCA 16+8": Pipe([c for c in pruned if fam[c] not in aef],
                                         pca={"AlphaEarth (pixel)": 16, "AlphaEarth (150 m mean)": 8}),
    }


def metrics(y, p):
    f1 = f1_score(y, p, labels=CLASSES, average=None, zero_division=0)
    return {"macro_f1": f1.mean(), **{f"f1_{CNAME[c]}": v for c, v in zip(CLASSES, f1)}}


def validation_features(cols):
    """Feature vectors at the hand-labelled pixel centres (computed with the same code as training)."""
    fp = LU / "validation_features.parquet"
    if fp.exists():
        return pd.read_parquet(fp)
    T = F.tiles()
    v = gpd.read_file(LU / "validation_points.gpkg", layer="validation_pixels").to_crs(UTM)
    key = pd.read_csv(LU / "validation_key.csv")
    v = v.merge(key[["pid", "stratum"]], on="pid")
    c = v.geometry.centroid
    v["tile"] = [f"x{int(a // 4000 * 4)}_y{int(b // 4000 * 4)}" for a, b in zip(c.x, c.y)]
    parts = []
    for k, g in v.groupby("tile"):
        if k not in T:
            continue
        minx, miny, maxx, maxy = T[k]
        names, arr = F.compute(k)
        r = ((maxy - c[g.index].y) // 10).astype(int).clip(0, 399).values
        cc = ((c[g.index].x - minx) // 10).astype(int).clip(0, 399).values
        d = pd.DataFrame(arr[:, r, cc].T, columns=names)
        d["pid"] = g.pid.values
        parts.append(d)
    X = pd.concat(parts, ignore_index=True).merge(
        v[["pid", "stratum", "true_class", "confidence", "is_road"]], on="pid")
    X.to_parquet(fp)
    return X


def main():
    t0 = time.time()
    s, cols = load()
    catalogue(cols).to_csv(OUT / "feature_catalogue.csv", index=False)
    shap = shap_legend(s, cols)
    pruned = corr_clusters(s, cols, shap)

    sub = s.groupby("label").sample(n=N_SUB // 5, random_state=2).reset_index(drop=True)
    y = sub.label.values
    folds = list(GroupKFold(n_splits=5).split(sub, y, sub.block))
    V = validation_features(cols)
    Vm = V[(V.confidence.fillna(3) <= 2) & V.true_class.notna()]
    W = pd.read_csv(LU / "validation_strata.csv", index_col=0)["weight"].to_dict()
    log(f"subsample {len(sub)} px, {sub.block.nunique()} blocks; {len(Vm)} hand-labelled px")

    cv_rows, hl_rows = [], []
    for name, pipe in feature_sets(cols, pruned).items():
        oof = np.zeros(len(sub), int); nf = []
        for tr, te in folds:
            p = Pipe(pipe.cols, pipe.pca, pipe.topk).fit(sub.iloc[tr], y[tr], cols)
            oof[te] = p.predict(sub.iloc[te], cols); nf.append(p.n_features)
        cv = {"feature_set": name, "n_features": int(np.median(nf)), **metrics(y, oof)}
        cv_rows.append(cv)
        full = Pipe(pipe.cols, pipe.pca, pipe.topk).fit(sub, y, cols)
        pred = full.predict(Vm, cols)
        r, _ = eh.weighted(Vm.true_class.astype(int).values, pred, Vm.stratum.values, W)
        lo, hi = eh.bootstrap(Vm.true_class.astype(int).values, pred, Vm.stratum.values, W, B=300)
        hl_rows.append({"feature_set": name, "n_features": full.n_features, "macro_F1": r["macro_F1"],
                        "lo": lo, "hi": hi, **{f"F1_{CNAME[c]}": r[f"F1_{c}"] for c in CLASSES},
                        "selected": ",".join(full.sel) if pipe.topk else ""})
        log(f"{name:28s} n={cv['n_features']:3d}  CV {cv['macro_f1']:.3f}  hand {r['macro_F1']:.3f}  "
            f"({(time.time() - t0) / 60:.0f} min)")
        pd.DataFrame(cv_rows).to_csv(OUT / "reduced_sets_cv.csv", index=False)
        pd.DataFrame(hl_rows).to_csv(OUT / "reduced_sets_handlabel.csv", index=False)


if __name__ == "__main__":
    main()
