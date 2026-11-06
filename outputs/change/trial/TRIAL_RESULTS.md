# Trial run: booth-level population and land-use change (binary logit)

*5 Nov 2026. Region: 3 assembly constituencies (Maheshwaram, Rajendranagar, Serilingampally). Code:
`scripts/change/01_form20_ocr.py`, `02_trial_data.py`, `03_trial_logit.py`. Full tables: `coefs.csv`,
`fit.csv`, `checks.csv`, `rates.csv` in this folder.*

## Answer in short

1. **Yes, there is a correlation.** Undeveloped land in the most populated fifth of the region (by 2018
   votes per km²) developed **10–15 times** more often than land in the least populated fifth.
2. **But it is almost all shared with the built-up neighbourhood and road density.** Once those are in
   the model, booth population adds nothing measurable: pooled coefficient +0.03, p = 0.76. WorldPop adds
   a little in 2017–20 only.
3. **The factors that matter, in order:** built share within 1 km, start class (open land converts,
   trees much less), distance to HITEC City / Financial District, distance to the airport, road km in the
   4 × 4 km window, then distance to major roads and the ORR. Metro distance is not significant here.
   The model separates changers well: cross-validated AUC 0.80.
4. **This is not yet a fair test of the voter data.** The booth locations are approximate (§5), and
   location error biases the voter effect towards zero. The trial shows the pipeline works and what the
   data can and can't show; it doesn't settle whether voter counts beat WorldPop.

## 1. Data

| | |
|---|---|
| Region | 20 m cells inside HMDA whose nearest 2017 polling station is in AC 50, 51 or 52: **1,164 km²** (Maheshwaram 700, Rajendranagar 344, Serilingampally 120) |
| Periods | 2017 → 2020 and 2020 → 2023 (final 20 m maps) |
| At risk | cells undeveloped at the start: map trees/open and Open Buildings cover < 5% (2.3 M cells) |
| Change = 1 | map built at the end **and** Open Buildings new building (cover ≥ 20%, 3×3 gain ≥ 0.10): 8,048 and 8,363 cells, **0.35–0.37% of undeveloped land per 3 years** |
| Change = 0 | still undeveloped by both sources. Cells where the two disagree (10–13%) are left out. |
| Sample | **20,000 cells**: per period all changers at one per 200 m block (about 1,500) plus about 8,500 non-changers. The constant is corrected for the choice-based sampling (King & Zeng); standard errors are clustered by 4 km tile. |
| Booth population | **total votes polled per booth, 2018 assembly election** (Form 20, CEO Telangana), by OCR: 1,479 booths, 759k votes. Form 20 has no electors per booth; votes polled counts residents who turned out, so roll entries of people who moved away drop out. |
| Booth locations | 2017 polling-station coordinates (scrape of ECI's locator, April 2017). 2018 booths are placed by their position in the booth sequence (§5). Surface: kernel density of votes, σ = 1 km (2 km in a check). |
| Other factors | all at the start year: distances to airport, nearest ORR interchange, nearest open metro station, HITEC/FD, old CBD, nearest major road; all-road km in the 4 × 4 km window (dated OSM); built share in 1 km (map); WorldPop per km²; AC dummies |

## 2. The raw correlation

Share of undeveloped land that developed in the period (%), by fifth of the region's sample:

| fifth | votes per km² (median) | 2017–20 | 2020–23 | | WorldPop per km² (median) | 2017–20 | 2020–23 |
|---|---|---|---|---|---|---|---|
| Q1 (least) | 28 | 0.09 | 0.18 | | 134–143 | 0.02 | 0.05 |
| Q2 | 86 | 0.13 | 0.18 | | 200–203 | 0.08 | 0.15 |
| Q3 | 154 | 0.20 | 0.23 | | 338–345 | 0.22 | 0.29 |
| Q4 | 305 | 0.50 | 0.60 | | 1,126–1,147 | 0.64 | 0.65 |
| Q5 (most) | 1,200 | **1.27** | **1.23** | | 3,218–3,417 | **1.39** | **1.26** |

Alone, ln(votes density) has a coefficient of 0.60 (odds × 2.4 per SD, p < 0.001, AUC 0.73). WorldPop
alone is stronger (odds × 2.8 per SD, AUC 0.78).

## 3. Does population add anything beyond location and the neighbourhood?

| model | 2017–20 AUC (cv) | 2020–23 AUC (cv) | pooled McFadden R² | pooled LR test vs M0 |
|---|---|---|---|---|
| M0 base (distances, roads, built share, start class, AC) | 0.819 | 0.797 | 0.192 | |
| M1 + votes | 0.819 | 0.794 | 0.192 | p = 0.27 |
| M2 + WorldPop | 0.822 | 0.796 | 0.193 | p < 0.001 (2017–20 only) |
| M3 + both | 0.822 | 0.793 | 0.193 | |
| votes only | 0.761 | 0.709 | 0.098 | |

**Why population drops out:** ln(votes) is correlated 0.65 with built share in 1 km and 0.72 with road km
in 4 km. WorldPop is even more so (0.84, 0.88), partly because WorldPop is itself modelled from built-up
area and roads. At this scale, "many people nearby" mostly means "next to the existing city", and that
is already in the model.

## 4. What drives change: base model, pooled (M0)

| factor | coefficient | p | in words |
|---|---|---|---|
| built share in 1 km | +1.81 | < 0.001 | +10 points of built share nearby → odds × 1.20. **Strongest factor** (odds × 1.56 per SD). |
| start class trees (vs open) | −1.37 | < 0.001 | tree-covered land develops at a quarter of the odds of open land |
| ln distance to HITEC / Financial District | −0.43 | 0.001 | twice as far → odds × 0.74 |
| ln distance to airport | −0.39 | < 0.001 | twice as far → odds × 0.76 |
| road km in 4 × 4 km (per 100 km) | +0.42 | 0.003 | +100 km of road in the 16 km² window → odds × 1.53 |
| ln distance to major road | −0.16 | 0.025 | twice as far → odds × 0.89 |
| ln distance to ORR interchange | −0.17 | 0.06 | twice as far → odds × 0.89. Significant in 2020–23 (p = 0.04), not in 2017–20. |
| ln distance to metro | −0.09 | 0.58 | not significant: almost all of this region is far from the metro |
| period 2020–23 | −0.08 | 0.48 | same overall rate in both periods |

The signs and sizes are similar in the two periods, except the non-significant metro term. Built share
matters more in 2020–23 (+2.09 vs +1.55). The full per-period tables are in `coefs.csv`.

## 5. Why this is not yet a fair test of the voter data

- **Booth locations are approximate.** The booth list was renumbered between April 2017 (the only
  coordinate list available) and December 2018: Rajendranagar went from 317 to 441 booths, Maheshwaram
  from 301 to 460, Serilingampally from 400 to 580. No 2018 list with booth names is openly available
  (the rolls sit behind a captcha). So 2018 booth *k* is placed at 2017 booth *k × N₂₀₁₇ / N₂₀₁₈*.
  In 2017, booths 5 numbers apart are typically **1.4–3 km** apart, because the numbering jumps between
  localities. So even a small slip moves votes to the wrong neighbourhood. That kind of noise pushes the
  coefficient towards zero.
- Shifting the alignment by ±10 booths gives coefficients of +0.03 and −0.01, both non-significant. The
  result doesn't depend on the exact alignment, but all three versions share the same noise.
- With a 2 km kernel, which is more forgiving of location error, votes become significant (+0.29,
  p = 0.02). That is consistent with the signal being blurred rather than absent.
- **Edge effect:** only these three ACs' booths are counted, so density is too low near the region edge.
  Dropping cells within 1.5 km of a neighbouring AC's booth doesn't change the result.
- **Timing:** for 2017–20 the 2018 votes fall in the middle of the period. 2020–23 is clean (population
  measured before the period), and votes are also null there (p = 0.63).
- **Change definition** still awaits the eyeball check of the 60 cells (`EYEBALL_GUIDE.md`).

## 6. What would make the voter test conclusive

1. **The 2018 polling-station list with names and addresses** (one PDF per AC) from CEO Telangana or the
   district election office, through Prof. Eluru or an RTI. Booths could then be matched by building to
   the 2017 coordinates, which removes the guesswork. This is the single most useful item.
2. **More ACs.** Three ACs give little variation between areas. The OCR handles a sheet in 2–7 minutes.
3. **Growth instead of level.** The 2023 Form 20 sheets are downloaded. Votes growth 2018 → 2023 is
   endogenous for 2020–23 change, but it is the natural lagged predictor for a later period, and it is
   the variable most likely to carry information that the built-up share doesn't.

## 7. Compute

Building the sample takes about 1 minute per period (mostly reading the dated OSM roads); the 18 models
plus cross-validation take under a minute. OCR of one constituency's Form 20 takes 2–7 minutes. None of
this needs an overnight run.
