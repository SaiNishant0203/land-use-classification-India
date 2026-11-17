"""
Census factors for the change model, all measured before the first period (2017):
  jobs           6th Economic Census 2013-14 microdata (Telangana file exported from the MoSPI DVD with
                 Nesstar, data/raw/ec6/ec6_telangana.parquet), aggregated to SHRUG villages / towns with
                 the SHRUG ec13 keys
  people         Population Census 2011 Primary Census Abstract (SHRUG, by shrid)
  households     SECC 2011-12 rural + urban (SHRUG, by shrid): vehicle ownership, the analogue of
                 Table 18's zero-vehicle households
  boundaries     SHRUG open shrid polygons (Census 2011 villages and towns), data/raw/shrug/shrid_hmda.gpkg

Variables per 20 m trial cell
  own village / town (shrid that contains the cell):
    jobdens_vill   workers per km2 (2013)
    popdens_vill   people per km2 (2011)
    scst_share     share of people SC or ST (2011)
    lit_rate       literacy rate of people aged 7+ (2011)
    agri_share     share of workers who are cultivators or agricultural labourers (2011)
    veh23_share    share of households with a two- or three-wheeler (SECC)
    veh4_share     share of households with a four-wheeler (SECC)
    in_ghmc        cell is in one of the two GHMC parts (one big polygon each, so village values are
                   city-wide averages there)
  within about 5 km (each village's totals spread evenly over its area on a 100 m grid, then a
  Gaussian kernel with sigma 2.5 km):
    jobs_5km, pop_5km     workers and people (kernel-weighted)
    it_share_5km          share of those jobs in software / IT services (NIC 582, 620, 631, 639)
    manuf_share_5km       share in manufacturing
    large_share_5km       share in establishments with 100 or more workers

Usage: python 07_census_factors.py        (REGION=hmda: hmda_cells_full -> hmda_cells_census)
Output: data/processed/change/trial_cells_census.parquet, data/processed/change/shrid_hmda_census.gpkg
"""
import os
from pathlib import Path
import numpy as np, pandas as pd, geopandas as gpd
from rasterio.features import rasterize
from rasterio.transform import from_origin
from scipy.ndimage import gaussian_filter

ROOT = Path(__file__).resolve().parents[2]
CH = ROOT / "data" / "processed" / "change"
U = ROOT / "data" / "raw" / "shrug" / "unz"
IT = ["582", "620", "631", "639"]
RES, SIGMA_KM, PAD = 100, 2.5, 15000
REGION = os.environ.get("REGION", "trial")     # trial: ACs 50-52 with booth votes; hmda: all of HMDA, no votes
HMDA = REGION == "hmda"
OUTCOME = os.environ.get("OUTCOME", "both")   # both: map + Open Buildings agree (#45); persist: map built in t1-1 and t1 (#53)
PERSIST = OUTCOME == "persist"
TAG = ("hmda" if HMDA else "trial") + ("_persist" if PERSIST else "")
PFX = TAG


def ec13_by_shrid():
    d = pd.read_parquet(ROOT / "data/raw/ec6/ec6_telangana.parquet",
                        columns=["DT", "TEH", "T_V", "SECTOR", "BACT", "NIC3", "TOTAL_WORKER"])
    for c in ["DT", "TEH", "T_V"]:
        d[c] = d[c].astype(int)
    keys = []
    for f, idc, sec in (("ec13r_shrid_key.csv", "ec13_village_id", "1"), ("ec13u_shrid_key.csv", "ec13_town_id", "2")):
        k = pd.read_csv(U / "shrug-ec-keys-csv" / f)
        k = k[k.ec13_state_id == 36].rename(columns={"ec13_district_id": "DT", "ec13_subdistrict_id": "TEH", idc: "T_V"})
        k[["DT", "TEH", "T_V"]] = k[["DT", "TEH", "T_V"]].astype(int); k["SECTOR"] = sec
        keys.append(k[["DT", "TEH", "T_V", "SECTOR", "shrid2"]])
    d = d.merge(pd.concat(keys).drop_duplicates(["DT", "TEH", "T_V", "SECTOR"]), on=["DT", "TEH", "T_V", "SECTOR"], how="left")
    print(f"EC 2013: {d.TOTAL_WORKER.sum():,} workers in Telangana, {d.loc[d.shrid2.notna(), 'TOTAL_WORKER'].sum() / d.TOTAL_WORKER.sum():.1%} linked to a shrid")
    w = d.TOTAL_WORKER.astype(float)
    d = d.assign(emp=w, emp_it=w * d.NIC3.isin(IT), emp_manuf=w * (d.BACT == "06"), emp_large=w * (d.TOTAL_WORKER >= 100), est=1)
    return d.groupby("shrid2")[["emp", "emp_it", "emp_manuf", "emp_large", "est"]].sum()


def pca_by_shrid(ids):
    p = pd.read_csv(U / "shrug-pca11-csv/pc11_pca_clean_shrid.csv",
                    usecols=["shrid2", "pc11_pca_tot_p", "pc11_pca_no_hh", "pc11_pca_p_06", "pc11_pca_p_sc", "pc11_pca_p_st",
                             "pc11_pca_p_lit", "pc11_pca_tot_work_p", "pc11_pca_main_cl_p", "pc11_pca_main_al_p",
                             "pc11_pca_marg_cl_p", "pc11_pca_marg_al_p"])
    p = p[p.shrid2.isin(ids)].set_index("shrid2")
    out = pd.DataFrame(index=p.index)
    out["pop11"] = p.pc11_pca_tot_p
    out["scst_share"] = (p.pc11_pca_p_sc + p.pc11_pca_p_st) / p.pc11_pca_tot_p
    out["lit_rate"] = p.pc11_pca_p_lit / (p.pc11_pca_tot_p - p.pc11_pca_p_06)
    out["agri_share"] = (p.pc11_pca_main_cl_p + p.pc11_pca_main_al_p + p.pc11_pca_marg_cl_p + p.pc11_pca_marg_al_p) / p.pc11_pca_tot_work_p
    return out


def secc_by_shrid(ids):
    parts = []
    for f in ("shrug-secc-mord-rural-csv/secc_rural_shrid.csv", "shrug-secc-parsed-urban-csv/secc_urban_shrid.csv"):
        s = pd.read_csv(U / f, usecols=["shrid2", "secc_hh", "veh_two_three_share", "veh_four_share"])
        parts.append(s[s.shrid2.isin(ids)])
    s = pd.concat(parts).dropna(subset=["secc_hh"])
    s["v23"] = s.veh_two_three_share * s.secc_hh; s["v4"] = s.veh_four_share * s.secc_hh
    g = s.groupby("shrid2")[["secc_hh", "v23", "v4"]].sum()
    return pd.DataFrame({"veh23_share": g.v23 / g.secc_hh, "veh4_share": g.v4 / g.secc_hh})


def main():
    poly = gpd.read_file(ROOT / "data/raw/shrug/shrid_hmda.gpkg").to_crs(32644)
    names = pd.read_csv(U / "shrug-shrid-keys-csv/shrid_loc_names.csv").set_index("shrid2")
    poly = poly.join(names[["district_name", "subdistrict_name", "town_name", "village_name"]], on="shrid2")
    poly["area_km2"] = poly.area / 1e6
    ids = set(poly.shrid2)
    poly = poly.join(ec13_by_shrid(), on="shrid2").join(pca_by_shrid(ids), on="shrid2").join(secc_by_shrid(ids), on="shrid2")
    for c in ["emp", "emp_it", "emp_manuf", "emp_large", "est"]:
        poly[c] = poly[c].fillna(0)
    poly["jobdens_vill"] = poly.emp / poly.area_km2; poly["popdens_vill"] = poly.pop11 / poly.area_km2
    poly["in_ghmc"] = poly.town_name.fillna("").str.contains("greater hyderabad").astype(int)
    print(f"{len(poly)} shrids in HMDA: {poly.emp.sum():,.0f} workers (2013), {poly.pop11.sum():,.0f} people (2011); "
          f"missing PCA {poly.pop11.isna().sum()}, missing SECC {poly.veh4_share.isna().sum()}")
    poly.to_file(CH / "shrid_hmda_census.gpkg")

    d = pd.read_parquet(CH / f"{PFX}_cells_full.parquet")
    pts = gpd.GeoDataFrame(d, geometry=gpd.points_from_xy(d.x, d.y), crs=32644)
    cols = ["jobdens_vill", "popdens_vill", "scst_share", "lit_rate", "agri_share", "veh23_share", "veh4_share", "in_ghmc", "shrid2"]
    j = gpd.sjoin(pts, poly[cols + ["geometry"]], how="left", predicate="within").drop(columns=["index_right", "geometry"])
    j = j[~j.index.duplicated()]
    # the open polygons leave slivers between villages (median 0.4 km wide here): nearest village within 3 km
    miss = j.shrid2.isna(); j["shrid_nearest"] = miss.astype(int)
    nn = gpd.sjoin_nearest(pts[miss], poly[cols + ["geometry"]], how="left", max_distance=3000).drop(columns=["index_right", "geometry"])
    nn = nn[~nn.index.duplicated()]
    j.loc[miss, cols] = nn[cols].values
    print(f"cells inside a shrid: {(~miss).mean():.1%}; + nearest within 3 km: {j.shrid2.notna().mean():.1%}; in GHMC parts: {j.in_ghmc.mean():.1%}")

    # kernel-weighted totals within ~5 km: spread each shrid's totals evenly over its area
    x0, x1 = d.x.min() - PAD, d.x.max() + PAD; y0, y1 = d.y.min() - PAD, d.y.max() + PAD
    nx, ny = int((x1 - x0) // RES), int((y1 - y0) // RES); tr = from_origin(x0, y1, RES, RES)
    lab = rasterize(((g, i + 1) for i, g in enumerate(poly.geometry)), (ny, nx), transform=tr, dtype="int32")
    ncell = np.bincount(lab.ravel(), minlength=len(poly) + 1)
    r = ((y1 - d.y.values) // RES).astype(int); c = ((d.x.values - x0) // RES).astype(int)
    sm = {}
    for v in ["emp", "emp_it", "emp_manuf", "emp_large", "pop11"]:
        per = np.r_[0, poly[v].fillna(0).values] / np.maximum(ncell, 1)
        sm[v] = gaussian_filter(per[lab], SIGMA_KM * 1000 / RES, mode="constant") * 2 * np.pi * (SIGMA_KM * 1000 / RES) ** 2
    j["jobs_5km"] = sm["emp"][r, c]; j["pop_5km"] = sm["pop11"][r, c]
    for v, k in (("emp_it", "it_share_5km"), ("emp_manuf", "manuf_share_5km"), ("emp_large", "large_share_5km")):
        j[k] = sm[v][r, c] / np.maximum(sm["emp"][r, c], 1)
    j.to_parquet(CH / f"{PFX}_cells_census.parquet")
    print(j[["jobdens_vill", "popdens_vill", "jobs_5km", "pop_5km", "it_share_5km", "manuf_share_5km", "large_share_5km",
             "scst_share", "lit_rate", "agri_share", "veh23_share", "veh4_share", "in_ghmc"]].describe().T.round(3).to_string())
    print(j[["change", "jobs_5km", "jobdens_vill", "pop_5km", "veh4_share", "agri_share", "built_1km", "d_jobs"]]
          .assign(l_jobs=lambda t: np.log1p(t.jobs_5km), l_jd=lambda t: np.log1p(t.jobdens_vill), l_pop=lambda t: np.log1p(t.pop_5km),
                  l_dj=lambda t: np.log(t.d_jobs + 0.1))[["l_jobs", "l_jd", "l_pop", "veh4_share", "agri_share", "built_1km", "l_dj"]]
          .corr().round(2).to_string())


if __name__ == "__main__":
    main()
