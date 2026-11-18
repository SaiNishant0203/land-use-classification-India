"""
Satellite factors from Google Earth Engine at the sampled cells, all from the year before the period
(t0 - 1 = 2016 for 2017-20, 2019 for 2020-23) or fixed geography, so none overlaps the outcome period.

  dw_crops, dw_bare, dw_shrub, dw_grass   Dynamic World V1 mean class probability over year t0-1 (10 m, at the
                                          cell centre): what kind of "open" land the cell is (farmland, barren,
                                          scrub, grass). Our map has one "other open" class.
  ln_hand                                 ln(1 + height above nearest drainage, m), MERIT Hydro (90 m), fixed:
                                          low-lying, flood-prone land (Florida's "% flood zone A" analogue)
  wet_yrs_250m                            share of years 2000..t0-1 with seasonal or permanent water within
                                          250 m (JRC Global Surface Water YearlyHistory): lake beds, flood plains
  ndvi_dry                                median Sentinel-2 NDVI in the dry season (Mar-May) of t0-1: irrigated
                                          / perennial green vs rain-fed fallow
  ndvi_amp                                90th - 10th percentile NDVI over t0-1: cropping intensity

EE project: set the EE_PROJECT env var to your own Earth Engine project (required). Batches are cached in
experiments/feature_tests/ee_cache/ so a rerun resumes.
Runs on a random subsample of N_SUB cells per period (default 25,000), see below.
Output: experiments/feature_tests/feat_ee.parquet
"""
import os, time
from pathlib import Path
import numpy as np, pandas as pd, ee
from pyproj import Transformer

ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / "experiments/feature_tests/ee_cache"; CACHE.mkdir(exist_ok=True)
ee.Initialize(project=os.environ["EE_PROJECT"])
BATCH = 2500


def image(t0):
    y = t0 - 1; a, b = f"{y}-01-01", f"{y + 1}-01-01"
    dw = (ee.ImageCollection("GOOGLE/DYNAMICWORLD/V1").filterDate(a, b)
          .filterBounds(ee.Geometry.Rectangle([77.9, 16.9, 79.1, 18.0]))
          .select(["crops", "bare", "shrub_and_scrub", "grass"]).mean()
          .rename(["dw_crops", "dw_bare", "dw_shrub", "dw_grass"]))
    hand = ee.Image("MERIT/Hydro/v1_0_1").select("hnd").add(1).log().rename("ln_hand")
    yh = ee.ImageCollection("JRC/GSW1_4/YearlyHistory").filter(ee.Filter.rangeContains("year", 2000, y))
    wet = (yh.map(lambda im: im.gte(2).unmask(0).focalMax(250, "circle", "meters")).mean().rename("wet_yrs_250m"))

    def ndvi(im):
        scl = im.select("SCL"); ok = scl.neq(3).And(scl.neq(8)).And(scl.neq(9)).And(scl.neq(10)).And(scl.neq(11))
        return im.normalizedDifference(["B8", "B4"]).rename("ndvi").updateMask(ok)
    s2 = (ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED" if y >= 2019 else "COPERNICUS/S2_HARMONIZED")
          .filterBounds(ee.Geometry.Rectangle([77.9, 16.9, 79.1, 18.0])).filterDate(a, b)
          .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 40)))
    if y < 2019:   # L1C has no SCL; use QA60 cloud bits
        s2 = s2.map(lambda im: im.updateMask(im.select("QA60").eq(0)).normalizedDifference(["B8", "B4"]).rename("ndvi").copyProperties(im, ["system:time_start"]))
    else:
        s2 = s2.map(lambda im: ndvi(im).copyProperties(im, ["system:time_start"]))
    dry = s2.filterDate(f"{y}-03-01", f"{y}-06-01").median().rename("ndvi_dry")
    pct = s2.reduce(ee.Reducer.percentile([10, 90]))
    amp = pct.select("ndvi_p90").subtract(pct.select("ndvi_p10")).rename("ndvi_amp")
    return dw.addBands([hand, wet, dry, amp])


cells = pd.concat([pd.read_parquet(ROOT / "data/processed/change" / f, columns=["period", "t0", "x", "y"])
                   for f in ("hmda_cells_census.parquet", "hmda_persist_cells_census.parquet")]).drop_duplicates(["period", "x", "y"])
cells["lon"], cells["lat"] = Transformer.from_crs(32644, 4326, always_xy=True).transform(cells.x.values, cells.y.values)
# Random subsample: N_SUB cells per period, drawn uniformly over the union of both samples (seed 0). A uniform
# subsample of a choice-based sample keeps its design, so the tests stay valid with wider intervals.
# Cells already extracted by an earlier full run (cache files <t0>_<i>.parquet) are reused.
N_SUB = int(os.environ.get("N_SUB", 25000))
parts = []
for t0 in (2017, 2020):
    img = image(t0); c = cells[cells.t0 == t0].reset_index(drop=True)
    sub = c.sample(n=min(N_SUB, len(c)), random_state=0)
    old = [pd.read_parquet(f) for f in sorted(CACHE.glob(f"{t0}_*.parquet"))]
    old = pd.concat(old) if old else pd.DataFrame(columns=["period", "x", "y"])
    have = sub.merge(old, on=["period", "x", "y"], how="inner")
    todo = sub.merge(old[["period", "x", "y"]], on=["period", "x", "y"], how="left", indicator=True)
    todo = todo[todo._merge == "left_only"].drop(columns="_merge").reset_index(drop=True)
    print(t0, "subsample", len(sub), "cached", len(have), "to fetch", len(todo), flush=True)
    parts.append(have[["period", "x", "y"] + [k for k in have.columns if k not in ("period", "x", "y", "t0", "lon", "lat")]])
    for i in range(0, len(todo), BATCH):
        f = CACHE / f"sub_{t0}_{i:06d}.parquet"
        if not f.exists():
            chunk = todo.iloc[i:i + BATCH]
            fc = ee.FeatureCollection([ee.Feature(ee.Geometry.Point([lo, la]), {"k": int(k)})
                                       for k, lo, la in zip(chunk.index, chunk.lon, chunk.lat)])
            for attempt in range(4):
                try:
                    r = img.reduceRegions(fc, ee.Reducer.first(), scale=10, tileScale=4).getInfo()
                    break
                except Exception as e:
                    print("retry", t0, i, str(e)[:120], flush=True); time.sleep(20 * (attempt + 1))
            else:
                raise RuntimeError(f"batch {t0} {i} failed")
            rows = pd.DataFrame([ft["properties"] for ft in r["features"]]).set_index("k")
            chunk[["period", "x", "y"]].join(rows).to_parquet(f)
        parts.append(pd.read_parquet(f))
        print(t0, min(i + BATCH, len(todo)), "/", len(todo), flush=True)
o = pd.concat(parts); o.to_parquet(ROOT / "experiments/feature_tests/feat_ee.parquet", index=False)
print(o.describe().T[["count", "mean", "min", "max"]])
