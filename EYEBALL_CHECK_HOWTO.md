# How to do the eyeball check (about 1 hour)

## Why it matters

Our map often says "this open land became built", while Google's Open Buildings shows no new building there.
This check decides who is right, and so which change rule the model uses:

- strict rule: 0.23% of open land changes per 3 years;
- persistence rule: about 1.4%;
- something in between.

You look at 60 small squares in old satellite images and write down what really happened in each one.
The answer decides the final change model.

---

## 1. Before you start (5 minutes)

1. **Install Google Earth Pro** for desktop (free; search "Google Earth Pro download"). Use the desktop
   program, not the web version: only the desktop one has old images.
2. **Find the three files** in `data/processed/change/`:

| file | what it is |
|---|---|
| `eyeball_points.kml` | the 60 squares, named E01 to E60 |
| `eyeball_form.csv` | the form you fill in |
| `eyeball_key.csv` | the answers. **Do not open it.** If you know which square is which, your labels get biased and the check is worthless |

3. **Open the form** `eyeball_form.csv` in Excel or Google Sheets. It has the columns
   `id, lat, lon, period, label, notes`.
   - You fill in only `label` and `notes`.
   - Don't change the other columns.
4. **Open the squares:** in Google Earth Pro, File → Open → `eyeball_points.kml`. On the left, under
   "Places", a folder appears with E01 … E60.
5. **Arrange the windows** so you can see Google Earth and the form side by side.

---

## 2. For each square (about 1 minute each)

**Step 1. Go to it.**
- Double-click E01 in the Places list. Google Earth flies there.
- You'll see a small **yellow square**. It is 20 m × 20 m, about the size of one house plot.
- Zoom so the square is clearly visible: an eye altitude of about 150–300 m (shown at the bottom right).

**Step 2. Check the period.** Look at the `period` column in the form for this id: **2017-2020** or
**2020-2023**. Clicking the square also shows it.

**Step 3. Open the old images.**
- Click the **clock icon** in the top toolbar (View → Historical Imagery). A time slider appears.
- Slide to an image **near the start year**, e.g. 2017 for 2017-2020. Pick a clear one with no clouds;
  January–May images are best (dry season).
- Then slide to an image **near the end year**, e.g. 2020. Again pick a clear one.
- Flip between the two a few times.

**Step 4. Decide what happened inside the square.**
- Judge what is **inside or touching** the yellow square.
- Our map can be off by about 10 m, so a building just touching the edge counts.
- Use the area around it (about 100 m) only for context, e.g. to see that a layout is being built.

**Step 5. Write one letter** in the `label` column, using the decision list below. Then write in `notes`:
- the two image dates, e.g. `3/2017 vs 2/2020`;
- how sure you are: `conf=1` (sure), `conf=2` (fairly sure), `conf=3` (guess);
- optionally, a few words, e.g. `layout with roads, no houses`.

---

## 3. Decision list: go down it and stop at the first "yes"

| ask yourself | if yes, write |
|---|---|
| No usable image near one of the two years, or clouds? | **U** (can't tell) |
| Was there already a building, road or paved yard **at the start**? | **X** (already built) |
| Is there a **new building** at the end: house, shed, warehouse, poultry farm, compound with a roof? | **B** (building) |
| Is the ground **cleared and levelled for building**: foundations, machinery, heaps of material, bare scraped soil? | **C** (construction site) |
| New **plot layout**: a grid of new internal roads, boundary stones, compound walls, but **no houses yet**? | **L** (layout / venture) |
| New **road, paved yard or parking**, but nothing else? | **R** (road / paving) |
| **Solar panels, greenhouse or polyhouse**? | **S** (solar / greenhouse) |
| **Quarry, mining, brick kiln, dumping or earth cutting**? | **Q** (quarry / dump) |
| None of the above: same fields or scrub, only the colour, crop, water or season differs | **N** (no real change) |

**Tricky cases:**

| what you see | label |
|---|---|
| Field green in one image, brown in the other | **N** (season) |
| Trees cut down, but the ground is not levelled and nothing built | **N**, note `trees cut` |
| Layout roads drawn around the square, but the square itself is an empty plot | **L**: a plot inside a layout counts |
| Compound wall built, nothing inside | **L** |
| Square half on a new house, half on open land | **B** (touching counts) |
| A big shadow or blur makes it unclear | pick your best guess and write `conf=3`, or **U** if you really can't tell |
| Already built in 2017 and still built | **X** |
| A temporary shed or tent that is gone in later images | **C**, note `temporary` |

**Aim for one letter per row.** Don't spend more than 2 minutes on one square: write your best guess with
`conf=3`, then move on.

---

## 4. When you're done

1. **Save the form as CSV** (File → Save As → CSV UTF-8), with the same name, in the same folder. Check that
   all 60 rows have a letter.
2. **Tell Claude "eyeball done".** Claude then:
   - opens the key and scores your labels. There are three groups of squares, mixed so you can't tell them
     apart:
     - **40 "map-only"** squares: our map says built, Open Buildings says nothing. **These are the question.**
     - **10 "confirmed"** squares: both sources say built. These should mostly come out B, which checks your
       eye.
     - **10 "stable"** squares: both say nothing happened. These should mostly come out N.
   - works out the share of map-only squares that are real change (B, C, L, R, S, Q) vs noise (N);
   - chooses the change rule from that:

| what you find in the map-only squares | what the model will use |
|---|---|
| mostly **B, C or L** (real change that Open Buildings missed) | the **persistence rule** (about 1.4% per 3 years); maybe "layout" as its own outcome if L is common |
| mostly **N** (noise) | the **middle rule**: our map plus at least a small gain in Open Buildings (about 0.5%) |
| many **S or Q** | treat them as non-urban change and leave them out of "development" |

3. Claude reruns the model with the chosen rule (about 20 minutes) and writes up the final table for sir.

**Time:** 60 squares × about 1 minute, so about an hour. Take a break halfway if you need one: the form saves
your place.
