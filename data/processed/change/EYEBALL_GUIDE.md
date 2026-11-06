# Change eyeball check: how to label (about 1 hour)

**Purpose:** decide what counts as "change" in the change model (CHANGE_MODEL_PLAN.md §2).
**Code:** `scripts/change/00_eyeball_sample.py`

## Files
| file | use |
|---|---|
| `eyeball_points.kml` | open in **Google Earth Pro**: 60 yellow 20 m squares, E01–E60 |
| `eyeball_form.csv` | fill the `label` and `notes` columns |
| `eyeball_key.csv` | which group each cell is in. **Don't open it until you finish**, or the labels get biased |

The cells are shuffled. Some are map changes, and some are controls where we already know the answer.

## Steps for each cell
1. Double-click the cell in Google Earth Pro. Zoom so the square fills about a quarter of the screen.
2. Open the **historical imagery clock**. The cell's description says which period it belongs to (2017→2020 or 2020→2023).
3. Compare the clearest image **near the start year** with the clearest image **near the end year**.
   - Dry-season images (Jan–May) are best.
   - Write both image dates in `notes`, e.g. `3/2017 vs 2/2020`.
4. Choose **one** label, judging what is **inside or touching the square**:

| label | meaning |
|---|---|
| **B** | new building(s), including sheds, poultry farms and warehouses |
| **C** | construction site: cleared and levelled ground, foundations, machinery, material heaps |
| **L** | **plotted layout**: new internal roads, plot boundary stones or compound walls, but no houses yet |
| **R** | new road, paved yard, parking or other infrastructure |
| **S** | solar farm, greenhouse or polyhouse |
| **Q** | quarry, mining, brick kiln, dumping or earth cutting |
| **N** | **no real change**: same land, only crop, season, wetness or colour differs |
| **X** | already built or developed at the **start** (the map was wrong in the start year) |
| **U** | can't tell (no usable image near one of the years, or clouds) |

5. Optionally, add `conf=1/2/3` in notes (1 = sure).

## What happens next
**I compare your labels with the key.** The deciding number is the share of **map-only** cells that are B, C, L, R, S or Q (real change) rather than N (noise).

| share real | what the change model does |
|---|---|
| mostly N | use the strict definition: map change **and** Open Buildings confirmation |
| many L or C | add **"under development / layout"** as an outcome of its own |
| many S or Q | treat these as a separate, non-urban change type |

The control cells check you as a labeller:
- **Confirmed** cells should come out as B.
- **Stable** cells should come out as N.

The map-only cells are half to-res and half to-non-res. In the map itself, to-non-res is about four times more common. I re-weight for that when scoring.
