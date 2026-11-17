Bus stops: 5,177 (current, TGSRTC via shift-transport.org). Median distance of a sampled cell to a stop 0.87 km; 8.8% of cells more than 5 km away.

## 1. Added to the final specification

| sample | added | factor | estimate | t | odds ratio [95%] | rho2 gain | AUC gain (base) |
|---|---|---|---|---|---|---|---|
| pooled | ln_d_bus | Ln(km to the nearest bus stop, current stops) | -0.148 | -6.23 | 1.11 [1.07, 1.14] per half as far | 0.0013 | +0.0002 (0.849) |
| pooled | bus_1km | Bus stops within 1 km (/10) | -0.321 | -5.05 | 0.73 [0.64, 0.82] per +10 stops | 0.0006 | +0.0001 (0.849) |
| pooled | ln_d_bus + bus_1km | Ln(km to the nearest bus stop, current stops) | -0.215 | -8.16 | 1.16 [1.12, 1.20] per half as far | 0.0029 | +0.0007 (0.849) |
| pooled | ln_d_bus + bus_1km | Bus stops within 1 km (/10) | -0.573 | -7.89 | 0.56 [0.49, 0.65] per +10 stops | 0.0029 | +0.0007 (0.849) |
| 2017-2020 | ln_d_bus | Ln(km to the nearest bus stop, current stops) | -0.177 | -6.13 | 1.13 [1.09, 1.18] per half as far | 0.0018 | +0.0004 (0.852) |
| 2017-2020 | bus_1km | Bus stops within 1 km (/10) | -0.286 | -3.45 | 0.75 [0.64, 0.88] per +10 stops | 0.0005 | +0.0001 (0.852) |
| 2017-2020 | ln_d_bus + bus_1km | Ln(km to the nearest bus stop, current stops) | -0.242 | -7.87 | 1.18 [1.13, 1.23] per half as far | 0.0034 | +0.0009 (0.852) |
| 2017-2020 | ln_d_bus + bus_1km | Bus stops within 1 km (/10) | -0.561 | -6.36 | 0.57 [0.48, 0.68] per +10 stops | 0.0034 | +0.0009 (0.852) |
| 2020-2023 | ln_d_bus | Ln(km to the nearest bus stop, current stops) | -0.125 | -4.85 | 1.09 [1.05, 1.13] per half as far | 0.0009 | -0.0001 (0.845) |
| 2020-2023 | bus_1km | Bus stops within 1 km (/10) | -0.357 | -5.09 | 0.70 [0.61, 0.80] per +10 stops | 0.0007 | +0.0002 (0.845) |
| 2020-2023 | ln_d_bus + bus_1km | Ln(km to the nearest bus stop, current stops) | -0.195 | -6.70 | 1.14 [1.10, 1.19] per half as far | 0.0027 | +0.0003 (0.845) |
| 2020-2023 | ln_d_bus + bus_1km | Bus stops within 1 km (/10) | -0.594 | -7.31 | 0.55 [0.47, 0.65] per +10 stops | 0.0027 | +0.0003 (0.845) |

## 2. Backward elimination from every candidate plus the bus factors

- Ln(km to the nearest bus stop, current stops): **kept**, estimate -0.222, t -8.53
- Bus stops within 1 km (/10): **kept**, estimate -0.606, t -8.35
- kept overall: 20 variables; rho2 0.295
