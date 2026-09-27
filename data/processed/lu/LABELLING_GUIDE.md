# Labelling guide: Hyderabad land-use validation pixels

325 pixels, each a 10 m × 10 m square. **Test set only. It is never used for training.**
This set is what every model and product (ours, WRI, Industrial Land, GULU, GHS, Dynamic World)
gets scored against, so apply the same rules every time. Expect about 30 s per pixel,
roughly 3 hours in total. Doing it in 2–3 sittings is fine.

## Classes

| code | class | includes |
|---|---|---|
| 1 | **Residential** | houses, apartments, gated communities, informal housing, village settlements |
| 2 | **Non-residential built** | shops, markets, malls, offices, IT parks, factories, warehouses, schools, colleges, hospitals, government, temples/mosques/churches, bus depots |
| 3 | **Water** | lakes, tanks, rivers, reservoirs *with water in 2023* |
| 4 | **Forest / trees** | continuous tree canopy **outside** any compound: forest, tree-covered parks, hill scrub-forest |
| 5 | **Other open** | farmland, barren, rock, grass, vacant plots, dry tank beds, open construction ground |

## The one rule that matters

**Label the USE of the plot or compound the square falls in, not what the surface looks like.**

- Lawn, pool or parking *inside* an apartment complex → **1**
- Parking lot, lawn or open yard *inside* an IT campus, factory or college wall → **2**
- Trees inside a residential colony → **1**, not 4
- Vacant plot in a layout with no building on it → **5** (write `vacant layout` in notes)

## Edge cases

- **Mixed use** (shops below, homes above): pick the dominant use of *that building*.
  A main-road shopping frontage → 2; a residential lane with a small shop → 1.
- **Roads:** give the road the use that dominates both sides and tick `is_road`.
  Roads can then be handled separately later.
- **Construction:** if the building type is already clear (apartment towers vs office
  block), label it and write `under construction`. Otherwise use 5.
- **Military / cantonment:** barracks and housing → 1, offices and depots → 2,
  open ground → 5, forest → 4.
- **Square straddles two uses:** take whichever covers more than half the square.
- **Not sure:** still pick a class, but set `confidence` = 3 and explain in `notes`.
  Guesses are fine as long as they are marked.

`confidence`: 1 = sure, 2 = probably, 3 = guess.

## Year

Labels are for **2023**. If you can see the place changed after 2023 (e.g. farmland in the
2023 Google Earth image, towers today), label the 2023 state and write `changed after 2023`.

## Tools

**QGIS (recommended):**
1. Open `validation_points.gpkg`. The dropdowns and colours load automatically.
2. Add imagery: Browser panel → XYZ Tiles → New connection:
   `https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}` (Google Satellite)
   or Esri World Imagery.
3. Toggle editing (pencil icon), open the attribute table, select a row, press `Ctrl+J`
   to zoom to it, then fill in `true_class`, `confidence`, `is_road` and `notes`.
   The square's outline changes colour once it has a label.
4. Save edits often (`Ctrl+S`).

**Google Earth Pro, to check the date:** open `validation_points.kml` and use the clock
icon (historical imagery) to see 2023. Google Maps labels and Street View help with
deciding use (is that a hospital or an apartment?).

Which layer each point was drawn from is kept in a separate file (`validation_key.csv`)
so it can't bias the labels. Don't open that file until labelling is finished.
