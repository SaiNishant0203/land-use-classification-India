# Papers and products we have read

Each folder has a short `summary.md` covering what the source is, what it did, whether to
trust it, and **how it is useful for our Hyderabad land-use project**. The summaries are
written for beginners.

| folder | what it is | one-line takeaway |
|---|---|---|
| [2025_jagannathan_katpadi_irunet](2025_jagannathan_katpadi_irunet/summary.md) | Paper: deep-learning (U-Net) land-use maps of Katpadi, 2017–2024 | Claims 98% accuracy, but the numbers contradict each other and it uses a random test split. Useful only as an example of why we test the way we do. |
| [2025_karnik_sentinel2_roads](2025_karnik_sentinel2_roads/summary.md) | Dataset paper: 5,634 Sentinel-2 patches with OpenStreetMap road masks, 7 Indian regions | Honest and modest: the best networks find only about half the roads at 10 m (F1 ≈ 0.51) despite 99% "accuracy". We don't need the data. It's useful as evidence for using macro-F1 and building data. |
| [2022_esri_io_lulc_india](2022_esri_io_lulc_india/summary.md) | Product: Esri / Impact Observatory 10 m land-cover map of India, 2021 | A good extra baseline to compare against. Like the other products, it can't separate residential from non-residential land. |

## Adding a new one

1. Make a folder `YEAR_firstauthor_shortname/`.
2. Add `summary.md`, following the existing ones: a verdict line, *In one paragraph*, what
   they did, how far to trust it, *How it is useful for us*, *Words you may not know*.
3. If the source is open access (e.g. CC BY), save the full text or PDF next to it.
4. Add a row to the table above.
