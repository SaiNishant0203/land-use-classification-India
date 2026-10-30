# Esri / Impact Observatory 10 m Land Use/Land Cover: India 2021

**Source:** [ArcGIS item 196281a3ee5b4296ad594d34db56e543](https://www.arcgis.com/home/item.html?id=196281a3ee5b4296ad594d34db56e543#overview)
(published by Esri India, January 2022, licence CC BY 4.0)
**Map service:** `https://livingatlas.esri.in/server/rest/services/Imagery/IN_S2_LULC_2021/MapServer`
**Method paper:** Karra, Kontgis et al. (2021), *"Global land use/land cover with Sentinel-2
and deep learning"*, IGARSS 2021. That paper is not saved here; this file summarises the
ArcGIS item.

**Verdict:** this is a ready-made **map**, not a research paper. It is worth adding as **one
more baseline** in our product comparison. Like the others, it can't separate residential
from non-residential land.

---

## In one paragraph

Esri, Impact Observatory and Microsoft trained one deep-learning model on **over 5 billion
hand-labelled Sentinel-2 pixels from more than 20,000 sites worldwide**. They ran it on many
dates of 2021 imagery and merged the results into one map. Every 10 m pixel of India gets one
of 9 land-**cover** classes. This layer is the India cut of that global map.

## Key facts

| item | value |
|---|---|
| Year | 2021 (this layer). Global versions exist for other years too. |
| Resolution | 10 m |
| Input | Sentinel-2, 6 bands: blue, green, red, NIR, SWIR1, SWIR2 |
| Model | Deep-learning segmentation model, run on several dates and then composited |
| Training labels | National Geographic / Dynamic World hand-labelled dataset |
| Compute | Microsoft Planetary Computer + Azure Batch |

## The 9 classes (and how they map to ours)

| code | Esri class | what it means | our class |
|---|---|---|---|
| 1 | Water | water most of the year | 3 Water |
| 2 | Trees | tall (~15 m+), dense vegetation, plantations | 4 Forest / trees |
| 4 | Flooded vegetation | wetlands, **rice paddies** | 5 Other open |
| 5 | Crops | planted fields, fallow plots | 5 Other open |
| 7 | Built Area | houses, offices, roads, all hard surfaces | 1 **or** 2: can't tell which |
| 8 | Bare ground | rock, soil, mines, dry lake beds | 5 Other open |
| 9 | Snow/Ice | permanent snow | not used |
| 10 | Clouds | no data due to cloud | not used |
| 11 | Rangeland | grass, scrub, parks, lawns | 5 Other open |

(Codes 3 and 6 are not used.)

## How it is useful for us

1. **One more baseline for Test B.** We already score Dynamic World, ESA WorldCover and
   others on our 325 hand-labelled pixels. Esri's map belongs in the same table. Because
   "Built Area" lumps homes, offices and roads together, it can only be scored on water,
   trees, open and built-overall. That gap is what our model is for.
2. **A possible third vote for training labels.** Water, forest and open labels currently
   need ESA WorldCover and Dynamic World to agree. Esri could be a third vote. **Caveat:** it
   was trained on Dynamic World's labels, so it partly repeats Dynamic World and is not a
   fully independent opinion.
3. **A check on change over time.** The global version has yearly maps. Comparing how much
   its "Built Area" changes year to year against our noisy pixel-change maps would show
   whether the instability comes from us or affects every product.
4. **It explains the Katpadi paper.** Its odd class list (snow/ice, clouds, rangeland) is
   exactly this product's. See
   [the IRUNet summary](../2025_jagannathan_katpadi_irunet/summary.md).

## Limits to keep in mind

- **Land cover, not land use.** It shows what covers the ground (roofs, trees, water), not
  what the land is used for (homes vs shops vs factories). Transport planning needs land use.
- **This India layer is 2021 only.** Our model uses 2023, so expect some real differences
  from construction since then.
- **It is a map service built for viewing.** To get the raw pixels for our audit, the global
  dataset is also distributed through Google Earth Engine's community catalogue and Microsoft
  Planetary Computer. Check the current dataset IDs before downloading.

## Words you may not know

- **Land cover vs land use:** *cover* is what is physically there (concrete, grass). *Use* is
  what people do there (live, work, shop).
- **Composite:** combining many images from a year into one, so clouds and seasons average out.
- **Baseline:** an existing product we compare our model against.
