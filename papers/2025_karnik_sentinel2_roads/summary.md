# Sentinel-2 Roads Dataset: road masks for 7 Indian regions

**Paper:** Karnik, Pimpalkar, Panchagnula & Acharya (2025), *Data in Brief* 63, 112141.
[doi:10.1016/j.dib.2025.112141](https://doi.org/10.1016/j.dib.2025.112141) · open access
(CC BY-NC 4.0). Authors are from VNIT Nagpur, AISSMS Pune and **NRSC (ISRO), Hyderabad**.
**Data:** [zenodo.org/records/15765738](https://zenodo.org/records/15765738) (CC BY 4.0, about 3.6 GB)
**Full text:** [fulltext.txt](fulltext.txt), without figures

**Verdict:** an honest, modest dataset paper. **Low direct use for us.** Its masks are just
OpenStreetMap roads drawn onto Sentinel-2 images, which we can make for Hyderabad ourselves.
Its main value is **evidence**: it shows how hard roads are to see at 10 m, and why accuracy
is the wrong score.

---

## In one paragraph

The authors downloaded cloud-free Sentinel-2 images (10 m) of Bengaluru, Delhi, Lucknow,
Pune, Warangal, Nagpur and part of Gujarat. They drew OpenStreetMap roads onto them as
black-and-white masks (road = 1, not road = 0) and cut everything into 256 × 256 patches.
After removing bad patches by hand, 5,634 image–mask pairs remain. They then trained six
common segmentation networks on it. **Even the best one finds only about half the roads (F1
≈ 0.51)**, yet every model shows 99% "accuracy".

## What they did, step by step

| step | what they did |
|---|---|
| Images | Sentinel-2 L2A median composite from Google Earth Engine, clouds < 20%, bands **R, G, B, NIR** |
| Road masks | OpenStreetMap roads, rasterised on the same 10 m grid; roads under 2 pixels wide dropped |
| Tiles | 256 × 256 pixel patches; 10,640 made, **5,634 kept** after manual checking |
| Formats | TIF (with map coordinates), PNG, and an "enhanced" PNG (brightened and contrast-boosted) |
| Test | 6 networks (U-Net, Residual U-Net, DeepLabv3+, D-LinkNet, RSE-Net, CADUNet) on a random split: 3,605 train / 902 validation / 1,127 test patches |

## Results

| model | F1 on normal images | F1 on enhanced images | overall accuracy |
|---|---|---|---|
| U-Net | 0.42 | 0.43 | 99.3% |
| Residual U-Net | 0.46 | 0.46 | 99.3% |
| DeepLabv3+ | 0.45 | 0.47 | 99.1% |
| D-LinkNet | 0.49 | 0.49 | 99.5% |
| RSE-Net | 0.49 | 0.51 | 99.6% |
| CADUNet | 0.50 | **0.51** | 99.6% |

**Why is accuracy 99% while F1 is 0.5?** Roads cover less than 5% of each patch. A model that
says "no road" everywhere is already about 95% "accurate". F1 only looks at how well the
roads themselves are found, so it shows the real picture. The authors say this clearly,
unlike the [Katpadi paper](../2025_jagannathan_katpadi_irunet/summary.md).

## Can we trust it?

Mostly yes. The numbers are consistent, modest and honestly explained. Small caveats:
- **Random split:** neighbouring patches from the same city sit in both training and test, so
  the scores are slightly optimistic.
- **The labels are OpenStreetMap,** so roads that OSM missed count as "wrong" even when the
  model finds them.
- **Only main roads:** narrow lanes are invisible at 10 m and were removed.
- **The "enhanced images help" claim is small** (0 to +0.02 F1, with no repeat runs), so it
  could be noise.

## How it is useful for us

| what | why it matters |
|---|---|
| **We don't need its data** | Roads are not one of our 5 classes. Our hand labels give a road the use on both sides and flag it with `is_road`. For transport, we take the road network straight from OpenStreetMap (`prox/roads_major_2023.gpkg`), which is far better than detecting roads from images (F1 ≈ 0.5). Hyderabad isn't in the dataset either; the nearest region is Warangal. |
| **Evidence that 10 m is coarse** | Roads 1–2 pixels wide are half-missed by the best networks. That matches our own finding that buildings are only 1.5–2 pixels wide, which is part of why non-residential land is hard (F1 0.41). It supports adding building data (Open Buildings 2.5D) instead of relying on imagery alone. |
| **Supports our choice of macro-F1** | It's a clean, citable example of accuracy looking great (99%) while the class you care about is found only half the time. That's the same reason we report macro-F1, not accuracy. |
| **A possible extra feature** | Road density within our 70–610 m windows, computed from OSM, could help separate busy commercial strips from quiet housing. Caution: DATA.md notes our distance-to-road features mostly helped the model memorise *where* labelled estates are. Any road feature must be tested on the hand labels, not just spatial CV. |
| **Image "enhancement" is irrelevant for LightGBM** | Brightening and contrast boosting make pictures easier for a CNN to read. Our tree model splits on raw values, so a simple brightness rescale changes nothing. |
| **A contact** | One author is at NRSC Hyderabad, the same organisation behind the SIS-DP land-use map we already compare against. |

## Words you may not know

- **Binary mask:** an image where each pixel is 1 (road) or 0 (not road).
- **Patch / tile:** a small square cut from a big satellite scene so a network can handle it.
- **Precision / recall / F1:** precision = of the pixels called road, how many really are;
  recall = of the real road pixels, how many were found; F1 = a balance of the two.
- **Class imbalance:** one class is far rarer than the others (here roads < 5%), which makes
  accuracy misleading.
- **CLAHE / gamma correction:** ways to brighten dark areas and boost local contrast in a picture.
