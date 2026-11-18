# New factors for the HMDA change model: what we tested (18 Nov 2026)

This is the plain-language summary of the new-factor tests. The model these factors were added to is described in
`DISCRETE_CHOICE_MODELS_REPORT.md` (Part 1). Full numbers and the commands to reproduce them are in `RESULTS.md`
in this folder.

## What we tried

We looked for new factors that could explain development better. They came from three research sweeps:

- the Florida report itself;
- studies of urban growth in Indian and Asian cities;
- what Hyderabad data can actually be obtained.

Then we tested the ones we could build quickly.

**How each factor was tested**

- **No peeking at the future.** Every factor is measured at or before the start of its period:
  - 2016 / 2019 satellite data;
  - 2017 polling stations;
  - roads as mapped at the start;
  - schools by founding year.
- **Added to the final model**, one at a time, under both change rules (strict and persistence).
- **Kept only if** all three hold:
  - it is significant;
  - it has the same sign in both periods;
  - it improves prediction on areas the model has not seen (AUC, cross-validated by 4 km tile) and from period 1 to
    period 2.

A ΔAUC of +0.001 to +0.005 is typical for one good factor here. The existing access, terrain and census groups each
add about that much.

## Results

| New factor | Strict: coef (t) | Persistence: coef (t) | ΔAUC (strict / pers.) | Verdict |
|---|---|---|---|---|
| **Road network** (OSM as mapped at the start of each period) | | | | |
| **Travel time on the road network** to the old CBD and ORR, in place of straight-line distance | ρ² 0.2360 → 0.2375 | ρ² 0.2922 → 0.2947 | +0.0009 / +0.0006 | **Keep**: better on every measure, same number of factors |
| Travel time to HITEC / Financial District | not sig. | −0.18 (−2.9) | 0 / 0 | Drop |
| **Momentum** | | | | |
| **Recent building nearby**: % of the 1 km area that changed in 2017–20 (period 2 only) | +0.20 (6.2) | +0.02 (2.7) | +0.0045 / +0.0002 | **Keep**: biggest single gain (strict) |
| **Villages** (2017 polling stations, UDISE schools by founding year) | | | | |
| **Distance to the village core** (nearest government school) | +0.25 (5.0) | −0.46 (−13.0) | +0.0007 / +0.0018 | Keep, read carefully: sign flips between rules |
| Distance to the nearest polling station | +0.41 (8.6) | −0.25 (−8.2) | +0.0024 / 0.0000 | Same flip |
| **Polling stations within 1 km** (settlement density) | −0.026 (−7.3) | −0.017 (−5.8) | +0.0012 / +0.0007 | **Keep** |
| **Satellite** (year before the period; random ~17,600-cell subsample per rule; with a Dynamic World "built" control) | | | | |
| **Bare-ground probability** (Dynamic World) | +5.2 (5.6) | +4.2 (5.5) | +0.0023 / +0.0006 | **Keep**: barren land gets built |
| **How actively the land is cropped** (yearly greenness range, Sentinel-2) | −2.0 (−5.9) | −0.6 (−2.3) | +0.0017 / +0.0001 | **Keep**: cropped land doesn't |
| **Height above the nearest drain** (flood exposure; Florida's flood-zone factor) | +0.09 (2.1) | +0.24 (7.3) | +0.0006 / +0.0009 | Keep, weak: low-lying land is built less |
| Cropland probability | −1.6 (−3.6) | −1.6 (−4.9) | +0.0012 / +0.0007 | Weak: overlaps cropping intensity |
| Scrub, grass, dry-season greenness, water history | small or unstable | small or unstable | ≈ 0 | Drop |
| **Other** | | | | |
| OSM shops / amenities within 1 km | −0.27 (−4.6) | −0.18 (−3.9) | +0.0010 / +0.0001 | Drop: OSM coverage is uneven |
| Schools and private schools nearby, new private schools, OSM school / clinic distance, inside the ORR | not sig. | not sig. | ≈ 0 | Drop |

**All the kept non-satellite factors together:**

- strict rule: Δρ² +0.006, ΔAUC +0.003;
- strict rule, adding recent building nearby in period 2: Δρ² +0.011, ΔAUC +0.007.

They are useful for explanation but add little to prediction, as with every factor group so far.

## What we learned about the open question (strict or persistence?)

Three separate checks point the same way: the extra changes that only the persistence rule counts are not like the
confirmed ones.

- **Near villages.** Confirmed (strict) changes happen *away* from village cores, as new layouts on open land.
  Persistence-only changes happen *near* village cores. Two independent sources agree: polling stations and
  government schools.
- **Already partly built.** Dynamic World's "built" probability a year *before* the period predicts change. The
  effect is far larger under persistence (t 32, ΔAUC +0.067) than under strict (t 14, +0.023). Many persistence
  changes may not have been open land at the start.
- **Odd signs.** Under persistence, steeper land and land farther from the city get built more. Both effects come
  entirely from changes that Open Buildings does not see.

**Proposed rule.** Apply the two-year logic at both ends of the period:

- open in t0 **and** t0−1, with Dynamic World "built" probability low in t0−1;
- built in both of the last two years.

This should remove the start-of-period map errors and keep a realistic rate (about 1% a year). The eyeball check
should focus on map-only squares near villages, and on squares that already look partly built in the first image.

## Also found

- **The right Florida table.** We followed Table 18 of the Florida report (Eluru et al. 2025, FDOT BED26-977-02).
  Table 18 is for *single-family residential* parcels (§7.2).
  - The closer match to "open land gets built on" is **Table 94 (vacant residential)**, with Table 78 (vacant
    commercial) and Table 30 (agricultural).
  - Their strongest factor everywhere is parcel size, which we don't have yet. The nearest substitute is the size of
    the open patch a cell sits in.
- **Other conversions.**
  - **Open → residential vs non-residential:** possible only if a hand check shows the map gets these right.
  - **Residential ↔ non-residential:** not credible with our maps (macro-F1 0.65). Most of that "change" would be the
    two classes being confused.
  - A safer next model is built share per 100–500 m block (Florida's fractional split).

## Next steps

1. **Do the eyeball check** (about an hour) and pick the change rule. Also try the proposed rule.
2. **Update the final model:**
   - network travel time instead of straight-line distance;
   - add recent building nearby × period 2, settlement density, bare-ground probability, cropping intensity and
     height above drainage;
   - move the zoning dummies into the main specification.

   The satellite factors first need a full-HMDA Earth Engine export (they were only fetched for a subsample).
   Then rerun once with the chosen rule.
3. **Fit the Table 94 version**, and build open-patch size once the full maps are available.
4. **Request data through Prof. Eluru:** HMDA layout approvals with dates, and the 2013 land guideline values. These
   are the strongest missing factors, and they sit behind captchas or have no public archive.
