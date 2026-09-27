# Pixel-wise land use for HMDA (scripts/lu)

**Aims:**
1. Test how well existing land-use models and products perform on Hyderabad at the urban scale.
2. Build an imagery → land-use model that works there.

Classes (fixed, transport-oriented):

| code | class | notes |
|---|---|---|
| 1 | residential | |
| 2 | non-residential built | |
| 3 | water | |
| 4 | forest / trees | |
| 5 | other open | farmland, barren, vacant |

## Pipeline

| step | script | env | output |
|---|---|---|---|
| OSM label sources | `01_osm_label_sources.py` | main | `data/processed/lu/osm_extra_tiles/` |
| hand-label test sample (325 px) | `02_validation_sample.py` | main | `validation_points.gpkg` + `LABELLING_GUIDE.md` |
| 10 m feature tiles (76 bands) | `03_download_features.py` | main | `data/raw/lu/feat_2023/` |
| existing products on same grid | `03b_download_products.py` | main | `data/raw/lu/prod/` |
| S2 B6/B7/B8A (BigEarthNet only) | `03c_download_s2extra.py` | main | `data/raw/lu/s2x_2023/` |
| training labels (OSM + agreement) | `04_labels.py` | main | `data/raw/lu/lab/` |
| labelled pixel samples + product values | `05_sample_pixels.py` | main | `data/processed/lu/samples.parquet` |
| LightGBM ablation + product audit | `06_train_eval.py` | main | `outputs/lu/cv_ablation.csv`, `audit_products.csv` |
| score everything on hand labels | `07_eval_handlabels.py` | main | `outputs/lu/handlabel_eval.csv` |
| BigEarthNet v2 zero-shot | `08_bigearthnet.py` | .venv-xpu | `data/raw/lu/ben/` |
| full HMDA map | `09_predict_map.py` | main | `outputs/lu/landuse_hmda_2023_10m.tif`, `.png` |
| U-Net (our model v2) | `10_unet.py [epochs]` | .venv-xpu | `outputs/lu/unet_vs_lgbm.csv` |
| SenCLIP zero-shot | `11_senclip.py` | .venv-xpu | `data/raw/lu/senclip/` |
| EULUC-Globe 2024 parcels | `12_euluc.py` | main | `data/raw/lu/euluc/` |

Chains: `run_overnight.sh` runs downloads → labels → samples → BEN → 06 → 09 → 07, and
`final_rerun.sh` runs EULUC and then re-runs 06 and 07 once everything exists. Logs are in
`outputs/lu/logs/`, with a timeline in `overnight.log`.

## Rules that keep the comparison honest

- **The hand-labelled pixels are test only.** Training pixels within 300 m of them are removed (`04_labels.py`).
- **Every model and product is scored on the same pixels.** Our model is also scored on exactly the pixels each product covers (`ours_same_px_*` columns).
- **OSM-based scores are not the headline.**
  - The OSM class mix is not natural prevalence.
  - GULU was trained on OSM labels, so an OSM test flatters it.
  - DW, WorldCover and JRC helped make the water/forest/open labels, so they are advantaged on classes 3–5.
  - Headline numbers come from `07_eval_handlabels.py` (stratum-weighted, Olofsson et al. 2014).
- **Spatial CV:** GroupKFold over 12 km blocks. The U-Net uses fold 0 of the same split.

## Gotchas

- **Open Buildings Temporal:** filter the collection to Hyderabad before `first().projection()`. Unfiltered, it picks a tile from another UTM zone and `reduceResolution` fails.
- **`ob_cnt` is stored ×1e4:** a 10 m pixel holds only ~0.01 buildings.
- **GULU `IND.tif`:** the CRS tag is broken; the data is EPSG:3857.
- **`getDownloadURL`:**
  - The cap is 50 MB, hence 4 km tiles.
  - Restricted mode allows only ~5 concurrent requests, so HTTP 429s are normal.
  - The GeoTIFF drops band names; the band order is `lu_common.BANDS`.
- **Tile keys are `x{minx km}_y{miny km}`** in EPSG:32644. Charminar is about (231000, 1921000).
