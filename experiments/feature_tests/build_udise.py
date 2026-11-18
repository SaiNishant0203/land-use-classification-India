"""
School factors from UDISE+ (India Data Portal, retrieved 2022; data/raw/udise/telangana_schools.csv), dated by
year_of_establishment so only schools that existed before the period count (est. < t0).

  ln_sch_2km        ln(1 + schools within 2 km, est. before t0)
  ln_priv_2km       ln(1 + private unaided schools within 2 km, est. before t0): private schools follow paying
                    middle-class demand, a pre-period signal of where households are moving
  ln_newpriv_3km    ln(1 + private unaided schools within 3 km established in the 3 years before t0
                    (t0-3 .. t0-1)): growth momentum of demand, lagged
  ln_d_govsch       ln(km + 0.1) to the nearest government / local-body school est. before t0 (village core proxy)

Caveat: the register lists schools operating around 2019-22, so schools that closed earlier are missing
(survivor bias); coordinates are self-reported and some are wrong (points outside Telangana are dropped).
Output: experiments/feature_tests/feat_udise.parquet
"""
from pathlib import Path
import numpy as np, pandas as pd
from pyproj import Transformer
from scipy.spatial import cKDTree

ROOT = Path(__file__).resolve().parents[2]
s = pd.read_csv(ROOT / "data/raw/udise/telangana_schools.csv")
s = s[s.latitude.between(15.8, 19.95) & s.longitude.between(77.2, 81.4)].copy()
s["yr"] = pd.to_numeric(s.year_of_establishment, errors="coerce")
s["x"], s["y"] = Transformer.from_crs(4326, 32644, always_xy=True).transform(s.longitude.values, s.latitude.values)
s["priv"] = s.management.str.contains("Private Unaided", na=False)
s["gov"] = s.management.isin(["Local body", "Department of Education"])

cells = pd.concat([pd.read_parquet(ROOT / "data/processed/change" / f, columns=["period", "t0", "x", "y"])
                   for f in ("hmda_cells_census.parquet", "hmda_persist_cells_census.parquet")]).drop_duplicates(["period", "x", "y"])
out = []
for t0 in (2017, 2020):
    c = cells[cells.t0 == t0].copy(); P = c[["x", "y"]].to_numpy()
    pre = s[s.yr < t0]
    cnt = lambda df, r: np.array([len(i) for i in cKDTree(df[["x", "y"]].to_numpy()).query_ball_point(P, r)])
    c["ln_sch_2km"] = np.log1p(cnt(pre, 2000))
    c["ln_priv_2km"] = np.log1p(cnt(pre[pre.priv], 2000))
    c["ln_newpriv_3km"] = np.log1p(cnt(pre[pre.priv & (pre.yr >= t0 - 3)], 3000))
    c["ln_d_govsch"] = np.log(cKDTree(pre.loc[pre.gov, ["x", "y"]].to_numpy()).query(P)[0] / 1000 + 0.1)
    print(t0, "schools before t0:", len(pre), "private:", int(pre.priv.sum()), "new private (3 yrs):",
          int((pre.priv & (pre.yr >= t0 - 3)).sum()))
    out.append(c.drop(columns="t0"))
o = pd.concat(out); o.to_parquet(ROOT / "experiments/feature_tests/feat_udise.parquet", index=False)
print(o.describe().T[["mean", "min", "max"]])
