| Variable | Estimate | t stat | 2017-20 est. | t | 2020-23 est. | t |
|---|---|---|---|---|---|---|
| Constant | -3.333 | -6.81 | -3.523 | -6.94 | -3.292 | -5.44 |
| ***Land cover of the cell at t-1 (Base: open land)*** | | | | | | |
| Tree cover (vs open land) | -1.162 | -7.88 | -0.995 | -4.87 | -1.338 | -7.66 |
| ***Land use within 1 km (% by area) (Base: open land)*** | | | | | | |
| Trees | -0.029 | -5.90 | -0.027 | -4.18 | -0.031 | -4.98 |
| Land-use mix (entropy, 0-1) | 1.893 | 5.65 | 2.221 | 4.65 | 1.575 | 3.52 |
| ***Urban form*** | | | | | | |
| Ln(km to the dense city, 1 km built share >= 40%) | -0.300 | -4.00 | -0.270 | -3.12 | -0.325 | -3.14 |
| ***Accessibility*** | | | | | | |
| Ln(km to the airport) | -0.507 | -5.15 | -0.472 | -4.04 | -0.515 | -4.57 |
| Ln(km to HITEC City / Financial District) | -0.480 | -4.68 | -0.541 | -5.08 | -0.418 | -3.32 |
| Ln(km to the nearest major road) | -0.132 | -2.23 | -0.100 | -1.29 | -0.186 | -2.77 |
| Road mileage in the 4 km x 4 km window (10 km) | 0.021 | 2.21 | 0.037 | 2.85 | 0.009 | 0.77 |
| ***Supply constraints*** | | | | | | |
| Slope (degrees) | -0.041 | -2.34 | -0.052 | -2.04 | -0.030 | -1.42 |
| Relief within 150 m (m) | -0.065 | -2.16 | -0.085 | -2.27 | -0.047 | -1.22 |
| Within 100 m of a lake | -1.284 | -8.96 | -1.537 | -7.15 | -1.038 | -5.77 |
| Military, forest, protected or airport land | -1.551 | -4.21 | -0.833 | -2.04 | -2.087 | -2.52 |
| ***Assembly constituency (Base: Maheshwaram)*** | | | | | | |
| Rajendranagar | -0.109 | -0.75 | -0.236 | -1.37 | -0.026 | -0.15 |
| Serilingampally | -0.355 | -1.34 | -0.495 | -1.70 | -0.294 | -0.97 |
| ***Period (Base: 2017-2020)*** | | | | | | |
| 2020-2023 | -0.056 | -0.78 | -- | -- | -- | -- |

| | pooled | 2017-20 | 2020-23 |
|---|---|---|---|
| cells | 19,813 | 9,896 | 9,917 |
| changes | 3,071 | 1,521 | 1,550 |
| parameters | 16 | 15 | 15 |
| log-likelihood, constant only | -8,545.0 | -4,246.1 | -4,298.8 |
| log-likelihood at convergence | -6,646.8 | -3,199.7 | -3,421.2 |
| rho-squared (vs constant only) | 0.222 | 0.246 | 0.204 |
| adjusted rho-squared | 0.220 | 0.243 | 0.201 |
| AUC, 5-fold cross-validated by 4 km tile | 0.824 | 0.838 | 0.803 |

Eliminated jointly: robust Wald chi2 = 15.6 on 12 df, p = 0.21

| step | eliminated | t when eliminated |
|---|---|---|
| 1 | Ln(WorldPop people per km2) | 0.08 |
| 2 | Elevation (100 m) | -0.19 |
| 3 | Ln(km to the old CBD) | 0.46 |
| 4 | Ln(km to the nearest ORR interchange) | -0.58 |
| 5 | Ln(votes polled per km2, 2018 booths) | -0.70 |
| 6 | Ln(km to a lake >= 2 ha) | -0.74 |
| 7 | Non-residential | -0.86 |
| 8 | Residential | -0.99 |
| 9 | GO 111 zone (within 10 km of Osman / Himayat Sagar) | 1.09 |
| 10 | Ln(km to the nearest open metro station) | -1.28 |
| 11 | Water | -1.50 |
| 12 | Ln(night lights within 1 km) | -1.84 |
