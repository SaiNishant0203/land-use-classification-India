| Variable | Estimate | t stat | 2017-20 est. | t | 2020-23 est. | t |
|---|---|---|---|---|---|---|
| Constant | -5.310 | -12.10 | -6.316 | -11.64 | -4.344 | -9.27 |
| ***Land use within 1 km (% by area) (Base: open land)*** | | | | | | |
| Residential | 0.025 | 11.90 | 0.018 | 7.15 | 0.031 | 13.31 |
| Non-residential | 0.022 | 11.12 | 0.016 | 7.01 | 0.028 | 11.77 |
| Water | -0.058 | -8.55 | -0.054 | -7.31 | -0.061 | -6.89 |
| Trees | -0.044 | -13.32 | -0.044 | -11.99 | -0.043 | -10.67 |
| Land-use mix (entropy, 0-1) | 5.089 | 25.56 | 5.314 | 23.82 | 4.856 | 20.52 |
| ***Urban form*** | | | | | | |
| Ln(km to the dense city, 1 km built share >= 40%) | 0.141 | 6.62 | 0.111 | 4.04 | 0.174 | 7.06 |
| Ln(night lights within 1 km) | -4.055 | -8.08 | -4.498 | -6.68 | -3.745 | -7.22 |
| ***Accessibility*** | | | | | | |
| Ln(km to the airport) | -0.122 | -2.47 | -0.136 | -2.51 | -0.110 | -2.01 |
| Ln(km to the old CBD) | -0.552 | -4.35 | -0.473 | -3.14 | -0.581 | -4.37 |
| Ln(km to the nearest ORR interchange) | -0.111 | -3.85 | -0.103 | -3.10 | -0.125 | -3.59 |
| Ln(km to the nearest major road) | -0.168 | -9.79 | -0.152 | -7.98 | -0.185 | -9.07 |
| Road mileage in the 4 km x 4 km window (10 km) | -0.030 | -5.16 | -0.029 | -3.88 | -0.029 | -4.73 |
| ***Supply constraints*** | | | | | | |
| Slope (degrees) | 0.085 | 11.05 | 0.094 | 9.47 | 0.076 | 8.02 |
| Relief within 150 m (m) | -0.094 | -9.80 | -0.095 | -7.37 | -0.092 | -7.67 |
| Ln(km to a lake >= 2 ha) | 0.047 | 2.08 | 0.049 | 1.75 | 0.043 | 1.67 |
| Within 100 m of a lake | -0.852 | -14.99 | -0.984 | -12.83 | -0.731 | -10.45 |
| ***Population*** | | | | | | |
| Ln(WorldPop people per km2) | 0.275 | 7.23 | 0.421 | 9.04 | 0.135 | 3.21 |
| ***Jobs, Economic Census 2013*** | | | | | | |
| Establishments with 100+ workers (% of jobs within ~5 km) | 0.004 | 3.27 | 0.004 | 2.41 | 0.005 | 3.19 |
| ***District (Base: Rangareddy)*** | | | | | | |
| Medak | 0.285 | 5.69 | 0.325 | 5.28 | 0.232 | 3.89 |
| Nalgonda | 0.224 | 3.59 | 0.217 | 2.82 | 0.215 | 3.07 |
| Mahabubnagar | 0.343 | 3.70 | 0.493 | 4.50 | 0.190 | 1.98 |
| Hyderabad | -0.202 | -1.34 | -0.327 | -1.74 | -0.043 | -0.29 |
| ***Period (Base: 2017-2020)*** | | | | | | |
| 2020-2023 | 0.154 | 6.87 | -- | -- | -- | -- |

| | pooled | 2017-20 | 2020-23 |
|---|---|---|---|
| cells | 120,000 | 60,000 | 60,000 |
| changes | 54,598 | 25,564 | 29,034 |
| parameters | 24 | 23 | 23 |
| log-likelihood, constant only | -82,690.6 | -40,930.5 | -41,557.7 |
| log-likelihood at convergence | -58,529.1 | -28,739.1 | -29,664.4 |
| rho-squared (vs constant only) | 0.292 | 0.298 | 0.286 |
| adjusted rho-squared | 0.292 | 0.297 | 0.286 |
| AUC, 5-fold cross-validated by 4 km tile | 0.849 | 0.852 | 0.845 |

Eliminated jointly: robust Wald chi2 = 19.7 on 17 df, p = 0.29

| step | eliminated | t when eliminated |
|---|---|---|
| 1 | Ln(workers within ~5 km) | 0.05 |
| 2 | Households with a two- or three-wheeler (%) | 0.20 |
| 3 | Agricultural workers (% of workers) | -0.29 |
| 4 | Ln(km to the nearest open metro station) | 0.35 |
| 5 | GO 111 zone (within 10 km of Osman / Himayat Sagar) | -0.30 |
| 6 | Military, forest, protected or airport land | -0.35 |
| 7 | Households with a four-wheeler (%) | -0.51 |
| 8 | Software / IT services (% of jobs within ~5 km) | 0.83 |
| 9 | Literacy rate (% of people aged 7+) | 0.91 |
| 10 | SC / ST (% of people) | 0.80 |
| 11 | Ln(km to HITEC City / Financial District) | -1.19 |
| 12 | Ln(people per km2 in the village / town) | -1.33 |
| 13 | Manufacturing (% of jobs within ~5 km) | -1.25 |
| 14 | Ln(workers per km2 in the village / town) | 1.32 |
| 15 | Inside GHMC (village values are city-wide averages) | -1.52 |
| 16 | Tree cover (vs open land) | 1.63 |
| 17 | Elevation (100 m) | 1.71 |
