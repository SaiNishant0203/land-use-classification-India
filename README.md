# Land-Use Classification for Hyderabad (HMDA): Progress Update

**Project:** Land use and transportation planning in Hyderabad
**Status as of:** September 2026
**Scope of this update:** the pixel-level land-use model (LightGBM): its inputs, design and
outputs, how it was tested, and how it compares with existing land-use products

---

## 1. Summary

- We built a model that labels every 10 m pixel in the Hyderabad Metropolitan Development
  Authority (HMDA) area with one of five land-use classes, using 2023 satellite and
  building data.
- **On an independent, hand-labelled test set, it scores macro-F1 0.62 (95% CI 0.55–0.69).**
  - The best existing product scores 0.38 on the same test pixels.
  - Nine existing global and research products were tested. All perform poorly on Hyderabad.
- **Building shape and height, from Google Open Buildings 2.5D, are the most useful input.**
  They help most with telling residential from non-residential buildings.
- **Limitation:** non-residential land is still identified poorly (F1 0.41). Maps of
  year-to-year class change are too noisy to use.
- This motivates the next step: estimate **floor space and land-use shares per zone** instead
  of relying on labels for individual pixels.

---

## 2. What the model does

**Input:** 181 numbers per 10 m pixel, derived from 2023 satellite and building data.

**Output:** one of five classes per pixel.

| code | class | why it matters for transport |
|---|---|---|
| 1 | Residential | trip productions (where trips start) |
| 2 | Non-residential built (commercial, industrial, institutional) | trip attractions (where trips end) |
| 3 | Water | not developable |
| 4 | Forest / trees | not developable |
| 5 | Other open (farmland, barren, vacant) | land available for development |

The scheme is kept deliberately small. Transport planning mainly needs to know where people
live and where activity happens.

---

## 3. Pipeline overview

```
Satellite + building data (2023, Google Earth Engine)
        │
        ▼
Feature engineering  →  181 features per pixel
        │
        ▼
Training labels (OpenStreetMap + agreement between land-cover products)
        │
        ▼
LightGBM classifier  ──►  Test A: spatial cross-validation (393k pixels)
        │               ──►  Test B: 325 hand-labelled pixels (headline result)
        ▼
10 m land-use map of HMDA (2023)
```

---

## 4. Input data

All inputs are from 2023. They are resampled to the same 10 m grid and downloaded in 4 km
tiles.

| source | resolution | what it provides | why it helps |
|---|---|---|---|
| **Sentinel-2** (7 bands: blue, green, red, red-edge, NIR, 2× SWIR) | 10–20 m | Surface reflectance. Uses the median of the year, with clouds removed using Cloud Score+. | Separates vegetation, water, concrete and bare soil |
| **Google Open Buildings 2.5D Temporal** | 0.5 m, aggregated to 10 m | Building cover, mean height, maximum height, building count | Building form: a factory, an office tower and a house look different in size and height |
| **VIIRS night lights** | ~500 m | Night-time brightness | Indicates the intensity of activity |
| **AlphaEarth satellite embeddings** (Google) | 10 m | 64 learned values per pixel that summarise a year of multi-sensor data | A general-purpose "fingerprint" of each location |

## 5. Feature engineering (76 raw bands → 181 features)

1. **Spectral indices:**
   - NDVI (vegetation)
   - NDBI (built-up)
   - MNDWI (water)
   - BSI (bare soil)
2. **Neighbourhood context.** A single pixel cannot show that it lies inside an industrial
   estate, but its surroundings can. For windows of **70 m, 150 m, 310 m and 610 m**, we
   compute:
   - building cover, building count, **average building size (m²)** and **average building
     height**;
   - average NDVI, NDBI, MNDWI and night lights;
   - maximum building height (150 m and 310 m windows only).
3. **Texture:** local variability of near-infrared reflectance and of building height.
4. **AlphaEarth:** the 64 values at the pixel, plus their averages over 150 m.

Tiles are processed together with their neighbours, so window-based features have no
artefacts at tile edges.

---

## 6. Training labels

There is no official land-use map of Hyderabad at this resolution. Training labels were
therefore built from open sources:

- **Residential / non-residential:** OpenStreetMap.
  - Residential: land-use polygons tagged residential, and buildings tagged as houses or
    apartments.
  - Non-residential: polygons tagged industrial, commercial, retail, education or civic, plus
    offices, malls, schools, hospitals and other institutions.
  - Non-residential is applied after residential. A school inside a residential colony is
    therefore labelled non-residential.
- **Water:** labelled only where at least two of three products agree (JRC Global Surface
  Water, ESA WorldCover and Dynamic World).
  - JRC alone misses reservoirs built after 2021 (e.g. Kondapochamma Sagar). Using it alone
    made the model call those reservoirs residential.
- **Forest and other open:** OpenStreetMap tags, or pixels where ESA WorldCover and Dynamic
  World agree.
- **No overlap with the test set:** every training pixel within 300 m of a hand-labelled test
  pixel was removed.

**Sampling:** up to 200 pixels per class per tile, across 556 tiles.

| class | training pixels |
|---|---|
| Residential | 61,916 |
| Non-residential | 37,646 |
| Water | 71,334 |
| Forest / trees | 111,002 |
| Other open | 111,200 |
| **Total** | **393,098** |

---

## 7. Model: LightGBM

**LightGBM** is a gradient-boosted decision-tree model.
- It builds a sequence of small decision trees. Each new tree corrects the errors of the
  trees before it.
- The final prediction combines all the trees.
- It suits this problem because the data is tabular (one row per pixel). It trains quickly
  on a CPU and shows which features it relies on.

| setting | value | purpose |
|---|---|---|
| Number of trees | 400 | |
| Learning rate | 0.05 | how much each tree changes the prediction |
| Leaves per tree | 63 | model complexity |
| Row sampling | 80% per tree | reduces overfitting |
| Feature sampling | 60% per tree | reduces overfitting |
| Class weighting | balanced | keeps rarer classes (non-residential) from being ignored |

These are standard settings. No hyperparameter tuning has been done yet.

**Most important features** (share of total gain):

| rank | feature | share |
|---|---|---|
| 1 | SWIR reflectance (B11): concrete vs soil | 13% |
| 2 | Vegetation (NDVI) within 70 m | 9% |
| 3 | Building count within 150 m | 8% |
| 4 | Building count within 70 m | 5% |
| 5 | AlphaEarth dimension 42 | 4% |
| 6 | Average building size within 310 m | 3% |

---

## 8. How the model was tested

Two independent tests were run.

### Test A: spatial cross-validation (OpenStreetMap labels, 393k pixels)

- **Purpose:** to compare feature sets and existing products on a large sample.
- **Blocking:** HMDA was divided into **12 km blocks**. Each block is either entirely in
  training or entirely in testing (5-fold GroupKFold).
  - This prevents the model from scoring well simply by memorising a neighbourhood.
- **Feature ablation:** the model was trained with different input groups, to measure what
  each data source contributes.

| features used | no. of features | macro-F1 | residential F1 | non-residential F1 |
|---|---|---|---|---|
| Sentinel-2 only | 25 | 0.829 | 0.82 | 0.58 |
| + building morphology + night lights | 53 | 0.875 | 0.91 | 0.68 |
| AlphaEarth embeddings only | 128 | 0.872 | 0.88 | 0.65 |
| **All features** | **181** | **0.898** | **0.92** | **0.72** |

**Caution:** these scores are optimistic.
- OpenStreetMap labels come from well-mapped, clear-cut areas.
- Their class mix does not match HMDA as a whole.

### Test B: hand-labelled validation (headline result)

- **Test set:** 325 pixels, stratified and randomly placed. Each was labelled by hand from
  high-resolution imagery, following a written labelling guide. None of these pixels, or
  anything within 300 m of them, was used in training.
- **Scoring:** results are weighted by how common each class actually is across HMDA, using
  the standard map-accuracy estimator of Olofsson et al. (2014).
- **Confidence intervals:** 95% bootstrap intervals (500 resamples within strata).
- **Label filter:** only labels marked as confident are used (313 of 325 pixels).

**Why macro-F1 and not accuracy:** about 65% of HMDA is open land. A model that always
predicts "open" would score about 65% accuracy while being useless. Macro-F1 gives each class
equal weight.

---

## 9. Results on the hand-labelled test set

All models below are scored on the same pixels.

| model / product | coverage of test pixels | macro-F1 [95% CI] |
|---|---|---|
| **Our model (LightGBM, 181 features)** | 100% | **0.62 [0.55–0.69]** |
| Dynamic World 2023 (land cover) | 100% | 0.38 [0.33–0.45] |
| SenCLIP, zero-shot (WACV 2025) | 89% | 0.35 [0.29–0.41] |
| ESA WorldCover 2021 (land cover) | 100% | 0.34 [0.28–0.41] |
| GHS-BUILT-C 2018 | 99% | 0.30 [0.26–0.34] |
| BigEarthNet v2 ResNet-50 (Europe-trained) | 100% | 0.28 [0.24–0.33] |
| WRI Intra-urban Land Use 2020 | 29% | 0.45 (on its own coverage only) |
| EULUC-Globe 2024 (parcels) | 22% | 0.37 (on its own coverage only) |
| GULU / PPUL-Net 2020 | 19% | 0.30 (on its own coverage only) |
| Global Industrial Land 2023 | 41% | 0.19 (on its own coverage only) |

With road pixels excluded, our model scores **0.63 [0.56–0.70]**.

**Per-class results for our model:**

| class | F1 |
|---|---|
| Residential | 0.67 |
| Non-residential | 0.41 |
| Water | 0.72 |
| Forest / trees | 0.46 |
| Other open | 0.83 |

**Observations about existing products:**
- The parcel-level products (WRI, EULUC-Globe, GULU) cover only a small part of HMDA.
- GHS-BUILT-C labels almost no land as non-residential. EULUC-Globe labels about half of built
  land as non-residential. That is roughly a **tenfold disagreement**.
- BigEarthNet was trained in Europe. It labels dense old-city housing in Hyderabad as
  "industrial".

### Comparison with a deep-learning model

A U-Net was trained on the same labels and the same spatial split for comparison. It is a
convolutional network with a ResNet-34 encoder.

| model | macro-F1 (spatial CV) | macro-F1 (hand labels) |
|---|---|---|
| **LightGBM** | **0.877** | **0.62** |
| U-Net (ResNet-34) | 0.845 | 0.50* |

\*The U-Net was run only on part of HMDA, so its hand-label score covers just 78 of the test
pixels.

Engineered building features outperform learned image features in this setting.

---

## 10. Output

- **Land-use map:** a 10 m map of all of HMDA for 2023, with a class and a confidence value
  for every pixel. Files: `outputs/lu/landuse_hmda_2023_10m.tif` and `.png`.
- **Trained model:** `data/processed/lu/model_all_2023.pkl`
- **Estimated composition of HMDA, 2023:**

| class | share |
|---|---|
| Residential | 10.5% |
| Non-residential built | 8.4% |
| Water | 2.9% |
| Forest / trees | 13.5% |
| Other open | 64.7% |

---

## 11. Limitations

1. **The drop from 0.90 (Test A) to 0.62 (Test B) is expected.** The OpenStreetMap test uses
   easy, well-mapped areas. The hand-labelled test reflects real conditions, so 0.62 is the
   figure to report.
2. **Non-residential land remains difficult (F1 0.41).** Only about 30% of pixels the model
   labels non-residential are actually non-residential. The errors have three main causes:
   - **Label definitions disagree.** Open ground inside campuses and industrial compounds is
     "non-residential" in OpenStreetMap, but open or forest in the hand labels.
   - **Function is often invisible from above:** shops under homes, home businesses, and mixed
     commercial frontage.
   - **Buildings are small relative to the pixels:** a typical building is only 1.5–2
     Sentinel-2 pixels wide.
3. **Class change over time is not reliable.** The same model was run on 2017 and 2023 data
   for two 2 × 2 km areas:

   | area | real change on the ground | pixels "changing" class 2017 → 2023 |
   |---|---|---|
   | Lingampally | little | 24% |
   | Gachibowli / Financial District | construction boom | 32% |

   Most of this apparent change is model noise. In contrast, **building height and volume
   behave correctly** in the same windows:
   - Lingampally stays stable.
   - Mean building height in Gachibowli / Financial District rises from 19 m to 27 m, and
     building volume grows about 90%.
4. **Not yet done:** hyperparameter tuning. The test set is also small (325 pixels), which is
   why the confidence intervals are wide.

---

## 12. Next steps

Pixel-level labels are not accurate enough to be used directly for transport planning. The
next phase shifts to **zone-level estimates**:

1. **Floor space per zone per year (2016–2023)**, from building footprint × height in
   Open Buildings 2.5D Temporal. This is physically measured and stable over time.
2. **Residential / non-residential share per zone**, from the model's class probabilities.
   - The shares will be bias-corrected with the hand-labelled confusion matrix.
   - Each estimate will come with an uncertainty range.
3. **Non-image data** for what imagery cannot show: population (WorldPop, GHS-POP), night
   lights, points of interest, and potentially building-permission records.
4. **Conversion to travel demand:** trip productions from residential floor space and
   population; trip attractions from non-residential floor space.
5. **A transport question to be decided.** There are two options:
   - demand–supply mismatch: where demand grew faster than transport capacity;
   - an econometric model of intensification as a function of accessibility.

**Open decisions:**
- the zone system: grid, GHMC wards, or Comprehensive Mobility Plan traffic analysis zones;
- which transport question to pursue.
