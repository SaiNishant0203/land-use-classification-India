| Variable | Estimate | t stat | 2017-20 est. | t | 2020-23 est. | t |
|---|---|---|---|---|---|---|
| Constant | -4.843 | -9.57 | -4.910 | -8.46 | -4.780 | -8.24 |
| ***Land cover of the cell at t-1 (Base: open land)*** | | | | | | |
| Tree cover (vs open land) | -1.099 | -16.19 | -0.941 | -10.83 | -1.263 | -13.70 |
| ***Land use within 1 km (% by area) (Base: open land)*** | | | | | | |
| Residential | -0.012 | -5.12 | -0.015 | -4.37 | -0.009 | -3.02 |
| Non-residential | -0.006 | -2.67 | -0.007 | -2.32 | -0.006 | -2.09 |
| Water | -0.047 | -4.23 | -0.057 | -4.42 | -0.036 | -2.30 |
| Trees | -0.045 | -11.35 | -0.046 | -8.96 | -0.044 | -9.30 |
| Land-use mix (entropy, 0-1) | 3.353 | 15.48 | 3.810 | 12.34 | 2.944 | 11.68 |
| ***Urban form*** | | | | | | |
| Ln(km to the dense city, 1 km built share >= 40%) | -0.231 | -6.01 | -0.219 | -4.47 | -0.238 | -4.92 |
| ***Accessibility*** | | | | | | |
| Ln(km to the old CBD) | -0.655 | -5.49 | -0.561 | -4.02 | -0.737 | -5.48 |
| Ln(km to the nearest ORR interchange) | -0.237 | -5.61 | -0.269 | -5.54 | -0.214 | -4.40 |
| Ln(km to the nearest major road) | -0.170 | -5.64 | -0.151 | -4.23 | -0.192 | -5.26 |
| ***Supply constraints*** | | | | | | |
| Slope (degrees) | -0.055 | -5.49 | -0.050 | -3.71 | -0.059 | -4.28 |
| Relief within 150 m (m) | -0.062 | -3.75 | -0.071 | -3.34 | -0.054 | -2.41 |
| Elevation (100 m) | 0.162 | 2.18 | 0.098 | 1.10 | 0.215 | 2.59 |
| Ln(km to a lake >= 2 ha) | 0.095 | 2.49 | 0.066 | 1.32 | 0.120 | 2.75 |
| Within 100 m of a lake | -1.091 | -10.76 | -1.288 | -9.26 | -0.911 | -7.45 |
| Military, forest, protected or airport land | -1.025 | -3.90 | -1.108 | -3.48 | -0.926 | -3.03 |
| ***Jobs, Economic Census 2013*** | | | | | | |
| Software / IT services (% of jobs within ~5 km) | 0.015 | 2.90 | 0.023 | 3.84 | 0.006 | 1.03 |
| Manufacturing (% of jobs within ~5 km) | -0.006 | -2.48 | -0.006 | -2.15 | -0.006 | -2.13 |
| Establishments with 100+ workers (% of jobs within ~5 km) | 0.011 | 4.50 | 0.011 | 4.04 | 0.011 | 3.70 |
| ***District (Base: Rangareddy)*** | | | | | | |
| Medak | 0.306 | 3.17 | 0.323 | 2.56 | 0.302 | 2.81 |
| Nalgonda | 0.126 | 0.71 | 0.150 | 0.76 | 0.119 | 0.52 |
| Mahabubnagar | 0.173 | 0.97 | 0.525 | 2.23 | -0.158 | -0.91 |
| Hyderabad | -0.740 | -3.66 | -0.440 | -2.04 | -1.056 | -4.47 |
| ***Period (Base: 2017-2020)*** | | | | | | |
| 2020-2023 | -0.021 | -0.58 | -- | -- | -- | -- |

| | pooled | 2017-20 | 2020-23 |
|---|---|---|---|
| cells | 120,000 | 60,000 | 60,000 |
| changes | 12,314 | 6,034 | 6,280 |
| parameters | 25 | 24 | 24 |
| log-likelihood, constant only | -39,695.4 | -19,579.6 | -20,113.0 |
| log-likelihood at convergence | -30,326.0 | -14,674.6 | -15,583.8 |
| rho-squared (vs constant only) | 0.236 | 0.251 | 0.225 |
| adjusted rho-squared | 0.235 | 0.249 | 0.224 |
| AUC, 5-fold cross-validated by 4 km tile | 0.841 | 0.847 | 0.837 |

Eliminated jointly: robust Wald chi2 = 11.1 on 16 df, p = 0.80

| step | eliminated | t when eliminated |
|---|---|---|
| 1 | Ln(workers per km2 in the village / town) | -0.06 |
| 2 | Ln(workers within ~5 km) | -0.12 |
| 3 | Ln(WorldPop people per km2) | -0.14 |
| 4 | Ln(km to HITEC City / Financial District) | 0.16 |
| 5 | Households with a four-wheeler (%) | -0.29 |
| 6 | Ln(km to the nearest open metro station) | 0.36 |
| 7 | Literacy rate (% of people aged 7+) | 0.47 |
| 8 | Road mileage in the 4 km x 4 km window (10 km) | 0.64 |
| 9 | GO 111 zone (within 10 km of Osman / Himayat Sagar) | 0.75 |
| 10 | Ln(night lights within 1 km) | -0.77 |
| 11 | Agricultural workers (% of workers) | -0.97 |
| 12 | Ln(people per km2 in the village / town) | -1.01 |
| 13 | SC / ST (% of people) | -0.94 |
| 14 | Households with a two- or three-wheeler (%) | 0.97 |
| 15 | Ln(km to the airport) | -1.23 |
| 16 | Inside GHMC (village values are city-wide averages) | -1.47 |
