| Variable | Estimate | t stat | 2017-20 est. | t | 2020-23 est. | t |
|---|---|---|---|---|---|---|
| Constant | -5.027 | -11.66 | -6.014 | -11.35 | -4.081 | -8.76 |
| ***Land use within 1 km (% by area) (Base: open land)*** | | | | | | |
| Residential | 0.024 | 11.40 | 0.018 | 6.69 | 0.031 | 12.92 |
| Non-residential | 0.021 | 10.44 | 0.016 | 6.47 | 0.028 | 11.36 |
| Water | -0.059 | -8.74 | -0.054 | -7.56 | -0.062 | -7.00 |
| Trees | -0.044 | -13.38 | -0.044 | -11.99 | -0.044 | -10.79 |
| Land-use mix (entropy, 0-1) | 5.112 | 25.33 | 5.340 | 23.63 | 4.880 | 20.42 |
| ***Urban form*** | | | | | | |
| Ln(km to the dense city, 1 km built share >= 40%) | 0.124 | 6.01 | 0.096 | 3.65 | 0.157 | 6.40 |
| Ln(night lights within 1 km) | -4.034 | -7.39 | -4.408 | -5.87 | -3.767 | -7.11 |
| ***Accessibility*** | | | | | | |
| Ln(km to the old CBD) | -0.699 | -6.48 | -0.636 | -4.88 | -0.713 | -6.10 |
| Ln(km to the nearest ORR interchange) | -0.135 | -4.62 | -0.126 | -3.81 | -0.149 | -4.25 |
| Ln(km to the nearest major road) | -0.170 | -9.98 | -0.155 | -8.16 | -0.186 | -9.21 |
| Road mileage in the 4 km x 4 km window (10 km) | -0.032 | -5.44 | -0.033 | -4.18 | -0.030 | -4.94 |
| ***Supply constraints*** | | | | | | |
| Slope (degrees) | 0.085 | 11.02 | 0.093 | 9.41 | 0.075 | 7.97 |
| Relief within 150 m (m) | -0.094 | -9.52 | -0.095 | -7.31 | -0.092 | -7.40 |
| Ln(km to a lake >= 2 ha) | 0.048 | 2.14 | 0.052 | 1.92 | 0.041 | 1.62 |
| Within 100 m of a lake | -0.852 | -15.12 | -0.983 | -12.90 | -0.732 | -10.47 |
| ***Population*** | | | | | | |
| Ln(WorldPop people per km2) | 0.270 | 7.07 | 0.411 | 9.04 | 0.131 | 3.12 |
| ***District (Base: Rangareddy)*** | | | | | | |
| Medak | 0.278 | 5.79 | 0.310 | 5.28 | 0.231 | 4.10 |
| Nalgonda | 0.203 | 3.26 | 0.191 | 2.54 | 0.197 | 2.82 |
| Mahabubnagar | 0.453 | 5.55 | 0.604 | 6.16 | 0.298 | 3.45 |
| Hyderabad | -0.277 | -1.80 | -0.407 | -2.12 | -0.114 | -0.76 |
| ***Period (Base: 2017-2020)*** | | | | | | |
| 2020-2023 | 0.155 | 6.92 | -- | -- | -- | -- |

| | pooled | 2017-20 | 2020-23 |
|---|---|---|---|
| cells | 120,000 | 60,000 | 60,000 |
| changes | 54,598 | 25,564 | 29,034 |
| parameters | 22 | 21 | 21 |
| log-likelihood, constant only | -82,690.6 | -40,930.5 | -41,557.7 |
| log-likelihood at convergence | -58,568.0 | -28,757.5 | -29,684.5 |
| rho-squared (vs constant only) | 0.292 | 0.297 | 0.286 |
| adjusted rho-squared | 0.291 | 0.297 | 0.285 |
| AUC, 5-fold cross-validated by 4 km tile | 0.849 | 0.852 | 0.845 |

Eliminated jointly: robust Wald chi2 = 8.0 on 7 df, p = 0.33

| step | eliminated | t when eliminated |
|---|---|---|
| 1 | Ln(km to the nearest open metro station) | 0.43 |
| 2 | GO 111 zone (within 10 km of Osman / Himayat Sagar) | -0.37 |
| 3 | Military, forest, protected or airport land | -0.61 |
| 4 | Ln(km to HITEC City / Financial District) | -0.81 |
| 5 | Elevation (100 m) | 1.15 |
| 6 | Tree cover (vs open land) | 1.56 |
| 7 | Ln(km to the airport) | -1.78 |
