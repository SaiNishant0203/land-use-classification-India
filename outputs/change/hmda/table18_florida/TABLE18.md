| Variable | Estimate | t stat | 2017-20 est. | t | 2020-23 est. | t |
|---|---|---|---|---|---|---|
| Constant | -4.217 | -11.34 | -4.602 | -10.55 | -3.883 | -9.28 |
| ***Land cover of the cell at t-1 (Base: open land)*** | | | | | | |
| Tree cover (vs open land) | -1.092 | -16.00 | -0.941 | -10.95 | -1.250 | -13.64 |
| ***Land use within 1 km (% by area) (Base: open land)*** | | | | | | |
| Residential | -0.007 | -2.98 | -0.009 | -2.78 | -0.004 | -1.40 |
| Water | -0.052 | -4.44 | -0.061 | -4.62 | -0.041 | -2.48 |
| Trees | -0.047 | -12.64 | -0.047 | -10.42 | -0.047 | -10.10 |
| Land-use mix (entropy, 0-1) | 3.849 | 21.07 | 4.189 | 16.89 | 3.514 | 16.76 |
| ***Accessibility*** | | | | | | |
| Ln(km to the old CBD) | -0.687 | -6.22 | -0.608 | -4.78 | -0.753 | -6.07 |
| Ln(km to the nearest ORR interchange) | -0.258 | -6.39 | -0.279 | -6.11 | -0.244 | -5.28 |
| Ln(km to the nearest major road) | -0.181 | -6.15 | -0.162 | -4.58 | -0.205 | -5.85 |
| ***Supply constraints*** | | | | | | |
| Slope (degrees) | -0.055 | -5.56 | -0.051 | -3.81 | -0.059 | -4.29 |
| Relief within 150 m (m) | -0.056 | -3.41 | -0.065 | -3.08 | -0.047 | -2.19 |
| Ln(km to a lake >= 2 ha) | 0.113 | 2.89 | 0.074 | 1.49 | 0.144 | 3.27 |
| Within 100 m of a lake | -1.062 | -10.36 | -1.266 | -9.06 | -0.876 | -7.17 |
| Military, forest, protected or airport land | -0.965 | -3.71 | -1.074 | -3.44 | -0.842 | -2.77 |
| ***Jobs, Economic Census 2013*** | | | | | | |
| Software / IT services (% of jobs within ~5 km) | 0.020 | 3.92 | 0.028 | 4.68 | 0.011 | 2.00 |
| Establishments with 100+ workers (% of jobs within ~5 km) | 0.010 | 4.57 | 0.010 | 3.77 | 0.010 | 4.01 |
| ***District (Base: Rangareddy)*** | | | | | | |
| Medak | 0.211 | 2.23 | 0.231 | 1.92 | 0.198 | 1.99 |
| Nalgonda | -0.182 | -1.27 | -0.064 | -0.43 | -0.272 | -1.41 |
| Mahabubnagar | 0.176 | 0.97 | 0.472 | 2.04 | -0.112 | -0.62 |
| Hyderabad | -0.752 | -3.60 | -0.462 | -2.04 | -1.056 | -4.46 |
| ***Period (Base: 2017-2020)*** | | | | | | |
| 2020-2023 | -0.009 | -0.26 | -- | -- | -- | -- |

| | pooled | 2017-20 | 2020-23 |
|---|---|---|---|
| cells | 120,000 | 60,000 | 60,000 |
| changes | 12,314 | 6,034 | 6,280 |
| parameters | 21 | 20 | 20 |
| log-likelihood, constant only | -39,695.4 | -19,579.6 | -20,113.0 |
| log-likelihood at convergence | -30,436.6 | -14,721.1 | -15,649.5 |
| rho-squared (vs constant only) | 0.233 | 0.248 | 0.222 |
| adjusted rho-squared | 0.233 | 0.247 | 0.221 |
| AUC, 5-fold cross-validated by 4 km tile | 0.839 | 0.846 | 0.835 |

Eliminated jointly: robust Wald chi2 = 22.4 on 18 df, p = 0.22

| step | eliminated | t when eliminated |
|---|---|---|
| 1 | Ln(workers per km2 in the village / town) | -0.26 |
| 2 | Ln(km to HITEC City / Financial District) | 0.24 |
| 3 | GO 111 zone (within 10 km of Osman / Himayat Sagar) | 0.47 |
| 4 | Households with a four-wheeler (%) | -0.41 |
| 5 | Non-residential | 0.50 |
| 6 | Ln(km to the nearest open metro station) | 0.59 |
| 7 | Ln(workers within ~5 km) | 0.56 |
| 8 | Literacy rate (% of people aged 7+) | 0.67 |
| 9 | Households with a two- or three-wheeler (%) | 0.81 |
| 10 | Ln(night lights within 1 km) | -0.95 |
| 11 | Ln(WorldPop people per km2) | 0.94 |
| 12 | SC / ST (% of people) | -1.15 |
| 13 | Ln(people per km2 in the village / town) | -1.09 |
| 14 | Ln(km to the airport) | -1.45 |
| 15 | Agricultural workers (% of workers) | -1.63 |
| 16 | Inside GHMC (village values are city-wide averages) | -1.56 |
| 17 | Elevation (100 m) | 1.81 |
| 18 | Manufacturing (% of jobs within ~5 km) | -1.55 |
