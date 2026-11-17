"""
Pixel-level land-use TRANSITION dataset, 2017 -> 2023, for the choice models (22_choice_models.py).

Unit: a random sample of 10 m pixels across HMDA (PER_TILE per 4 km tile).

Start state (2017) and outcome (2023), defined so that the noisy hard-class change found in
13_change.py is avoided:
  - DEVELOPMENT is read from Open Buildings 2.5D Temporal building cover, which behaved
    consistently over time:
      undeveloped in 2017  : pixel cover < 5 % and 70 m-window cover < 10 %, not water
      developed by 2023    : pixel cover >= 20 % and 70 m-window cover >= 10 %
  - FUNCTION of newly developed pixels comes from the 53-feature physical LightGBM model
    (no AlphaEarth, so the same model is valid in both years) applied to 2023 inputs:
      share_nonres = P(non-res) / (P(res) + P(non-res));  non-residential if > 0.5.
    The continuous share is kept so models can use it with its uncertainty.
  - outcome: 0 stays undeveloped, 1 developed residential, 2 developed non-residential.

Explanatory variables: proximity as of 2017 (20_proximity.py) and 2017 context
(neighbourhood building cover at 150-610 m, NDVI, start-state class probabilities).

Panel version (2026-10-03): the SAME pixels are measured in 2017, 2020 and 2023, so periods
2017->2020, 2020->2023 and 2017->2023 can be compared on identical data. period(P, y0, y1)
turns the panel into one period's dataset with generic names (*_t0 = start year, *_t1 = end
year; road network and metro stations as they were at the start year).

Outputs: data/processed/lu/model_phys_2023.pkl (53-feature model, trained on all samples)
         data/processed/lu/transition_panel.parquet
"""
import json, pickle, sys
import numpy as np, pandas as pd, lightgbm as lgb
from lu_common import LU, LURAW, log
import lu_features as F
import importlib.util as iu

_s = iu.spec_from_file_location("px", LU.parents[2] / "scripts/lu/20_proximity.py")
px = iu.module_from_spec(_s); _s.loader.exec_module(px)

PER_TILE = 600
YEARS = {2017: "phys_2017", 2020: "phys_2020", 2023: "feat_2023"}
KEEP = ["ob_cov", "ob_h", "ob_cnt", "cov_7", "cov_15", "cov_31", "cov_61", "cnt_61", "bldg_h_61",
        "ndvi", "ndvi_15", "mndwi", "viirs", "viirs_61"]
PARAMS = dict(n_estimators=400, learning_rate=0.05, num_leaves=63, subsample=0.8, subsample_freq=1,
              colsample_bytree=0.6, class_weight="balanced", n_jobs=14, verbose=-1)
METRO_BY = {2017: "metro_2017", 2020: "metro_2020", 2023: "metro_2020"}


def phys_model():
    fp = LU / "model_phys_2023.pkl"
    if fp.exists():
        return pickle.load(open(fp, "rb"))
    s = pd.read_parquet(LU / "samples.parquet")
    names, _ = F.compute("x228_y1920", aef=False)
    m = lgb.LGBMClassifier(**PARAMS).fit(s[names], s.label.values)
    pickle.dump((m, names), open(fp, "wb"))
    log(f"trained 53-feature physical model on {len(s)} pixels")
    return m, names


def period(P, y0, y1):
    """One period's transition dataset from the panel, with generic column names."""
    d = P[["tile", "x", "y", "block12", "sisdp_code", "sisdp_class",
           "d_employment", "d_cbd_abids", "d_charminar", "d_secunderabad", "d_hitec_cyber_towers",
           "d_financial_district", "d_airport_rgia", "d_orr_access"]].copy()
    for f in KEEP + [f"p{c}" for c in (1, 2, 3, 4, 5)]:
        d[f"{f}_t0"], d[f"{f}_t1"] = P[f"{f}_{y0}"].values, P[f"{f}_{y1}"].values
    d["d_major_road_t0"] = P[f"d_major_road_{y0}"].values             # network as at the start year
    d["d_major_road_t1"] = P[f"d_major_road_{y1}"].values             # end-year network (endogenous)
    d["d_metro_t0"] = P[f"d_{METRO_BY[y0]}"].values                   # stations open by the start year
    d["d_metro_2020"] = P["d_metro_2020"].values
    d["undeveloped_t0"] = (d.ob_cov_t0 < 0.05) & (d.cov_7_t0 < 0.10) & (d.p3_t0 < 0.5)
    d["developed_t1"] = (d.ob_cov_t1 >= 0.20) & (d.cov_7_t1 >= 0.10)
    d["share_nonres_t1"] = d.p2_t1 / (d.p1_t1 + d.p2_t1 + 1e-9)
    d["outcome"] = np.where(~d.developed_t1, 0, np.where(d.share_nonres_t1 > 0.5, 2, 1))
    d["start_class_t0"] = d[[f"p{c}_t0" for c in (1, 2, 3, 4, 5)]].values.argmax(1) + 1
    d.attrs.update(y0=y0, y1=y1)
    return d


def main():
    import os
    m, names = phys_model()
    T = F.tiles()
    have = lambda d, k: (LURAW / d / f"{k}.tif").exists()
    # neighbours must exist too (else neighbourhood features are zero-padded at the edge)
    nb_ok = lambda d, k: all(have(d, n) or n not in T for n in
                             (F.neighbour_key(k, dx, dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1)))
    keys = [k for k in T if all(have(f, k) and nb_ok(f, k) for f in YEARS.values())]
    log(f"{len(keys)} of {len(T)} tiles have all of {list(YEARS)} with complete neighbours")
    DRY = bool(os.environ.get("DRY"))
    if DRY:
        keys = keys[:15]
    rng = np.random.default_rng(11)
    parts = []
    for i, k in enumerate(keys, 1):
        r = rng.integers(0, F.TS, PER_TILE); c = rng.integers(0, F.TS, PER_TILE)
        minx, miny, maxx, maxy = T[k]
        d = pd.DataFrame({"tile": k, "x": minx + (c + 0.5) * 10, "y": maxy - (r + 0.5) * 10})
        for yr, folder in YEARS.items():
            n_, a = F.compute(k, folder=folder, aef=False)
            assert n_ == names
            X = pd.DataFrame(a[:, r, c].T, columns=names)
            p = m.predict_proba(X)
            for j, cl in enumerate(m.classes_):
                d[f"p{cl}_{yr}"] = p[:, j]
            for f in KEEP:
                d[f"{f}_{yr}"] = X[f].values
        sp = LURAW / "sisdp" / f"{k}.tif"                      # 23_sisdp_raster.py (NRSC 2016-19)
        if sp.exists():
            import rasterio
            with rasterio.open(sp) as s:
                a = s.read()
            d["sisdp_code"], d["sisdp_class"] = a[0, r, c], a[1, r, c]
        else:
            d["sisdp_code"], d["sisdp_class"] = 0, 0
        parts.append(d)
        if i % 50 == 0:
            log(f"  {i}/{len(keys)} tiles")
    P = pd.concat(parts, ignore_index=True)
    P = pd.concat([P, px.Prox().at(P.x.values, P.y.values)], axis=1)
    tx = P.tile.str.extract(r"x(\d+)_y(\d+)").astype(int)
    P["block12"] = (tx[0] // 12).astype(str) + "_" + (tx[1] // 12).astype(str)
    P.to_parquet(LU / ("transition_panel_dryrun.parquet" if DRY else "transition_panel.parquet"))
    for y0, y1 in ((2017, 2020), (2020, 2023), (2017, 2023)):
        e = period(P, y0, y1); e = e[e.undeveloped_t0]
        log(f"{y0}->{y1}: {len(e):,} undeveloped at start; outcome {e.outcome.value_counts().sort_index().to_dict()} "
            f"(developed {e.developed_t1.mean():.2%})")


if __name__ == "__main__":
    main()
