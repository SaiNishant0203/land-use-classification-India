| Variable | Estimate | t stat | 2017-20 est. | t | 2020-23 est. | t |
|---|---|---|---|---|---|---|
| Constant | -4.500 | -8.75 | -6.016 | -9.45 | -2.926 | -4.65 |
| ***Land use within 1 km (% by area) (Base: open land)*** | | | | | | |
| Residential | 0.021 | 9.83 | 0.015 | 5.85 | 0.026 | 11.40 |
| Non-residential | 0.017 | 8.85 | 0.013 | 5.42 | 0.023 | 10.11 |
| Water | -0.057 | -8.56 | -0.053 | -7.40 | -0.059 | -6.78 |
| Trees | -0.044 | -13.03 | -0.044 | -11.71 | -0.043 | -10.51 |
| Land-use mix (entropy, 0-1) | 4.948 | 24.88 | 5.196 | 23.14 | 4.671 | 20.25 |
| ***Urban form*** | | | | | | |
| Ln(night lights within 1 km) | -4.559 | -8.17 | -5.206 | -7.22 | -4.007 | -7.04 |
| ***Accessibility*** | | | | | | |
| Ln(km to the airport) | -0.141 | -2.79 | -0.156 | -2.70 | -0.123 | -2.26 |
| Ln(km to HITEC City / Financial District) | -0.151 | -3.78 | -0.118 | -2.47 | -0.180 | -3.34 |
| Ln(km to the old CBD) | -0.418 | -3.96 | -0.326 | -2.49 | -0.494 | -4.40 |
| Ln(km to the nearest major road) | -0.165 | -9.62 | -0.152 | -7.90 | -0.180 | -8.80 |
| ***Supply constraints*** | | | | | | |
| Slope (degrees) | 0.086 | 11.12 | 0.095 | 9.51 | 0.078 | 8.16 |
| Relief within 150 m (m) | -0.092 | -9.64 | -0.093 | -7.19 | -0.091 | -7.59 |
| Elevation (100 m) | 0.079 | 2.03 | 0.093 | 1.99 | 0.065 | 1.45 |
| Within 100 m of a lake | -0.938 | -18.56 | -1.074 | -15.79 | -0.808 | -12.68 |
| ***Population*** | | | | | | |
| Ln(WorldPop people per km2) | 0.213 | 5.95 | 0.370 | 8.52 | 0.068 | 1.67 |
| ***Jobs, Economic Census 2013*** | | | | | | |
| Ln(workers within ~5 km) | -0.098 | -3.17 | -0.067 | -1.78 | -0.136 | -3.41 |
| Ln(workers per km2 in the village / town) | 0.041 | 2.56 | 0.042 | 2.01 | 0.037 | 1.98 |
| Establishments with 100+ workers (% of jobs within ~5 km) | 0.005 | 3.69 | 0.004 | 2.74 | 0.005 | 3.48 |
| ***Village / town, Census 2011 and SECC 2011-12*** | | | | | | |
| Ln(people per km2 in the village / town) | -0.065 | -3.18 | -0.070 | -2.58 | -0.063 | -2.64 |
| ***District (Base: Rangareddy)*** | | | | | | |
| Medak | 0.317 | 6.42 | 0.343 | 5.68 | 0.281 | 4.57 |
| Nalgonda | 0.345 | 4.23 | 0.334 | 3.31 | 0.342 | 3.74 |
| Mahabubnagar | 0.281 | 3.05 | 0.420 | 3.80 | 0.135 | 1.44 |
| Hyderabad | -0.105 | -0.78 | -0.258 | -1.51 | 0.080 | 0.58 |
| ***Period (Base: 2017-2020)*** | | | | | | |
| 2020-2023 | 0.125 | 5.57 | -- | -- | -- | -- |

| | pooled | 2017-20 | 2020-23 |
|---|---|---|---|
| cells | 120,000 | 60,000 | 60,000 |
| changes | 54,598 | 25,564 | 29,034 |
| parameters | 25 | 24 | 24 |
| log-likelihood, constant only | -82,690.6 | -40,930.5 | -41,557.7 |
| log-likelihood at convergence | -58,664.4 | -28,791.1 | -29,744.3 |
| rho-squared (vs constant only) | 0.291 | 0.297 | 0.284 |
| adjusted rho-squared | 0.290 | 0.296 | 0.284 |
| AUC, 5-fold cross-validated by 4 km tile | 0.849 | 0.853 | 0.845 |

Eliminated jointly: robust Wald chi2 = 13.7 on 14 df, p = 0.47

| step | eliminated | t when eliminated |
|---|---|---|
| 1 | Software / IT services (% of jobs within ~5 km) | 0.03 |
| 2 | Literacy rate (% of people aged 7+) | -0.07 |
| 3 | GO 111 zone (within 10 km of Osman / Himayat Sagar) | -0.12 |
| 4 | Households with a four-wheeler (%) | -0.28 |
| 5 | Households with a two- or three-wheeler (%) | 0.47 |
| 6 | Military, forest, protected or airport land | -0.59 |
| 7 | Agricultural workers (% of workers) | 0.87 |
| 8 | Ln(km to the nearest open metro station) | 1.00 |
| 9 | SC / ST (% of people) | 1.00 |
| 10 | Manufacturing (% of jobs within ~5 km) | -1.35 |
| 11 | Ln(km to the nearest ORR interchange) | -1.38 |
| 12 | Ln(km to a lake >= 2 ha) | 1.26 |
| 13 | Tree cover (vs open land) | 1.75 |
| 14 | Inside GHMC (village values are city-wide averages) | -1.79 |
