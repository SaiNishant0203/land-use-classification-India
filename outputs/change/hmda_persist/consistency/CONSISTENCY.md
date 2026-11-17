## A. HMDA final specification fitted in each subregion (estimate, t in brackets; * = sign differs from HMDA)

| variable | HMDA | trial ACs 50-52 | rest of HMDA | CBD < 20 km | CBD 20-35 km | CBD >= 35 km |
|---|---|---|---|---|---|---|
| Residential | 0.025 (11.9) | 0.017 (4.7) | 0.026 (11.0) | 0.018 (9.0) | 0.012 (3.0) | 0.024 (3.2) |
| Non-residential | 0.022 (11.1) | 0.018 (4.8) | 0.024 (11.4) | 0.018 (9.0) | 0.015 (4.4) | 0.017 (2.1) |
| Water | -0.058 (-8.6) | -0.024 (-2.2) | -0.070 (-8.9) | -0.015 (-2.2) | -0.084 (-8.9) | -0.130 (-8.0) |
| Trees | -0.044 (-13.3) | -0.032 (-6.2) | -0.047 (-12.1) | -0.016 (-6.1) | -0.061 (-12.6) | -0.089 (-7.1) |
| Land-use mix (entropy, 0-1) | 5.089 (25.6) | 3.610 (9.5) | 5.388 (24.3) | 1.745 (7.1) | 5.959 (20.1) | 7.962 (14.3) |
| Ln(km to the dense city, 1 km built share >= 40%) | 0.141 (6.6) | 0.037 (0.6) | 0.164 (7.2) | -0.071 (-1.3) * | 0.106 (3.5) | 0.213 (5.9) |
| Ln(night lights within 1 km) | -4.055 (-8.1) | -2.518 (-3.9) | -4.618 (-6.7) | -0.893 (-2.2) | -2.231 (-1.6) | 4.193 (1.8) * |
| Ln(km to the airport) | -0.122 (-2.5) | -0.353 (-4.2) | -0.213 (-2.2) | -0.075 (-1.5) | 0.094 (1.3) * | 0.010 (0.0) * |
| Ln(km to the old CBD) | -0.552 (-4.4) | 0.272 (1.1) * | -0.658 (-4.4) | 0.100 (1.2) * | -1.352 (-5.2) | -0.936 (-1.7) |
| Ln(km to the nearest ORR interchange) | -0.111 (-3.8) | -0.107 (-1.9) | -0.125 (-3.9) | 0.081 (1.6) * | -0.101 (-2.5) | -0.081 (-0.4) |
| Ln(km to the nearest major road) | -0.168 (-9.8) | -0.144 (-3.0) | -0.172 (-9.3) | -0.078 (-2.8) | -0.173 (-6.2) | -0.190 (-6.8) |
| Road mileage in the 4 km x 4 km window (10 km) | -0.030 (-5.2) | -0.013 (-1.0) | -0.032 (-5.1) | -0.009 (-1.8) | -0.032 (-3.7) | -0.074 (-2.7) |
| Slope (degrees) | 0.085 (11.1) | 0.061 (4.0) | 0.092 (10.7) | 0.050 (4.7) | 0.077 (6.4) | 0.144 (9.8) |
| Relief within 150 m (m) | -0.094 (-9.8) | -0.028 (-1.5) | -0.106 (-9.7) | -0.049 (-3.4) | -0.057 (-4.5) | -0.141 (-7.1) |
| Ln(km to a lake >= 2 ha) | 0.047 (2.1) | -0.054 (-1.0) * | 0.044 (1.8) | 0.042 (1.1) | 0.113 (3.3) | 0.060 (1.6) |
| Within 100 m of a lake | -0.852 (-15.0) | -0.994 (-8.4) | -0.846 (-13.1) | -0.677 (-8.5) | -0.717 (-8.0) | -1.070 (-9.2) |
| Ln(WorldPop people per km2) | 0.275 (7.2) | 0.417 (4.0) | 0.260 (6.2) | 0.001 (0.0) | 0.052 (0.9) | 0.180 (2.3) |
| Establishments with 100+ workers (% of jobs within ~5 km) | 0.004 (3.3) | 0.007 (1.4) | 0.003 (2.4) | 0.012 (2.3) | 0.003 (1.6) | -0.003 (-1.2) * |
| Medak | 0.285 (5.7) | -- | 0.315 (5.6) | -- | 0.226 (3.2) | 0.412 (2.9) |
| Nalgonda | 0.224 (3.6) | -- | 0.234 (3.6) | -- | 0.039 (0.4) | 0.283 (2.1) |
| Mahabubnagar | 0.343 (3.7) | -- | 0.334 (3.2) | -- | 0.330 (2.1) | 0.573 (4.7) |
| Hyderabad | -0.202 (-1.3) | -- | -0.254 (-1.3) | -0.018 (-0.2) | -- | -- |
| 2020-2023 | 0.154 (6.9) | 0.153 (3.2) | 0.155 (6.3) | 0.062 (1.5) | 0.228 (7.0) | 0.112 (2.5) |

| | HMDA | trial ACs 50-52 | rest of HMDA | CBD < 20 km | CBD 20-35 km | CBD >= 35 km |
|---|---|---|---|---|---|---|
| cells | 120,000 | 20,802 | 99,198 | 29,364 | 41,923 | 48,713 |
| changes | 54,598 | 11,241 | 43,357 | 21,967 | 18,971 | 13,660 |
| rho-squared | 0.292 | 0.274 | 0.295 | 0.091 | 0.240 | 0.308 |
| AUC, cross-validated by tile | 0.849 | 0.825 | 0.851 | 0.680 | 0.819 | 0.864 |
| variables kept by own elimination | 18 | 17 | 21 | 19 | 21 | 19 |

## B. Backward elimination from every candidate, separately in each subregion (t of the kept variables)

| variable | HMDA | trial ACs 50-52 | rest of HMDA | CBD < 20 km | CBD 20-35 km | CBD >= 35 km |
|---|---|---|---|---|---|---|
| Tree cover (vs open land) |  |  | 2.7 | -6.2 | 2.2 | 7.0 |
| Residential | 11.9 | 5.4 | 11.1 | 11.3 | 2.1 | 4.3 |
| Non-residential | 11.1 | 5.5 | 11.3 | 14.0 | 3.4 | 4.0 |
| Water | -8.6 | -2.2 | -9.2 | -2.1 | -9.5 | -8.0 |
| Trees | -13.3 | -6.2 | -12.3 | -3.6 | -14.5 | -7.5 |
| Land-use mix (entropy, 0-1) | 25.6 | 10.5 | 24.5 | 9.6 | 21.5 | 14.1 |
| Ln(km to the dense city, 1 km built share >= 40%) | 6.6 |  | 7.6 |  | 3.7 | 7.2 |
| Ln(night lights within 1 km) | -8.1 | -2.9 | -7.2 | -2.3 |  |  |
| Ln(km to the airport) | -2.5 | -5.2 |  | -2.7 | 2.2 |  |
| Ln(km to HITEC City / Financial District) |  | -2.1 | -3.1 |  |  | -4.7 |
| Ln(km to the old CBD) | -4.4 |  | -6.0 |  | -6.6 |  |
| Ln(km to the nearest ORR interchange) | -3.8 |  | -2.3 | 2.0 |  |  |
| Ln(km to the nearest open metro station) |  |  | 3.0 |  |  |  |
| Ln(km to the nearest major road) | -9.8 | -3.0 | -9.2 | -2.9 | -7.0 | -7.5 |
| Road mileage in the 4 km x 4 km window (10 km) | -5.2 |  | -4.5 |  | -3.3 | -2.6 |
| Slope (degrees) | 11.1 | 2.7 | 10.6 | 5.1 | 6.2 | 9.1 |
| Relief within 150 m (m) | -9.8 |  | -9.4 | -3.6 | -5.1 | -6.9 |
| Elevation (100 m) |  |  |  |  | 4.1 | 6.6 |
| Ln(km to a lake >= 2 ha) | 2.1 |  | 2.0 |  | 2.3 |  |
| Within 100 m of a lake | -15.0 | -8.3 | -13.2 | -9.9 | -8.2 | -11.2 |
| Military, forest, protected or airport land |  | -3.7 |  | -3.4 | 2.3 |  |
| GO 111 zone (within 10 km of Osman / Himayat Sagar) |  |  |  |  |  |  |
| Ln(WorldPop people per km2) | 7.2 | 4.0 | 6.3 |  |  | 2.5 |
| Ln(workers within ~5 km) |  | -2.5 |  | -3.7 |  | 3.2 |
| Ln(workers per km2 in the village / town) |  |  |  |  |  |  |
| Software / IT services (% of jobs within ~5 km) |  | 2.5 |  | 2.2 | -2.0 | 2.2 |
| Manufacturing (% of jobs within ~5 km) |  |  |  |  | -3.2 |  |
| Establishments with 100+ workers (% of jobs within ~5 km) | 3.3 |  | 2.1 | 3.0 | 2.8 |  |
| Ln(people per km2 in the village / town) |  |  |  |  |  |  |
| SC / ST (% of people) |  |  |  |  |  | 4.8 |
| Literacy rate (% of people aged 7+) |  |  |  | 2.8 |  |  |
| Agricultural workers (% of workers) |  | 2.2 | -2.0 |  | -2.1 |  |
| Households with a two- or three-wheeler (%) |  | 2.6 |  |  |  | -2.1 |
| Households with a four-wheeler (%) |  |  |  | -2.9 |  |  |
| Inside GHMC (village values are city-wide averages) |  |  |  |  |  |  |
| Medak | 5.7 |  | 5.2 |  | 4.8 | 6.2 |
| Nalgonda | 3.6 |  | 3.4 |  | 2.3 | 8.2 |
| Mahabubnagar | 3.7 |  | 4.0 |  | 3.0 | 3.1 |
| Hyderabad | -1.3 |  | -1.9 | 3.0 |  |  |
| 2020-2023 | 6.9 | 3.1 | 6.9 | 1.5 | 6.3 | 3.0 |
