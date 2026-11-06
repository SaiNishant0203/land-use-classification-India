| Variable | Estimate | t stat | 2017-20 est. | t | 2020-23 est. | t |
|---|---|---|---|---|---|---|
| Constant | -3.598 | -6.86 | -3.955 | -6.88 | -3.326 | -5.18 |
| ***Land cover of the cell at t-1 (Base: open land)*** | | | | | | |
| Tree cover (vs open land) | -1.096 | -7.51 | -0.931 | -4.67 | -1.278 | -7.51 |
| ***Land use within 1 km (% by area) (Base: open land)*** | | | | | | |
| Water | -0.040 | -2.88 | -0.054 | -2.81 | -0.023 | -1.38 |
| Trees | -0.042 | -7.56 | -0.042 | -6.34 | -0.042 | -5.97 |
| Land-use mix (entropy, 0-1) | 3.123 | 9.59 | 3.428 | 8.60 | 2.799 | 7.37 |
| ***Accessibility*** | | | | | | |
| Ln(km to the airport) | -0.519 | -6.09 | -0.504 | -4.40 | -0.524 | -5.35 |
| Ln(km to HITEC City / Financial District) | -0.362 | -4.18 | -0.371 | -4.23 | -0.357 | -3.18 |
| Ln(km to the nearest major road) | -0.161 | -2.73 | -0.145 | -1.98 | -0.198 | -2.90 |
| ***Supply constraints*** | | | | | | |
| Slope (degrees) | -0.037 | -2.15 | -0.047 | -1.80 | -0.028 | -1.36 |
| Relief within 150 m (m) | -0.071 | -2.48 | -0.087 | -2.23 | -0.058 | -1.60 |
| Within 100 m of a lake | -1.169 | -7.46 | -1.290 | -5.85 | -1.060 | -5.27 |
| Military, forest, protected or airport land | -1.508 | -4.32 | -0.922 | -2.59 | -1.977 | -2.45 |
| ***Jobs, Economic Census 2013*** | | | | | | |
| Manufacturing (% of jobs within ~5 km) | -0.021 | -3.44 | -0.025 | -2.81 | -0.018 | -2.30 |
| Establishments with 100+ workers (% of jobs within ~5 km) | 0.030 | 3.82 | 0.041 | 4.74 | 0.021 | 2.15 |
| ***Village / town, Census 2011 and SECC 2011-12*** | | | | | | |
| SC / ST (% of people) | -0.009 | -3.10 | -0.007 | -1.92 | -0.011 | -3.04 |
| ***Assembly constituency (Base: Maheshwaram)*** | | | | | | |
| Rajendranagar | -0.104 | -0.73 | -0.149 | -0.86 | -0.073 | -0.43 |
| Serilingampally | -0.264 | -1.05 | -0.267 | -0.95 | -0.288 | -1.00 |
| ***Period (Base: 2017-2020)*** | | | | | | |
| 2020-2023 | -0.034 | -0.52 | -- | -- | -- | -- |

| | pooled | 2017-20 | 2020-23 |
|---|---|---|---|
| cells | 19,813 | 9,896 | 9,917 |
| changes | 3,071 | 1,521 | 1,550 |
| parameters | 18 | 17 | 17 |
| log-likelihood, constant only | -8,545.0 | -4,246.1 | -4,298.8 |
| log-likelihood at convergence | -6,645.2 | -3,195.5 | -3,424.1 |
| rho-squared (vs constant only) | 0.222 | 0.247 | 0.203 |
| adjusted rho-squared | 0.220 | 0.243 | 0.200 |
| AUC, 5-fold cross-validated by 4 km tile | 0.821 | 0.835 | 0.799 |

Eliminated jointly: robust Wald chi2 = 25.5 on 20 df, p = 0.18

| step | eliminated | t when eliminated |
|---|---|---|
| 1 | Residential | -0.01 |
| 2 | Ln(workers within ~5 km) | -0.05 |
| 3 | GO 111 zone (within 10 km of Osman / Himayat Sagar) | 0.14 |
| 4 | Inside GHMC (village values are city-wide averages) | 0.33 |
| 5 | Households with a four-wheeler (%) | -0.21 |
| 6 | Ln(votes polled per km2, 2018 booths) | -0.37 |
| 7 | Ln(km to a lake >= 2 ha) | -0.45 |
| 8 | Software / IT services (% of jobs within ~5 km) | -0.59 |
| 9 | Ln(night lights within 1 km) | -0.35 |
| 10 | Elevation (100 m) | -0.81 |
| 11 | Ln(workers per km2 in the village / town) | 0.96 |
| 12 | Ln(km to the old CBD) | 1.02 |
| 13 | Ln(WorldPop people per km2) | 0.92 |
| 14 | Ln(people per km2 in the village / town) | -1.11 |
| 15 | Literacy rate (% of people aged 7+) | 0.90 |
| 16 | Ln(km to the nearest ORR interchange) | -1.28 |
| 17 | Agricultural workers (% of workers) | 1.25 |
| 18 | Non-residential | 1.32 |
| 19 | Households with a two- or three-wheeler (%) | 1.59 |
| 20 | Ln(km to the nearest open metro station) | -1.88 |
