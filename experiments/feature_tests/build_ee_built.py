"""Dynamic World 'built' and 'trees' mean probability in t0-1 at the cells of feat_ee.parquet: a control for
cells our map calls open that Dynamic World already sees as partly built (map error, not a driver).
Light image (Dynamic World only), batches of 5,000. Output: experiments/feature_tests/feat_ee_built.parquet"""
import os, time
from pathlib import Path
import pandas as pd, ee
from pyproj import Transformer
ROOT = Path(__file__).resolve().parents[2]; C = ROOT / "experiments/feature_tests/ee_cache"
ee.Initialize(project=os.environ["EE_PROJECT"])
f = pd.read_parquet(ROOT / "experiments/feature_tests/feat_ee.parquet")[["period", "x", "y"]].reset_index(drop=True)
f["lon"], f["lat"] = Transformer.from_crs(32644, 4326, always_xy=True).transform(f.x.values, f.y.values)
out = []
for per, y in (("2017-2020", 2016), ("2020-2023", 2019)):
    img = (ee.ImageCollection("GOOGLE/DYNAMICWORLD/V1").filterDate(f"{y}-01-01", f"{y+1}-01-01")
           .filterBounds(ee.Geometry.Rectangle([77.9, 16.9, 79.1, 18.0])).select(["built", "trees"]).mean()
           .rename(["dw_built", "dw_trees"]))
    c = f[f.period == per]
    for i in range(0, len(c), 5000):
        fn = C / f"built_{y}_{i:06d}.parquet"
        if not fn.exists():
            ch = c.iloc[i:i + 5000]
            fc = ee.FeatureCollection([ee.Feature(ee.Geometry.Point([lo, la]), {"k": int(k)}) for k, lo, la in zip(ch.index, ch.lon, ch.lat)])
            for a in range(3):
                try:
                    r = img.reduceRegions(fc, ee.Reducer.first(), scale=10, tileScale=4).getInfo(); break
                except Exception as e:
                    print("retry", y, i, str(e)[:100], flush=True); time.sleep(15)
            else:
                raise RuntimeError("failed")
            ch[["period", "x", "y"]].join(pd.DataFrame([q["properties"] for q in r["features"]]).set_index("k")).to_parquet(fn)
        out.append(pd.read_parquet(fn)); print(per, min(i + 5000, len(c)), "/", len(c), flush=True)
pd.concat(out).to_parquet(ROOT / "experiments/feature_tests/feat_ee_built.parquet", index=False)
