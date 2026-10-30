# IRUNet: multi-year land use in Katpadi (Vellore) with a deep-learning model

**Paper:** Jagannathan, Vadivel & Divya (2025), *Scientific Reports* 15.
[doi:10.1038/s41598-025-12512-7](https://doi.org/10.1038/s41598-025-12512-7) · open access (CC BY 4.0)
**Full text:** [fulltext.txt](fulltext.txt), without figures or tables

**Verdict:** weak paper. It doesn't change our approach. It is useful as an example of
**how not to evaluate** a land-use model.

---

## In one paragraph

The authors labelled Sentinel-2 satellite images of Katpadi (near VIT, Tamil Nadu) by hand
for each year from 2017 to 2024. They trained an image-segmentation network called
**IRUNet** to colour every pixel by land type. IRUNet is a U-Net with an InceptionResNetV2
"eye", pretrained on everyday photos (ImageNet). They report **98% accuracy**, better than
the plain U-Net, ResUNet and Attention-UNet. Comparing the yearly maps, they say built-up
area grew about 10% and mostly replaced farmland.

## What they did, step by step

| step | what they did |
|---|---|
| Data | Sentinel-2 images (10 m), March–May each year, 2017–2024, from Bhuvan and Google Earth Engine |
| Labels | Drawn by hand in QGIS, checked with some field visits |
| Input to model | 256 × 256 pixel patches, **3 bands only (RGB)** |
| Model | U-Net decoder plus InceptionResNetV2 encoder (ImageNet weights) |
| Trick | **Test-time augmentation (TTA):** predict on the original, horizontally flipped and vertically flipped patch, then average |
| Training | Dice + cross-entropy loss, learning rate 1e-4, batch 16, 150 epochs |
| Test | **Random** 80 / 10 / 10 split of patches |
| Time | Each year is classified separately. The time series is not used. |

**Reported scores:** accuracy 98.21%, Dice 0.89, precision 0.947, recall 0.892, F1 0.919,
kappa 0.872.

## Why we don't trust the numbers

1. **The numbers contradict each other.** The abstract says 98.21% accuracy. The results
   section gives the same model 89.19%, and elsewhere says "96.74% → 96.91%". Dice and IoU
   are both reported as exactly 0.8896.
2. **The class list keeps changing.** It starts with 8 classes (Urban, Road, Agriculture, …).
   Later it lists *snow/ice, clouds, rangeland, flooded vegetation, no data*. That is exactly
   the class list of the **Esri / Impact Observatory** map
   ([see the other summary](../2022_esri_io_lulc_india/summary.md)). Snow is impossible in
   Vellore. So the maps (and maybe the labels) likely come from Esri's product, not from the
   authors' own model.
3. **The model as described can't do 8 classes.** Its output layer is one sigmoid channel,
   which can only answer yes/no. They also claim to use NIR and SWIR bands, but the input is
   RGB only.
4. **Copy-paste from a medical paper.** It mentions "polyp area segmentation" and "clinical
   investigations".
5. **A random split inflates scores.** Neighbouring patches from the same scene land in both
   training and test, so the model is partly tested on places it has already seen.
6. **Accuracy hides weak classes.** No per-class scores are given. Accuracy looks good when
   one big class dominates.
7. **Change results are unchecked.** The "+10% built-up" figure was never validated.

## How it is useful for us

| what | why it matters |
|---|---|
| **A citation for our evaluation design** | It shows why we use 12 km spatial blocks and an independent hand-labelled test (Olofsson-weighted). Our own scores drop from 0.90 on easy labels to 0.62 on hand labels. Papers like this, with random splits and no independent test, report 98%. |
| **No threat to our model choice** | We found LightGBM + building features beats a U-Net (0.62 vs 0.50 macro-F1 on hand labels). This paper only compares CNNs with other CNNs, so it says nothing against that. |
| **Supports our caution on change maps** | They report year-to-year class change without checking it. We found that pixel-level class change is mostly noise, so we use building height and floor space for change instead. |
| **TTA (flip-averaging)** | Cheap to try on our U-Net comparison. It does **nothing** for LightGBM: our features (pixel values and window averages) are the same when the image is flipped. The LightGBM equivalents are averaging several random seeds or smoothing the probability map. |
| **Their dataset** (IEEE Dataport, [doi:10.21227/ev8p-r080](https://doi.org/10.21227/ev8p-r080)) | Probably not worth using. It covers a small area far from Hyderabad, has no residential vs non-residential split, and its labels may come from Esri's map. |

## Words you may not know

- **Segmentation:** giving a class to every pixel of an image, not one label for the whole image.
- **U-Net:** a common segmentation network. It shrinks the image to understand it, then
  grows it back to full size to draw the map.
- **Encoder / pretrained on ImageNet:** the "understanding" half of the network, first trained
  on millions of ordinary photos, then fine-tuned on satellite images.
- **Dice / IoU:** overlap scores between the predicted map and the true map (1 = perfect).
- **Random vs spatial split:** a random split mixes neighbouring pixels into training and
  test. A spatial split keeps whole areas apart, which is a fairer test.
