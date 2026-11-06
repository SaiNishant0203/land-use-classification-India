# Land-Use Change Model (Discrete Choice): Plan

**Date:** 2 November 2026
**Basis:** Prof. Eluru's reference report (UCF/FDOT *Final Report*, §6–7: Figure 12 framework and Table 18 binary logit), our 20 m year maps (`outputs/lu20/maps/`), and the earlier 10 m choice models (`CHOICE_MODEL_RESULTS.md`).

---

## 1. What the reference model does, and our version of it

**The Florida model (Figure 12)** runs four steps for each parcel, separately for each current land-use type:

1. **Binary logit:** does the parcel change between t−1 and t? (Table 18)
2. **Binary logit:** full or partial conversion? (Table 19)
3. **Fractional split:** if partial, what fraction changes? (Table 20)
4. **MNL:** what is the new land-use type? (Table 21)

All inputs are measured at **t−1**. Table 18 uses these kinds of variables:
- socio-demographics (% Hispanic, % zero-vehicle households);
- job density;
- parcel size;
- block-group land-use shares;
- flood zone.

**Our version:**

| Florida | Hyderabad (ours) | note |
|---|---|---|
| parcel | 20 m pixel | We have no parcel data. GHMC property data may come through Prof. |
| annual steps | 2017→2020 and 2020→2023 (pooled with a period dummy) | 2017→2023 as a check |
| one model per current land use (18 types) | one model for **undeveloped** land (open + agriculture + trees, with a trees dummy) | See §2 for why built→built is left out |
| Step 1: change yes/no | **Step 1: undeveloped → developed, yes/no** (binary logit) | The main model |
| Steps 2–3: full/partial, fraction | Only meaningful for a unit bigger than a pixel | Option: 100 m block (25 pixels), where "partial" means 1–80% of the block converts. **Ask Prof.** |
| Step 4: new type (MNL) | **New type: residential vs non-residential** (binary/MNL) | Non-res map F1 is only 0.46, so step 4 is weaker than step 1 |

---

## 2. The decisive issue: what counts as "change"

**If we take "change" directly from the maps, most of the change pixels are classification noise.** This has to be fixed before any model runs.

**Where the maps' 3-year "change" comes from (share of all HMDA pixels):**

| transition | 2017→2020 | 2020→2023 | real? |
|---|---|---|---|
| total pixels changing class | 18.9% | 18.5% | real development is ~0.1% of open land per year (Open Buildings) |
| forest ↔ open | **12.7%** | **10.3%** | almost all greenness and season, not land conversion |
| open/forest → built | 3.0% | 3.0% | partly real |
| built → open/forest | 0.8% | 1.0% | almost never real; this is the noise floor |
| res ↔ non-res | 1.8% | 1.8% | mostly classifier uncertainty (non-res F1 0.46) |

**Check against Google Open Buildings (independent of our map),** on the 333,600-pixel panel:

| | 2017→2020 | 2020→2023 |
|---|---|---|
| undeveloped pixels the map calls built at period end | 3.5% | 3.6% |
| ...of these, a new building appears (Open Buildings cover < 5% → ≥ 20%) | **6%** | **6%** |
| ...of these, any building-cover gain ≥ 0.10 within 70 m | 11% | 10% |
| Open Buildings new buildings that the map also calls built | 74% | 78% |

**How to read this:**
- The map **finds** most real new development (high recall).
- But about **9 in 10 of its "changes" have no new building.**
- A logit fitted on raw map change would mostly be explaining noise: shadows, crop cycles, and the classifier's res/non-res uncertainty.

**Proposed definition (Step 1 dependent variable):**
- **change = 1** if the map says undeveloped → built **and** Open Buildings building cover rises (gain ≥ 0.10 within 70 m).
- **change = 0** if the map says undeveloped in both years **and** Open Buildings shows no gain.
- **Ambiguous pixels are dropped:** the map says change but Open Buildings doesn't, or the reverse. Robustness checks will put them back in.
- Thresholds are varied as in `outputs/dv_robustness.*`.
- **Open Buildings temporal runs 2016–2023, which is exactly our window.**

**One thing to check by eye first (~1 hour), because it is specific to India:**
- Some map-only "changes" may be real **plotted layouts** ("ventures"): farmland cleared, roads laid and plots marked, with houses coming years later.
- That is real land-use change, and often the *first* stage of urbanisation around Hyderabad, but Open Buildings would not see it.
- Plan: look at ~60 such pixels in Google Earth historical imagery.
- If many are layouts, add **"layout / under development"** as a third outcome (undeveloped → layout → built). This would be a genuinely Indian contribution.

---

## 3. Sample design (Prof.'s 15–20k pixels)

**Real conversions are rare** (~0.3% of undeveloped land per 3-year period). A plain random sample of 20k pixels would contain only about 60 events.

**Use choice-based (outcome-stratified) sampling,** standard in discrete choice:
- **Per period:** about 4,000 change pixels and 6,000 no-change pixels.
- **Two periods:** about 20,000 pixels in total.
- **Drawn from the full 20 m map,** not the 333k panel. Across HMDA there are about 14 million undeveloped pixels, so roughly 40k confirmed changers per period to draw from.
- **Minimum spacing of 200 m** between sampled pixels, to limit spatial autocorrelation.
- **Under choice-based sampling, logit slope coefficients stay consistent; only the constant shifts.** Correct the constant with the known population shares (Manski–Lerman / King–Zeng prior correction). Prof. will expect this.
- **Standard errors are clustered by 4 km tile.** Also report a period-specific model, to show stability.

---

## 4. Timing rule for the variables ("value or delta?")

| use | allowed? | why |
|---|---|---|
| **Level at the start of the period** (population 2017, road km 2017, ...) | yes, the default | It is known before the change happens |
| **Delta over the *previous* period** (e.g. Δpopulation 2017→20 used to explain change 2020→23) | yes | A lagged trend, still measured before the outcome |
| **Delta over the *same* period** (e.g. Δpopulation 2020→23 explaining change 2020→23) | **no** | It is partly the same event. New houses bring new people, so this is reverse causality |
| **Infrastructure that opened during the period** (a metro station in 2018) | only as a labelled "treatment" | Use the opening date and compare before and after |

The earlier work already follows this rule (`d_major_road_2017`, `d_metro_2017`).

---

## 5. Candidate factors

**Status key:**
- **HAVE** = already computed in the repo;
- **EASY** = up to about a day from data we have or public raster/vector data;
- **MEDIUM** = a few days (joining, geocoding);
- **HARD** = scraping, OCR or requests to an agency.

**Expected sign:** + means more likely to change.

### 5a. Prof.'s list

| factor | measure | source / status | expected sign, and the "why" |
|---|---|---|---|
| Population | level at t, lagged Δ | WorldPop 2017/2020: **HAVE**. GHS-POP 2020/2025: EASY. Voter rolls: see §8 | + Housing demand. **Caveat: WorldPop and GHS-POP are spread over built-up maps, so they partly encode the outcome (circular).** Voter rolls do not depend on imagery, which is why Prof.'s idea matters. |
| Distance to airport (RGIA) | km, ln | **HAVE** | Ambiguous. Earlier result: + for residential farther away (noise and height restrictions near the airport) |
| Road mileage in a 4 km × 4 km area | km of road in the window, total and by class | Geofabrik dated snapshots for 2017/2020/2023 are on disk (`data/raw/osm_snapshots/`): **EASY**, about 10 min of raster work | + Access. **Caveat: OSM mapping effort grew too** (4,441 → 5,251 km of major roads). Minor streets are often mapped *after* a layout is built, which makes them endogenous. Lead with major-road km, and report minor-road km separately. |
| ORR | distance to the nearest interchange | **HAVE** | + Most robust effect so far (−0.32 to −0.39 in every check) |
| Metro | distance to a station open at t | **HAVE** (opening dates in `prox/metro_stations_opening.csv`) | No robust effect so far. Keep it in, and also test the **opening** as an event (§6) |

### 5b. Indian-context factors (the Florida analogue is shown where one exists)

**Land use and neighbourhood** (Florida: block-group land-use shares, land-use mix)

| factor | source / status | why it might cause change |
|---|---|---|
| Shares of res, non-res, open, water and trees in 1 km and 4 km windows at t, plus land-use-mix entropy | our maps: **EASY** | Same as Table 18 |
| Building volume and height nearby at t (densification pressure) | Open Buildings temporal: **HAVE** (`bldg_h_61`, `cov_61`) | Growth spills over from dense areas |
| Distance to the contiguous built-up edge at t | our maps: **EASY** | Separates edge growth from leapfrog growth |
| Change in the neighbourhood during the previous period (spatial contagion) | our maps + Open Buildings: **EASY** (2020→23 model only) | Layouts and colonies spread outward from earlier ones |

**Supply constraints, i.e. land that cannot or may not be built on** (Florida: flood zone, conservation land)

| factor | source / status | why |
|---|---|---|
| Slope, elevation, rock outcrops | Copernicus DEM 30 m: **EASY** | Deccan granite boulders make building expensive |
| Lakes, including the **Full Tank Level (FTL) buffer**, and distance to nalas | OSM water + JRC: **EASY**. Official FTL maps from HMDA's lake protection committee: HARD | Building inside FTL and buffer zones is banned, but encroachment is common. That makes it a "why" question in itself |
| Reserved forest, defence/military land, airport land | OSM `landuse=military`, `boundary=protected_area`, forest blocks: **EASY** | Florida's conservation-land rule: exclude these, or add a dummy |
| Flood exposure | October 2020 flood extent from Sentinel-1 (EE): **MEDIUM** | Florida's flood zone A. Can be tested for the 2020→23 period |
| **GO 111 zone** (84 villages around Osman Sagar and Himayat Sagar; building restricted since 1996, **repealed April 2022** by GO 69) | village list + village boundaries: **MEDIUM** | **Natural experiment** (§6) |

**Institutions and policy (specific to India)**

| factor | source / status | why |
|---|---|---|
| Jurisdiction: GHMC, municipality/corporation, or gram panchayat. Several new municipal corporations were formed around the city in 2018–19 (Nizampet, Boduppal, Peerzadiguda, Badangpet, Bandlaguda Jagir, Meerpet, Jawaharnagar; *list to verify*) | OSM admin boundaries / datameet: **MEDIUM** | Different building-permission regimes and approval speed |
| Land market value: Telangana SRO guideline values per village, revised in 2013 and again in 2021–22 | registration.telangana.gov.in: **HARD** (scraping) | The price signal. This is the most direct economic "why" |
| HMDA master-plan zoning (MP 2031: residential, commercial, conservation, multiple use) | HMDA PDFs to georeference: **HARD** | Florida's "land-use plan designation" |
| State-led projects: HMDA land auctions (Kokapet/Neopolis 2021 and 2023, Budvel, ...), 2BHK housing colonies (e.g. Kollur), TSIIC industrial parks, SEZs, Pharma City | manual list with geocoding (~50 sites): **MEDIUM** | The state acts as a land developer; this is change not driven by the market |

**Socio-demographics** (Florida: race, zero-vehicle households)

| factor | source / status | why |
|---|---|---|
| Census 2011 village/ward PCA: % agricultural workers (cultivators + agricultural labourers), literacy, % SC/ST, 2011 density | censusindia.gov.in + SHRUG/datameet boundaries: **MEDIUM** | Baseline before the period. Agriculture-dependent villages may sell land or resist selling |
| Census 2011 houselisting: % of households with a car, % with a two-wheeler | same source: **MEDIUM** | **The closest analogue to Table 18's zero-vehicle households** |
| Voter-roll electors per polling booth (time-varying) | §8 | Population and growth independent of imagery |

**Economic activity** (Florida: job density)

| factor | source / status | why |
|---|---|---|
| Distance to employment centres (HITEC, Financial District, Gachibowli, Uppal, Pocharam, Adibatla aerospace SEZ, Genome Valley) | partly **HAVE**; the rest EASY | Job access |
| Network travel time to jobs on the start-year road graph | OSM snapshots: **MEDIUM** (planned in October, not yet done) | Fixes the HITEC / CBD / ORR collinearity |
| Night lights: level at t and lagged Δ | VIIRS: **HAVE** | Proxy for economic activity |
| Economic Census 2013 establishments and workers per village/ward | MoSPI: **MEDIUM** | Closest to job density |
| Radial highways (NH44, NH65, NH163, NH765), separate from the ORR | OSM: **EASY** | Freight and logistics corridors attract warehouses (non-res) |

### 5c. Proposed first specification (data in hand within about a week)
- Population (WorldPop at t, then voter rolls when ready);
- ln distance to the ORR interchange, airport, employment centre and metro;
- major-road km and minor-road km in the 4 km × 4 km window;
- neighbourhood land-use shares and land-use mix (1 km);
- distance to the built-up edge;
- night lights;
- slope;
- inside lake buffer, protected or military land;
- trees-at-start dummy;
- period dummy.

**Add GO 111, jurisdiction and Census 2011 as they arrive.**

---

## 6. From "what correlates" to "why"

A logit alone gives associations. Five things make the paper explanatory:

1. **Timing:** every X is measured before the outcome (§4).
2. **Mechanism groups:** report the effects grouped as
   - market pull (jobs, roads, ORR);
   - supply constraints (terrain, lakes, protected land, regulation);
   - neighbourhood contagion;
   - people.

   Then ask *which group explains most of the log-likelihood*, using likelihood-ratio tests or the drop in pseudo-R² when a group is removed.
3. **Natural experiments using our two periods:**
   - **GO 111 repeal (April 2022):** did conversion inside the 84 villages rise in 2020→23 relative to 2017→20, compared with similar villages just outside? A difference-in-differences inside the logit: period × inside-GO-111.
   - **Metro openings (November 2017 to February 2020):** station catchments before vs after opening.
   - **New municipalities (2018–19):** change in conversion after the change of jurisdiction.
   - **COVID (2020–21)** falls in period 2. The period dummy absorbs the overall slowdown.
4. **Latent segmentation** (already built; BIC preferred 3 segments: dormant, infill, growth corridor). It shows *different* causes in different land markets, which is Prof.'s own method.
5. **Stability across periods:** an effect found in both 2017→20 and 2020→23 is unlikely to be noise. Earlier, the ORR effect was −0.34 and −0.38.

---

## 7. Compute: choice models vs the deep-learning work

**Measured on this laptop** (`outputs/lu/logs/22_*.log`, `25_latent.log`, `scripts/lu20/run_all.py` log):

| job | data size | time |
|---|---|---|
| Binary logit + MNL + LightGBM spatial CV + SHAP + context models (whole suite) | 300,000 pixels | **1.5–2 min per period** |
| Latent segmentation, K = 1, 2, 3 | 300,000 pixels | **about 1 min** |
| LightGBM land-use classifier training | 20 m grids | 9 min |
| HMDA map prediction | 18 M pixels | 40 min |
| U-Net (Arc GPU) / retrain-across-seeds | | hours; overnight |

**For 15–20k pixels:**

| job | estimate |
|---|---|
| binary logit or MNL | under 1 second |
| bootstrap standard errors (500 reps) | a few minutes |
| latent segmentation (2–4 segments) | 1–5 minutes |
| mixed logit with simulated draws, if Prof. wants random parameters | 5–30 minutes |

**Verdict:**
- **No all-nighters for the models themselves.** Each run is seconds to minutes, can be done on battery, and is interactive.
- **The slow part is building the data, which happens once:**
  - Open Buildings and features for the new 20k sample (Earth Engine, about 1 min per chunk in restricted mode; maybe 1–2 hours);
  - road density and distance rasters (minutes);
  - voter rolls (see §8).
- **One overnight run for the first dataset build;** after that, everything is fast.

---

## 8. Voter rolls as a population source

Full report: [VOTER_DATA_FEASIBILITY.md](VOTER_DATA_FEASIBILITY.md). It was web research, checked on 2 November 2026; the report marks which facts were verified on a live page.

**What is available:**

| level | feasibility | source |
|---|---|---|
| **Assembly constituency (AC), about 29 over the HMDA core** | **easy, about 2 h** | CEO Telangana "Electors Summary" text PDFs: Dec 2018, Dec 2019, Oct 2023, Feb 2024, Jan 2025 |
| **Polling booth, with coordinates** | **4–8 days if the rolls come in bulk; 2–3 weeks if downloaded one by one** | ECI's part-wise roll downloads are behind a captcha (we do not bypass it). Ask CEO Telangana or the district offices for a booth-wise electors spreadsheet, via Prof. or an RTI request |
| booth coordinates | available for 2017 | `aaronrudkin/IndianPollingStations` (ECI `psleci` scrape, April 2017, lat/long per booth; no licence stated) |
| 2018 Form 20 booth results | not useful for population | scanned PDFs, with votes per booth but no electors per booth |

**Crude AC trend:** across 25 core ACs, electors rose from 79.5 lakh (December 2018) to 88.9 lakh (October 2023). Some ACs fall, e.g. Kukatpally. That is either deleted names or a parsing error, which shows how noisy this source is.

**Pitfalls:**
- **The 2026 SIR purge** removed 21.7% of the state's electors (Hyderabad district about 19 lakh). Use only pre-SIR rolls, SSR-2025 or earlier.
- The 2015 and 2018 deletion drives break comparability across those years.
- Booths are split and renumbered between revisions; expect 10–20% to fail matching.
- Electors are not people: only adults are counted, and migrants are often registered at their native place.

**Literature:** an Irish precedent (Whelan & Keogh 1980, 1986) exists. In India, Jensenius et al. 2025 (*Sci Data*) links booth-level electors to Census 2011 villages, but **no Indian paper uses electoral rolls as a population proxy.** That makes this novel, but it needs a calibration against Census 2011.

**Decision:**
- Use the **AC-level totals now**, as control totals and as a trend check on WorldPop.
- **Request booth-wise counts through Prof.**
- Treat booth electors as a **start-of-period covariate or robustness check,** not the main population layer.

---

## 9. Order of work

| # | task | who / time |
|---|---|---|
| 1 | Eyeball ~60 map-only "change" pixels in Google Earth history: layout, construction or noise? Decides the dependent variable (§2) | you, about 1 h. I can prepare the KML |
| 2 | Script `scripts/change/01_sample.py`: dependent variable + 20k choice-based sample with 200 m spacing | me; one overnight Earth Engine pull for Open Buildings |
| 3 | Script `02_factors.py`: §5c variables (road km window, neighbourhood shares, built edge, slope, constraints) | me, about 1 day |
| 4 | Script `03_models.py`: binary logit (per period + pooled, prior-corrected), res/non-res MNL, LR tests by factor group, latent segmentation | me, minutes per run |
| 5 | In parallel: GO 111 villages, jurisdiction boundaries, Census 2011 village tables, project-site list, voter rolls | split with Ethan? |
| 6 | Natural-experiment tests (§6.3) once task 5 lands | |
| 7 | Questions for Prof.: 100 m block for full/partial? Layout as a third outcome? GHMC property data status? | |
