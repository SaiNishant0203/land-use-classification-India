| Variable | Estimate | t stat | 2017-20 est. | t | 2020-23 est. | t |
|---|---|---|---|---|---|---|
| Constant | -3.248 | -9.11 | -3.312 | -7.27 | -3.254 | -8.68 |
| ***Land cover of the cell at t-1 (Base: open land)*** | | | | | | |
| Tree cover (vs open land) | -1.100 | -16.25 | -0.942 | -10.92 | -1.263 | -13.69 |
| ***Land use within 1 km (% by area) (Base: open land)*** | | | | | | |
| Residential | -0.012 | -5.10 | -0.016 | -4.55 | -0.009 | -3.02 |
| Non-residential | -0.005 | -2.18 | -0.007 | -2.08 | -0.004 | -1.62 |
| Water | -0.049 | -4.41 | -0.060 | -4.64 | -0.037 | -2.30 |
| Trees | -0.044 | -11.41 | -0.046 | -8.87 | -0.043 | -9.28 |
| Land-use mix (entropy, 0-1) | 3.402 | 15.82 | 3.923 | 12.68 | 2.945 | 11.70 |
| ***Urban form*** | | | | | | |
| Ln(km to the dense city, 1 km built share >= 40%) | -0.264 | -7.10 | -0.270 | -5.59 | -0.258 | -5.59 |
| ***Accessibility*** | | | | | | |
| Ln(km to the old CBD) | -0.806 | -7.25 | -0.821 | -5.90 | -0.782 | -6.72 |
| Ln(km to the nearest ORR interchange) | -0.255 | -6.51 | -0.273 | -6.28 | -0.240 | -5.26 |
| Ln(km to the nearest major road) | -0.154 | -5.15 | -0.128 | -3.58 | -0.182 | -5.05 |
| ***Supply constraints*** | | | | | | |
| Slope (degrees) | -0.055 | -5.50 | -0.049 | -3.68 | -0.059 | -4.33 |
| Relief within 150 m (m) | -0.052 | -3.15 | -0.062 | -3.01 | -0.042 | -1.92 |
| Ln(km to a lake >= 2 ha) | 0.087 | 2.16 | 0.057 | 1.09 | 0.113 | 2.56 |
| Within 100 m of a lake | -1.101 | -10.81 | -1.303 | -9.19 | -0.914 | -7.53 |
| Military, forest, protected or airport land | -0.994 | -3.75 | -1.077 | -3.37 | -0.903 | -2.97 |
| ***District (Base: Rangareddy)*** | | | | | | |
| Medak | 0.256 | 2.56 | 0.270 | 2.11 | 0.246 | 2.30 |
| Nalgonda | -0.186 | -1.32 | -0.090 | -0.62 | -0.260 | -1.35 |
| Mahabubnagar | 0.252 | 1.55 | 0.561 | 2.48 | -0.051 | -0.33 |
| Hyderabad | -0.999 | -4.75 | -0.823 | -3.51 | -1.171 | -5.27 |
| ***Period (Base: 2017-2020)*** | | | | | | |
| 2020-2023 | -0.031 | -0.84 | -- | -- | -- | -- |

| | pooled | 2017-20 | 2020-23 |
|---|---|---|---|
| cells | 120,000 | 60,000 | 60,000 |
| changes | 12,314 | 6,034 | 6,280 |
| parameters | 21 | 20 | 20 |
| log-likelihood, constant only | -39,695.4 | -19,579.6 | -20,113.0 |
| log-likelihood at convergence | -30,440.8 | -14,750.4 | -15,632.8 |
| rho-squared (vs constant only) | 0.233 | 0.247 | 0.223 |
| adjusted rho-squared | 0.233 | 0.246 | 0.222 |
| AUC, 5-fold cross-validated by 4 km tile | 0.839 | 0.845 | 0.836 |

Eliminated jointly: robust Wald chi2 = 11.0 on 8 df, p = 0.20

| step | eliminated | t when eliminated |
|---|---|---|
| 1 | Ln(km to the nearest open metro station) | 0.23 |
| 2 | Ln(km to the airport) | 0.56 |
| 3 | Ln(km to HITEC City / Financial District) | -0.90 |
| 4 | Ln(WorldPop people per km2) | 1.06 |
| 5 | GO 111 zone (within 10 km of Osman / Himayat Sagar) | 1.66 |
| 6 | Road mileage in the 4 km x 4 km window (10 km) | 1.34 |
| 7 | Ln(night lights within 1 km) | -1.05 |
| 8 | Elevation (100 m) | 1.55 |
