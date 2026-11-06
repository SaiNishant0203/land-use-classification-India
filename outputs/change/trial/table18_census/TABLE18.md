| Variable | Estimate | t stat | 2017-20 est. | t | 2020-23 est. | t |
|---|---|---|---|---|---|---|
| Constant | -1.957 | -1.99 | -2.285 | -2.08 | -1.355 | -1.17 |
| ***Land cover of the cell at t-1 (Base: open land)*** | | | | | | |
| Tree cover (vs open land) | -1.151 | -7.87 | -0.988 | -4.91 | -1.323 | -7.74 |
| ***Land use within 1 km (% by area) (Base: open land)*** | | | | | | |
| Trees | -0.029 | -5.69 | -0.027 | -4.29 | -0.030 | -4.73 |
| Land-use mix (entropy, 0-1) | 1.788 | 5.11 | 2.013 | 3.95 | 1.510 | 3.49 |
| ***Urban form*** | | | | | | |
| Ln(km to the dense city, 1 km built share >= 40%) | -0.312 | -4.37 | -0.259 | -3.12 | -0.357 | -3.41 |
| ***Accessibility*** | | | | | | |
| Ln(km to the airport) | -0.484 | -5.38 | -0.509 | -4.51 | -0.459 | -4.15 |
| Ln(km to HITEC City / Financial District) | -0.410 | -4.63 | -0.453 | -4.30 | -0.376 | -3.27 |
| Ln(km to the nearest major road) | -0.134 | -2.14 | -0.112 | -1.36 | -0.176 | -2.62 |
| Road mileage in the 4 km x 4 km window (10 km) | 0.032 | 2.12 | 0.047 | 2.45 | 0.030 | 1.74 |
| ***Supply constraints*** | | | | | | |
| Slope (degrees) | -0.039 | -2.28 | -0.051 | -2.01 | -0.028 | -1.35 |
| Relief within 150 m (m) | -0.064 | -2.06 | -0.087 | -2.29 | -0.042 | -1.12 |
| Within 100 m of a lake | -1.296 | -9.20 | -1.565 | -7.49 | -1.034 | -5.77 |
| Military, forest, protected or airport land | -1.535 | -4.32 | -0.843 | -2.10 | -2.072 | -2.51 |
| ***Jobs, Economic Census 2013*** | | | | | | |
| Ln(workers within ~5 km) | -0.256 | -2.16 | -0.267 | -2.22 | -0.310 | -2.20 |
| Manufacturing (% of jobs within ~5 km) | -0.020 | -2.94 | -0.018 | -1.85 | -0.021 | -2.48 |
| Establishments with 100+ workers (% of jobs within ~5 km) | 0.036 | 3.33 | 0.045 | 3.93 | 0.031 | 2.33 |
| ***Village / town, Census 2011 and SECC 2011-12*** | | | | | | |
| SC / ST (% of people) | -0.009 | -3.25 | -0.007 | -1.95 | -0.011 | -3.32 |
| Agricultural workers (% of workers) | 0.005 | 2.34 | 0.004 | 1.13 | 0.006 | 2.66 |
| Households with a two- or three-wheeler (%) | 0.007 | 2.16 | 0.011 | 2.63 | 0.003 | 0.98 |
| ***Assembly constituency (Base: Maheshwaram)*** | | | | | | |
| Rajendranagar | -0.080 | -0.61 | -0.204 | -1.24 | 0.002 | 0.01 |
| Serilingampally | -0.346 | -1.39 | -0.535 | -1.80 | -0.205 | -0.67 |
| ***Period (Base: 2017-2020)*** | | | | | | |
| 2020-2023 | -0.080 | -1.11 | -- | -- | -- | -- |

| | pooled | 2017-20 | 2020-23 |
|---|---|---|---|
| cells | 19,813 | 9,896 | 9,917 |
| changes | 3,071 | 1,521 | 1,550 |
| parameters | 22 | 21 | 21 |
| log-likelihood, constant only | -8,545.0 | -4,246.1 | -4,298.8 |
| log-likelihood at convergence | -6,589.2 | -3,167.4 | -3,385.4 |
| rho-squared (vs constant only) | 0.229 | 0.254 | 0.212 |
| adjusted rho-squared | 0.226 | 0.249 | 0.208 |
| AUC, 5-fold cross-validated by 4 km tile | 0.825 | 0.837 | 0.804 |

Eliminated jointly: robust Wald chi2 = 17.7 on 18 df, p = 0.47

| step | eliminated | t when eliminated |
|---|---|---|
| 1 | Ln(WorldPop people per km2) | 0.02 |
| 2 | Non-residential | -0.39 |
| 3 | Households with a four-wheeler (%) | -0.39 |
| 4 | Software / IT services (% of jobs within ~5 km) | -0.50 |
| 5 | Ln(night lights within 1 km) | -0.31 |
| 6 | Elevation (100 m) | -0.56 |
| 7 | Ln(km to the old CBD) | 0.46 |
| 8 | Ln(votes polled per km2, 2018 booths) | -0.47 |
| 9 | Inside GHMC (village values are city-wide averages) | 0.56 |
| 10 | Ln(km to the nearest ORR interchange) | -0.71 |
| 11 | Ln(km to a lake >= 2 ha) | -0.96 |
| 12 | Ln(km to the nearest open metro station) | -0.98 |
| 13 | GO 111 zone (within 10 km of Osman / Himayat Sagar) | 0.67 |
| 14 | Ln(workers per km2 in the village / town) | 1.01 |
| 15 | Ln(people per km2 in the village / town) | -0.89 |
| 16 | Literacy rate (% of people aged 7+) | 1.05 |
| 17 | Residential | -1.40 |
| 18 | Water | -1.78 |
