# scripts/masterplan: HMDA Master Plan 2031 zoning on our 20 m grid

**Source:** the 30 district sheets of the HMDA Metropolitan Development Plan 2031, "Proposed land use zoning and road
network" (approved by Government order in 2013). They come from OpenCity
(data.opencity.in/dataset/hyderabad-master-plan-2031; JPEG, 678 MB in all) and are saved in
`data/raw/masterplan_hmda2031/` (outside git).
- **Scale and sheet layout:** 1:25,000, mostly at 200 dpi, so 3.175 m per pixel. One mandal per sheet: its zones
  are in strong colours and the neighbours are faded. No coordinate ticks.
- **Coverage:** the HMDA area outside the erstwhile HUDA core.

| step | script | what it does |
|---|---|---|
| 1 | `01_georef.py` | first fit of each sheet: its zoned area matched to the Census 2011 mandal outline (SHRUG villages), by IoU. Accuracy about 1 km |
| 2 | `02_refine_roads.py` | the real fit: the red roads and HMDA boundary on the sheet are matched to OSM roads (1 Jan 2021) plus our HMDA outline, by chamfer matching. Exhaustive shift search at 3.175 m/px (or the printed sheet scale for low-resolution copies), then Nelder-Mead. **All 30 sheets fit with 34–75% of red pixels within 40 m of an OSM road**, at 3.17–3.18 m/px (Ibrahimpatnam_Manchal 8.82) and under 0.05° rotation |
| 3 | `03_zones.py` | zone classification: nearest reference colour for every strongly coloured pixel (legend swatches plus map samples; roads, boundaries and labels are ignored), majority in about 200 m windows, kept in the sheet's own zoned area (solid patches ≥ 0.5 km² that touch the Census mandal), resampled to the 20 m grid. Low-resolution copies are calibrated on their own legend |
| 4 | `04_mosaic.py` | one HMDA layer, `data/processed/masterplan/mp2031_zones_20m.tif`. Where sheets overlap, the one with more colour votes wins |

**Zone codes:**
- 1 residential (R1–R4, GDPZ), 2 peri-urban, 3 commercial, 4 manufacturing, 5 public / semi-public, 6 multiple use
  (including the ORR growth corridor)
- 7 conservation (agriculture), 8 protected green (forest, afforestation, recreation, lake buffers),
  9 bio-conservation (GO 111), 10 water, 11 special reservations, 12 settlements
- 0 not covered / not read

**State on 12 Nov 2026:**
- **All 30 sheets are in.** The mosaic covers 74.2% of HMDA (`zone_shares.csv`).
- **What is left uncovered:**
  - the erstwhile HUDA core, which is not in these sheets;
  - a few edge areas that seem to lie outside the 2013 plan area: the sheets draw the 2013 HMDA boundary,
    which differs from our current outline (seen on Yacharam).
- **Clipping:** each sheet is clipped to its own zoned area (solid patches of strong colour of at least
  0.5 km² that touch the Census mandal), not to the Census outline. The planning districts often differ from
  the Census mandals (Faruqnagar, Hatnura, Ghatkesar, Kisara).
- **Ibrahimpatnam_Manchal:** a low-resolution copy (8.82 m/px). Its red-road threshold is relaxed, and it is
  calibrated on its own legend swatches with a 500 m window, because of moiré. Read it with care:
  conservation and reserve forest may be partly mixed up.
- **Checked by eye:** Bibinagar, Chevella, Shamshabad, Medchal_Qutubullapur, Faruqnagar. The thin purple
  line of the erstwhile HUDA boundary is read as manufacturing (minor).

**Run:**

```
python scripts/masterplan/01_georef.py && python scripts/masterplan/02_refine_roads.py
python scripts/masterplan/03_zones.py && python scripts/masterplan/04_mosaic.py
```
