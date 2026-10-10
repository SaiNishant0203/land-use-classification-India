# Data guide: land-use classification for Hyderabad (HMDA)

This file explains every data file in the project: where it comes from, what was done to it,
what each band and column means, and how to use it. It covers:

1. the **data in this repository** (enough to train and test the model), and
2. the **raster zip shared separately** (needed for maps, new features and the product audit).

For the method and results, read `README.md`. For the scripts, read `scripts/lu/README.md`.

**Contents**

1. Quick start
2. Conventions used everywhere
3. How the data was made, step by step
4. Files in this repository
5. Files in the raster zip
6. How to use the data
7. What you can run with what you have
8. Things to watch out for
9. Sources and licences

---

## 1. Quick start

```bash
pip install numpy pandas pyarrow geopandas rasterio scipy scikit-learn lightgbm matplotlib pyproj shapely requests
python scripts/lu/00_join_samples.py     # joins the two sample parts into samples.parquet (once)
python scripts/lu/06_train_eval.py       # spatial cross-validation + audit of existing products
```

That is all you need to retrain and cross-validate. Nothing above needs the raster zip or an
Earth Engine account.

To use the raster zip, unzip it **into the repository root** so the `data/raw/lu/...` paths
line up with section 5.

---

## 2. Conventions used everywhere

| item | value |
|---|---|
| Area | Hyderabad Metropolitan Development Authority (HMDA), about 7,650 km² |
| Year | 2023, unless a folder name says otherwise |
| Coordinate system | **EPSG:32644** (UTM zone 44N, metres) |
| Pixel | 10 m × 10 m |
| Tile | 4 km × 4 km = 400 × 400 pixels. 556 tiles cover HMDA |
| Tile name | `x{minx in km}_y{miny in km}.tif`. `x228_y1920` has its lower-left corner at (228000, 1920000). Charminar is at about (231000, 1921000) |
| Row / column | row 0 is the **north** edge, column 0 the west edge |

**The five land-use classes** (the same codes in every file):

| code | class | includes |
|---|---|---|
| 1 | residential | houses, apartments, gated communities, informal housing, villages |
| 2 | non-residential built | shops, offices, IT parks, factories, warehouses, schools, hospitals, government, religious |
| 3 | water | lakes, tanks, rivers, reservoirs with water in 2023 |
| 4 | forest / trees | continuous tree canopy outside any compound |
| 5 | other open | farmland, barren, rock, grass, vacant plots, open construction ground |
| 0 | no label / no prediction | |

Classes describe the **use of the plot**, not the surface. A lawn inside an IT campus is 2,
trees inside a housing colony are 1. The full rules are in
`data/processed/lu/LABELLING_GUIDE.md`.

---

## 3. How the data was made, step by step

```
Earth Engine layers ──► 76-band tiles (10 m) ──► 181 features per pixel ─┐
OpenStreetMap + land-cover maps ──► label tiles ──► sampled pixels ──────┼─► LightGBM ─► map
325 hand-labelled pixels (test only) ────────────────────────────────────┘      │
existing land-use products on the same grid ──► audited on the same pixels ◄────┘
```

### 3.1 The grid

- **Study area:** the HMDA boundary from OpenStreetMap (relation 15027443), reprojected to
  EPSG:32644. Stored as `data/processed/aoi_utm44n.gpkg`.
- **Tiles:** the area is cut into squares whose corners are multiples of 4,000 m. Every tile
  that touches HMDA is kept: 556 tiles (`tile_grid()` in `lu_common.py`).
- **Why 4 km:** Earth Engine refuses single downloads above 50 MB. A 4 km tile of 76 bands is
  about 37 MB.
- **Every layer below is put on this same grid**, so pixel (row, col) of tile `k` means the
  same 10 m square of ground in every folder.

### 3.2 The four input layers (`03_download_features.py`, `base_stack()` in `lu_common.py`)

Each layer is built in Google Earth Engine for one calendar year and downloaded on the grid.

**Sentinel-2 (7 bands).**
- Source: `COPERNICUS/S2_SR_HARMONIZED`, all scenes from 1 January to 31 December.
- Cloud removal: each scene is joined to Cloud Score+ (`GOOGLE/CLOUD_SCORE_PLUS/V1/S2_HARMONIZED`)
  and pixels with `cs_cdf` < 0.6 are masked out.
- Composite: the **per-pixel median** of what is left. One clean image for the year.
- Bands kept: B2 blue, B3 green, B4 red, B5 red-edge, B8 near-infrared, B11 and B12
  short-wave infrared. B5, B11 and B12 are 20 m natively and are resampled to 10 m.
- Stored as surface reflectance × 10,000.

**Open Buildings 2.5D Temporal (4 bands).**
- Source: `GOOGLE/Research/open-buildings-temporal/v1`, on a 0.5 m grid, one mosaic per year.
- A 0.5 m cell counts as building where `building_presence` > 0.5.
- Aggregated to each 10 m pixel:
  - `ob_cov` = share of the 0.5 m cells that are building;
  - `ob_h` = mean `building_height` over the building cells (0 where there are none);
  - `ob_hmax` = maximum `building_height` over the building cells;
  - `ob_cnt` = sum of `building_fractional_count`, a measure of how many buildings fall in
    the pixel.

**VIIRS night lights (1 band).**
- Source: `NOAA/VIIRS/DNB/ANNUAL_V21` up to 2021 and `ANNUAL_V22` from 2022, band `average`.
- About 500 m natively, so every 10 m pixel inside one VIIRS cell holds the same value.

**AlphaEarth embeddings (64 bands).**
- Source: `GOOGLE/SATELLITE_EMBEDDING/V1/ANNUAL`, the annual mosaic.
- A learned 64-number summary of a year of multi-sensor imagery at 10 m. Values run from −1
  to 1 and have no physical unit.

**Storage.** The 76 bands are multiplied by the factors in section 5.1, converted to 16-bit
integers and saved as one deflate-compressed GeoTIFF per tile. Each tile is downloaded in
three band groups (1–7, 8–12, 13–76) and merged, because a single 76-band request exceeds
Earth Engine's memory limit.

### 3.3 From 76 bands to 181 features (`lu_features.compute()`)

Features are computed on your machine from the tiles, never in Earth Engine. The **same
function** makes the features for training pixels and for the full map.

**Step 1: undo the scaling** (divide by the factors in section 5.1).

**Step 2: spectral indices** from the Sentinel-2 bands. Each is a normalised difference,
(a − b) / (a + b), so it runs from −1 to 1:

| index | formula | high where |
|---|---|---|
| `ndvi` | (B8 − B4) / (B8 + B4) | vegetation |
| `ndbi` | (B11 − B8) / (B11 + B8) | built-up and bare ground |
| `mndwi` | (B3 − B11) / (B3 + B11) | water |
| `bsi` | ((B11 + B4) − (B8 + B2)) / ((B11 + B4) + (B8 + B2)) | bare soil |

**Step 3: neighbourhood features.** A single 10 m pixel cannot tell a house from a factory,
but its surroundings can. Each quantity is averaged over square windows of 7, 15, 31 and 61
pixels (70 m, 150 m, 310 m, 610 m), written as a suffix: `ndvi_15` is NDVI averaged over
150 m.

- To avoid seams, a tile is read together with its 8 neighbours, the windows are computed, and
  only the centre tile is kept.

| feature | how it is computed | meaning |
|---|---|---|
| `cov_w` | mean of `ob_cov` | built-up share of the neighbourhood |
| `cnt_w` | mean of `ob_cnt` × 100 | building density (relative units) |
| `bldg_area_w` | `cov_w` × 100 ÷ mean `ob_cnt` (0 where there are no buildings) | **size of the average building footprint**, in relative units. Small for houses, large for sheds and campuses |
| `bldg_h_w` | mean of (`ob_h` × `ob_cov`) ÷ `cov_w` | cover-weighted mean building height, m |
| `hmax_15`, `hmax_31` | maximum of `ob_hmax` | tallest building nearby |
| `h_sd_15` | standard deviation of `ob_h` over 150 m | how mixed the heights are |
| `ndvi_w`, `ndbi_w`, `mndwi_w` | mean of the index | greenness, built-up, wetness of the neighbourhood |
| `viirs_w` | mean of `viirs` | night-time brightness of the neighbourhood |
| `b8_sd_7`, `b8_sd_15` | standard deviation of B8 | texture: rough (mixed roofs and trees) or smooth (fields, water) |
| `A00_15` … `A63_15` | mean of each embedding band over 150 m | embedding of the neighbourhood |

**The full list (181 columns):**

| count | family | columns |
|---|---|---|
| 7 | Sentinel-2 bands | `B2 B3 B4 B5 B8 B11 B12` |
| 4 | Sentinel-2 indices | `ndvi` `ndbi` `mndwi` `bsi` |
| 12 | index neighbourhood means | `ndvi_w` `ndbi_w` `mndwi_w`, w = 7, 15, 31, 61 |
| 2 | texture | `b8_sd_7` `b8_sd_15` |
| 4 | buildings, pixel | `ob_cov` `ob_h` `ob_hmax` `ob_cnt` |
| 19 | buildings, neighbourhood | `cov_w` `cnt_w` `bldg_area_w` `bldg_h_w` (w = 7, 15, 31, 61), `hmax_15` `hmax_31`, `h_sd_15` |
| 5 | night lights | `viirs`, `viirs_w` (w = 7, 15, 31, 61) |
| 64 | AlphaEarth, pixel | `A00` … `A63` |
| 64 | AlphaEarth, 150 m | `A00_15` … `A63_15` |

The 53 columns that are not AlphaEarth are physical measurements. Dropping all 128 AlphaEarth
columns leaves the hand-label score essentially unchanged (macro-F1 0.626 against 0.627), so
the 53 are a reasonable smaller set. `compute(tile, aef=False)` returns just those. Details
are in `FEATURES.md`.

### 3.4 Training labels (`04_labels.py`)

There is no ground-truth land-use map of Hyderabad, so labels are built from OpenStreetMap
(for the built classes) and from agreement between land-cover maps (for the natural classes).
They are **weak labels**: plentiful, not hand-checked.

| class | rule |
|---|---|
| 1 | OSM `landuse=residential` polygons, and OSM buildings tagged as housing |
| 2 | OSM industrial / commercial / retail / education / civic land, institutional amenities (school, hospital, police, …), and buildings tagged as such. Painted after class 1, so a school inside a residential polygon stays 2 |
| 3 | at least two of: JRC surface-water occurrence ≥ 80%, WorldCover water, Dynamic World 2023 water |
| 4 | OSM forest polygon, or WorldCover tree **and** Dynamic World tree; outside OSM built land |
| 5 | OSM farmland / grass / quarry etc., or WorldCover **and** Dynamic World both say crop / grass / bare / shrub and GHS says not built; outside OSM built land |
| 0 | everything else: unlabelled, not used |

- The OSM polygons are rasterised onto the 10 m grid, one label tile per feature tile.
- **Pixels within 300 m of a hand-labelled test pixel are set to 0**, so the test set is never
  trained on.

### 3.5 Sampling the training pixels (`05_sample_pixels.py`)

- From each tile, up to **200 random pixels of each class** present in its label tile.
- For each sampled pixel: its 181 features, its label, its position, and the value of every
  existing product at that pixel (for the audit).
- Result: `samples.parquet`, 393,098 pixels from 556 tiles.

The class mix of this table is set by the sampling, not by how common each class is on the
ground.

### 3.6 The hand-labelled test set (`02_validation_sample.py`)

The only independent ground truth.

- **Design:** a stratified random sample of 325 pixels. The strata do not depend on any model
  we train:

  | stratum | definition | area share (`weight`) | pixels labelled |
  |---|---|---|---|
  | 1 | inside OSM non-residential polygons | 2.1% | 70 |
  | 2 | Dynamic World 2023 "built", elsewhere | 22.5% | 130 |
  | 3 | Dynamic World water | 3.3% | 30 |
  | 4 | Dynamic World trees | 13.6% | 35 |
  | 5 | everything else | 58.5% | 60 |

- **Labelling:** each 10 m square was labelled by eye on 2023 high-resolution imagery,
  following `LABELLING_GUIDE.md`, without seeing its stratum.
- **Weights:** built-up strata were over-sampled on purpose, because that is where the
  difficult cases are. Each stratum is therefore weighted by its true area share when scoring
  (Olofsson et al. 2014). A plain average over the 325 pixels is wrong.

### 3.7 Existing products on the same grid

Used only for comparison (and, for three land-cover maps, as label evidence in 3.4). Never as
model inputs.

| product | how it was put on our grid |
|---|---|
| Dynamic World, WorldCover, JRC water, GHS-BUILT-C, WRI urban land use, Global Industrial Land | downloaded from Earth Engine on the tile grid as one 6-band tile (`03b_download_products.py`). Dynamic World is the most frequent label over 2023 |
| GULU | one India-wide GeoTIFF, sampled at pixel centres |
| EULUC-Globe 2024 | parcel polygons clipped to HMDA and rasterised (`12_euluc.py`) |
| BigEarthNet v2 ResNet-50, SenCLIP | pretrained models run on our Sentinel-2 tiles without any training on Hyderabad (`08`, `11`); their classes are translated to our five |

### 3.8 Model, cross-validation and map

- **Model:** LightGBM, 400 trees, learning rate 0.05, 63 leaves, 80% row sampling, 60% column
  sampling, classes weighted to balance (`06_train_eval.py`, `09_predict_map.py`).
- **Spatial cross-validation:** tiles are grouped into 12 km blocks (3 × 3 tiles) and whole
  blocks are held out, 5 folds. Neighbouring pixels look alike, so a random split would give
  scores that are far too high.
- **Map:** the model trained on all samples is applied to every pixel of every tile
  (`pred_2023/`), then mosaicked and clipped to HMDA.

### 3.9 Proximity distances (`20_proximity.py`)

Straight-line distances in km from a pixel centre. Computed in EPSG:32644.

| column | distance to | how the target was obtained |
|---|---|---|
| `d_cbd_abids`, `d_charminar`, `d_secunderabad`, `d_hitec_cyber_towers`, `d_financial_district`, `d_airport_rgia` | a fixed landmark | coordinates in `LANDMARKS`, checked against OSM |
| `d_employment` | the nearer of Cyber Towers and the Financial District | minimum of the two |
| `d_orr_access` | nearest Outer Ring Road interchange | end points of OSM `motorway_link` ways within 30 m of the ORR, grouped into 800 m cells: 54 points (`prox/orr_access.gpkg`) |
| `d_metro_2017`, `d_metro_2020` | nearest metro station open by the end of that year | 57 stations with opening dates (`prox/metro_stations_opening.csv`). All were open by February 2020 |
| `d_major_road_2023` | nearest major road | OSM ways tagged motorway, trunk, primary, secondary and their links, as mapped on 1 January 2023: 6,205 ways, 5,251 km (`prox/roads_major_2023.gpkg`) |

**These distances are not model inputs.** We tested adding them to the classifier
(`16_proximity_features.py`) and they did not help:

| feature set | spatial CV | hand labels | change (95% interval) |
|---|---|---|---|
| 53 physical | 0.873 | 0.626 | – |
| + all 10 distances | 0.871 | 0.639 | +0.013 (−0.013 to +0.039) |
| + x, y coordinates instead | 0.872 | 0.640 | +0.014 (−0.008 to +0.038) |
| distances only | 0.243 | 0.317 | |

Raw map coordinates do as well as the distances, and distances alone are near chance, so the
model uses them to learn *where* the labelled estates are, not what being near a road means.
Results are in `outputs/lu/proximity_features/`.

---

## 4. Files in this repository

Paths are under `data/processed/lu/` unless shown otherwise.

### 4.1 `samples.parquet`: the training table

Stored as `samples_parts/samples_part1.parquet` and `samples_part2.parquet` because GitHub
limits files to 100 MB. `00_join_samples.py` joins them.

**393,098 rows × 194 columns.** One row is one labelled 10 m pixel.

| columns | count | meaning |
|---|---|---|
| feature columns | 181 | model inputs (section 3.3), in real units, not scaled |
| `label` | 1 | class 1–5 from the rules in section 3.4 |
| `tile` | 1 | tile name |
| `x`, `y` | 2 | pixel centre, EPSG:32644 |
| `row`, `col` | 2 | position of the pixel inside its tile |
| `p_dw`, `p_wc`, `p_jrc`, `p_ghsc`, `p_wri`, `p_ind`, `p_gulu` | 7 | what each existing product says at that pixel, in the product's **own** codes (section 5.2). For the audit only. **Never use them as features** |

**Rows per class:** residential 61,916 · non-residential 37,646 · water 71,334 · forest
111,002 · open 111,200.

### 4.2 The hand-labelled test set

| file | content |
|---|---|
| `validation_points.gpkg` (layer `validation_pixels`) | 325 squares of 10 m, EPSG:32644. Columns: `pid`, `lon`, `lat`, `true_class` (1–5), `confidence` (1 sure, 2 probably, 3 guess), `is_road` (1 if the pixel is on a road), `notes` |
| `validation_points.kml` | the same squares for Google Earth Pro |
| `validation_key.csv` | `pid`, `stratum`, `stratum_weight`, `lon`, `lat`. Kept apart from the labelling file so the labeller could not see the stratum |
| `validation_strata.csv` | per stratum: `pixels_10m`, `area_km2`, `weight`, `n_sample` |
| `validation_features.parquet` | 325 × 186: the 181 features at each test pixel, plus `pid`, `stratum`, `true_class`, `confidence`, `is_road`. Lets you score a new model without the raster zip |
| `sisdp_at_validation.json` | a list of `[pid, class name]`: the NRSC SIS-DP 1:10K (2016–19) class at each test pixel, in NRSC's own wording |
| `LABELLING_GUIDE.md` | the rules used when labelling |

**Labels by class:** residential 32 · non-residential 41 · water 26 · forest 51 · open 175.
Confidence: 262 sure, 51 probably, 10 guesses, 2 blank. 20 pixels are on roads. The headline
uses only pixels with `confidence` ≤ 2 (313 pixels).

### 4.3 Model, predictions and supporting files

| file | content |
|---|---|
| `model_all_2023.pkl` | a Python pickle holding a tuple `(model, columns)`: a fitted `lightgbm.LGBMClassifier` and the list of its 181 feature names **in the order the model expects**. Trained on all 393,098 samples |
| `oof_predictions.parquet` | 393,098 rows: `tile`, `x`, `y`, `label`, `block` (the 12 km cross-validation block), and the out-of-fold predicted class from four feature sets: `oof_S2`, `oof_S2+BLD`, `oof_AEF`, `oof_ALL` |
| `label_stats.csv` | per tile, how many pixels carry each label (`c0` = unlabelled … `c5`) |
| `prox/roads_major_2023.gpkg`, `prox/orr_access.gpkg`, `prox/metro_stations_opening.csv` | inputs for the proximity distances (section 3.9) |
| `data/processed/aoi_utm44n.gpkg` | the HMDA boundary, used to clip the map |

### 4.4 Result tables and maps (`outputs/lu/`)

| file | content |
|---|---|
| `handlabel_eval.csv` | **headline table.** Every model and product scored on the hand labels, for three subsets (`conf<=2`, `all`, `conf<=2, no roads`). `UA_c` = user's accuracy (precision), `PA_c` = producer's accuracy (recall), `F1_c` per class, `macro_F1` with a 95% interval (`_lo`, `_hi`), `coverage` = share of test pixels the product covers |
| `handlabel_confusion_<model>.csv` | area-weighted confusion matrix on the hand labels. Rows = predicted, columns = true |
| `cv_ablation.csv` | spatial cross-validation on the OSM-derived labels for the four feature sets |
| `audit_products.csv`, `confusion_<product>.csv`, `existing_products_vs_osm.csv` | existing products scored on the OSM-derived labels |
| `feature_importance.csv` | top 40 features by LightGBM gain |
| `features/` | feature analysis from `15_feature_analysis.py`: catalogue of all features, SHAP per class, redundancy clusters, reduced feature sets (explained in `FEATURES.md`) |
| `proximity_features/` | the proximity test: `cv.csv`, `handlabel.csv`, `shap_by_class.csv`, `shap_dependence.csv` / `.png` |
| `unet_vs_lgbm.csv` | U-Net against LightGBM on the same held-out fold |
| `landuse_hmda_2023_10m.tif` | the 10 m map of HMDA, one band, values 1–5, 0 outside HMDA, EPSG:32644 |
| `landuse_hmda_2023.png`, `landuse_hmda_2023_shares.json` | picture of the map and the area share of each class |
| `change/` | the 2017 → 2023 class-change test for two areas (Lingampally, Gachibowli / Financial District) |

---

## 5. Files in the raster zip

All folders sit under `data/raw/lu/`. Every per-tile raster is a GeoTIFF of 400 × 400 pixels
at 10 m in EPSG:32644, named by tile.

| folder | tiles | bands | type | what it is | made by |
|---|---|---|---|---|---|
| `feat_2023/` | 556 | 76 | int16 | the model inputs for 2023 (section 5.1), plus `tiles.json` | `03` |
| `prod/` | 556 | 6 | uint8 | six existing products (section 5.2) | `03b` |
| `lab/` | 556 | 1 | uint8 | training label, 0–5 (section 3.4) | `04` |
| `pred_2023/` | 556 | 2 | uint8 | our map: band 1 = class 1–5, band 2 = probability of that class × 100 | `09` |
| `ben/` | 556 | 1 | uint8 | BigEarthNet v2 ResNet-50 prediction, translated to our 5 classes | `08` |
| `senclip/` | 556 | 1 | uint8 | SenCLIP zero-shot prediction, translated to our 5 classes | `11` |
| `euluc/*.tif` | 556 | 1 | uint8 | EULUC-Globe 2024 parcels, translated to our 5 classes (0 = no parcel) | `12` |
| `unet_2023/` | 111 | 1 | uint8 | U-Net prediction, on its held-out tiles only | `10` |
| `gulu/IND.tif` | 1 file | 1 | uint8 | GULU 10 m land use for India | downloaded |
| `feat_2017/`, `feat_2020/` | 22 each | 76 | int16 | the same 76 bands for earlier years, for the two change-test areas only | `03`, `13` |

`feat_2023/tiles.json` maps each tile name to its bounds `[minx, miny, maxx, maxy]` in
EPSG:32644.

### 5.1 The 76 bands of a feature tile

GeoTIFFs downloaded from Earth Engine lose their band names, so the **order is fixed in
`lu_common.BANDS`**. Values are stored as scaled whole numbers. **Divide by the factor to get
the real value.**

| band (1-based) | name | what it measures | divide by | real unit | 5th–95th percentile in the training pixels |
|---|---|---|---|---|---|
| 1 | `B2` | blue reflectance (490 nm) | 10,000 | 0–1 | 0.04–0.15 |
| 2 | `B3` | green reflectance (560 nm) | 10,000 | 0–1 | 0.05–0.18 |
| 3 | `B4` | red reflectance (665 nm) | 10,000 | 0–1 | 0.04–0.22 |
| 4 | `B5` | red-edge reflectance (705 nm) | 10,000 | 0–1 | 0.05–0.24 |
| 5 | `B8` | near-infrared reflectance (842 nm); high over vegetation, low over water | 10,000 | 0–1 | 0.02–0.33 |
| 6 | `B11` | short-wave infrared (1610 nm); high over bare ground and roofs, very low over water | 10,000 | 0–1 | 0.02–0.37 |
| 7 | `B12` | short-wave infrared (2190 nm) | 10,000 | 0–1 | 0.02–0.30 |
| 8 | `ob_cov` | share of the pixel covered by buildings | 1,000 | 0–1 | 0–0.56; 0 in most pixels, median 0.16 in residential ones |
| 9 | `ob_h` | mean building height | 10 | metres | 0–5.7; residential median 3.3, 95th percentile 13.5 |
| 10 | `ob_hmax` | maximum building height | 10 | metres | 0–7.0 |
| 11 | `ob_cnt` | building count in the pixel, **relative units** (see section 8) | 10,000 | relative | 0–0.002 |
| 12 | `viirs` | night-light radiance | 100 | nW / cm² / sr | 0.9–35; median 2 in open land, 6 residential, 15 non-residential |
| 13–76 | `A00` … `A63` | AlphaEarth embedding | 1,000 | none | −0.22 to 0.20 |

Worked example: a stored value of 775 in band 9 is a mean building height of 77.5 m.

### 5.2 The 6 bands of a product tile (`prod/`)

uint8, **255 = no data or outside the product's extent**. The `p_*` columns of
`samples.parquet` hold the same codes.

| band | column | product | codes |
|---|---|---|---|
| 1 | `p_dw` | Dynamic World 2023, most frequent label | 0 water, 1 trees, 2 grass, 3 flooded vegetation, 4 crops, 5 shrub, 6 built, 7 bare, 8 snow |
| 2 | `p_wc` | ESA WorldCover 2021 | 10 tree, 20 shrub, 30 grass, 40 crop, 50 built, 60 bare, 80 water, 90 wetland |
| 3 | `p_jrc` | JRC Global Surface Water, occurrence 1984–2021 | 0–100 (% of time under water) |
| 4 | `p_ghsc` | GHS-BUILT-C 2018 | 1–5 open types, 11–15 residential, 21–25 non-residential |
| 5 | `p_wri` | WRI intra-urban land use V1 | 0 open, 1 non-residential, 2 atomistic, 3 informal, 4 formal, 5 housing project, 6 road |
| 6 | `p_ind` | Global Industrial Land 2023 | 0 non-built, 1 industrial, 2 other built |

`p_gulu` comes from `gulu/IND.tif`, not from `prod/`.

**Product code → our class.** The translation tables are `PRODUCT_MAPS` in
`06_train_eval.py`. Two special values appear after translation: `0` = the product says
nothing here, `9` = "built, but the product does not say which use".

---

## 6. How to use the data

Run these from the repository root. The scripts import each other, so put their folder on the
path first:

```python
import sys; sys.path.insert(0, "scripts/lu")
```

**Load the training table and pick the feature columns:**

```python
import pandas as pd
s = pd.read_parquet("data/processed/lu/samples.parquet")
meta = {"label", "tile", "x", "y", "row", "col"} | {c for c in s if c.startswith("p_")}
cols = [c for c in s.columns if c not in meta]            # 181 features
phys = [c for c in cols if not (c[0] == "A" and c[1:3].isdigit())]   # the 53 physical ones
```

**Cross-validate by 12 km blocks, never by random rows:**

```python
from sklearn.model_selection import GroupKFold
tx = s.tile.str.extract(r"x(\d+)_y(\d+)").astype(int)
s["block"] = (tx[0] // 12).astype(str) + "_" + (tx[1] // 12).astype(str)
folds = GroupKFold(n_splits=5).split(s, s.label, s.block)
```

**Use the trained model:**

```python
import pickle
model, cols = pickle.load(open("data/processed/lu/model_all_2023.pkl", "rb"))
pred = model.predict(s[cols])            # classes 1-5
prob = model.predict_proba(s[cols])      # columns in the order model.classes_
```

**Score any model on the hand labels (the number to report):**

```python
import importlib.util as iu, pandas as pd
spec = iu.spec_from_file_location("eh", "scripts/lu/07_eval_handlabels.py")
eh = iu.module_from_spec(spec); spec.loader.exec_module(eh)

V = pd.read_parquet("data/processed/lu/validation_features.parquet")
V = V[(V.confidence.fillna(3) <= 2) & V.true_class.notna()]
W = pd.read_csv("data/processed/lu/validation_strata.csv", index_col=0)["weight"].to_dict()

ref, pred, st = V.true_class.astype(int).values, model.predict(V[cols]), V.stratum.values
metrics, confusion = eh.weighted(ref, pred, st, W)       # metrics["macro_F1"], metrics["F1_2"], ...
lo, hi = eh.bootstrap(ref, pred, st, W)                  # 95% interval
```

**Read a tile and get real values** (needs the raster zip):

```python
import rasterio
from lu_common import BANDS
with rasterio.open("data/raw/lu/feat_2023/x228_y1920.tif") as r:
    a = r.read()                            # (76, 400, 400) int16
nir, red = a[BANDS.index("B8")] / 1e4, a[BANDS.index("B4")] / 1e4     # reflectance 0-1
height_m = a[BANDS.index("ob_h")] / 10
```

**Compute the features for a tile** (needs the raster zip):

```python
import lu_features as F
names, arr = F.compute("x228_y1920")               # arr is (181, 400, 400) float32
names53, arr53 = F.compute("x228_y1920", aef=False)   # the 53 physical features only
```

**Find the pixel for a coordinate** (x, y in EPSG:32644):

```python
tile = f"x{int(x // 4000 * 4)}_y{int(y // 4000 * 4)}"
minx, miny, maxx, maxy = F.tiles()[tile]
row, col = int((maxy - y) // 10), int((x - minx) // 10)
```

**Distances for any set of points:**

```python
import importlib.util as iu
spec = iu.spec_from_file_location("px", "scripts/lu/20_proximity.py")
px = iu.module_from_spec(spec); spec.loader.exec_module(px)
d = px.Prox(years=("2023",)).at(s.x.values, s.y.values)    # DataFrame of d_* columns, km
```

---

## 7. What you can run with what you have

| script | what it does | needs |
|---|---|---|
| `00_join_samples.py` | builds `samples.parquet` | repository only |
| `06_train_eval.py` | spatial CV for four feature sets, audit of products | repository only (uses `ben/`, `senclip/`, `euluc/` from the zip if present) |
| `15_feature_analysis.py` | SHAP legend, redundancy, reduced feature sets; about 75 min | repository only |
| `16_proximity_features.py` | the proximity test; about 85 min | repository only |
| `20_proximity.py` | distances at given points | repository only |
| `07_eval_handlabels.py` | headline table on the hand labels | repository + zip |
| `09_predict_map.py` | retrains, maps any tile without a prediction, rebuilds the mosaic | repository + zip |
| `05_sample_pixels.py` | re-samples training pixels from the tiles | repository + zip |
| `13_change.py --no-download` | class-change test for two areas | repository + zip |
| `03*_download_*.py` | downloads tiles from Earth Engine | an Earth Engine account; set the environment variable `EE_PROJECT` to your own project |
| `01`, `02`, `04` | OSM label sources, test-sample design, label tiles | OSM download caches that are **not shared** (their outputs are: `lab/` and the validation files) |
| `08`, `10`, `11` | BigEarthNet, U-Net, SenCLIP | PyTorch and model weights that are **not shared** (their outputs are in the zip) |
| `12_euluc.py` | rasterises EULUC-Globe | the 16 GB EULUC-Globe Asia download (its output is in the zip) |

---

## 8. Things to watch out for

- **Two kinds of accuracy, very different numbers.** On the OSM-derived labels the model
  scores about 0.90 macro-F1; on the hand labels 0.62 (95% interval 0.55–0.69). The OSM score
  is optimistic: it only tests places OSM has mapped, with an artificial class mix. Report the
  hand-label number.
- **Non-residential is the weak class.** F1 is about 0.41 on the hand labels, and only about
  30% of pixels predicted non-residential are correct.
- **The hand-label set is small.** 39 usable non-residential pixels. A change in macro-F1
  smaller than about 0.04 cannot be told apart from noise.
- **Always use the stratum weights** on the hand labels (section 3.6).
- **The training labels are weak.** OSM polygons are incomplete and sometimes wrong. OSM marks
  a whole campus as non-residential, including its open ground.
- **Water labels need two sources to agree.** JRC stops in 2021 and misses newer reservoirs
  such as Kondapochamma Sagar.
- **Never train on `p_*` columns**, and never train on the 325 test pixels.
- **Tile values are scaled integers; `samples.parquet` values are real.** Do not divide twice.
- **Building count and footprint size are in relative units.** `ob_cnt`, `cnt_w` and
  `bldg_area_w` are consistent with each other and rank places correctly (the median
  `bldg_area_15` is about 22,000 for residential pixels and 74,000 for non-residential ones),
  but the aggregation in Earth Engine did not preserve absolute counts, so do not read
  `bldg_area_w` as square metres or `ob_cnt` as a true number of buildings.
- **VIIRS is about 500 m.** `viirs` is constant across a block of roughly 50 × 50 pixels.
- **`gulu/IND.tif` has a broken CRS tag.** The data is in EPSG:3857; convert coordinates
  before sampling (see `gulu_at()` in `05_sample_pixels.py`).
- **`unet_2023/` covers 111 tiles only**, so the U-Net score is on a quarter of the test
  pixels.
- **Class change between years is not reliable.** In the Lingampally test 24% of pixels
  "changed" class between 2017 and 2023 although little changed on the ground.
- **The pickle needs a matching `lightgbm`.** If it will not load, retrain with
  `09_predict_map.train()`; it takes a few minutes.

---

## 9. Sources and licences

| data | source | licence / terms |
|---|---|---|
| Sentinel-2 L2A | Copernicus, via Earth Engine `COPERNICUS/S2_SR_HARMONIZED` | free and open (Copernicus) |
| Open Buildings 2.5D Temporal | Google, `GOOGLE/Research/open-buildings-temporal/v1` | CC BY 4.0 |
| VIIRS night lights | Earth Observation Group, `NOAA/VIIRS/DNB/ANNUAL_V21` and `V22` | CC BY 4.0 |
| AlphaEarth embeddings | Google, `GOOGLE/SATELLITE_EMBEDDING/V1/ANNUAL` | CC BY 4.0 |
| OpenStreetMap (labels, roads, boundary) | © OpenStreetMap contributors | ODbL |
| Dynamic World, ESA WorldCover | Google / ESA | CC BY 4.0 |
| JRC Global Surface Water, GHS-BUILT-C | European Commission JRC | free with attribution |
| WRI urban land use, Global Industrial Land, GULU, EULUC-Globe | the respective authors | check each product's terms before redistributing |
| NRSC SIS-DP | Bhuvan, NRSC / ISRO | check Bhuvan terms |
