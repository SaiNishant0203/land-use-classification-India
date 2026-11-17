Bus stops: 5,177 (current, TGSRTC via shift-transport.org). Median distance of a sampled cell to a stop 1.12 km; 10.0% of cells more than 5 km away.

## 1. Added to the final specification

| sample | added | factor | estimate | t | odds ratio [95%] | rho2 gain | AUC gain (base) |
|---|---|---|---|---|---|---|---|
| pooled | ln_d_bus | Ln(km to the nearest bus stop, current stops) | -0.087 | -2.19 | 1.06 [1.01, 1.12] per half as far | 0.0003 | +0.0001 (0.841) |
| pooled | bus_1km | Bus stops within 1 km (/10) | -0.343 | -4.16 | 0.71 [0.60, 0.83] per +10 stops | 0.0008 | +0.0003 (0.841) |
| pooled | ln_d_bus + bus_1km | Ln(km to the nearest bus stop, current stops) | -0.161 | -3.75 | 1.12 [1.05, 1.19] per half as far | 0.0018 | +0.0009 (0.841) |
| pooled | ln_d_bus + bus_1km | Bus stops within 1 km (/10) | -0.488 | -5.32 | 0.61 [0.51, 0.73] per +10 stops | 0.0018 | +0.0009 (0.841) |
| 2017-2020 | ln_d_bus | Ln(km to the nearest bus stop, current stops) | -0.122 | -2.26 | 1.09 [1.01, 1.17] per half as far | 0.0006 | +0.0006 (0.847) |
| 2017-2020 | bus_1km | Bus stops within 1 km (/10) | -0.271 | -2.64 | 0.76 [0.62, 0.93] per +10 stops | 0.0005 | +0.0003 (0.847) |
| 2017-2020 | ln_d_bus + bus_1km | Ln(km to the nearest bus stop, current stops) | -0.188 | -3.20 | 1.14 [1.05, 1.23] per half as far | 0.0018 | +0.0013 (0.847) |
| 2017-2020 | ln_d_bus + bus_1km | Bus stops within 1 km (/10) | -0.432 | -3.78 | 0.65 [0.52, 0.81] per +10 stops | 0.0018 | +0.0013 (0.847) |
| 2020-2023 | ln_d_bus | Ln(km to the nearest bus stop, current stops) | -0.050 | -1.15 | 1.04 [0.98, 1.10] per half as far | 0.0001 | +0.0000 (0.837) |
| 2020-2023 | bus_1km | Bus stops within 1 km (/10) | -0.425 | -4.79 | 0.65 [0.55, 0.78] per +10 stops | 0.0013 | +0.0006 (0.837) |
| 2020-2023 | ln_d_bus + bus_1km | Ln(km to the nearest bus stop, current stops) | -0.134 | -2.90 | 1.10 [1.03, 1.17] per half as far | 0.0019 | +0.0010 (0.837) |
| 2020-2023 | ln_d_bus + bus_1km | Bus stops within 1 km (/10) | -0.552 | -5.80 | 0.58 [0.48, 0.69] per +10 stops | 0.0019 | +0.0010 (0.837) |

## 2. Backward elimination from every candidate plus the bus factors

- Ln(km to the nearest bus stop, current stops): **kept**, estimate -0.171, t -4.08
- Bus stops within 1 km (/10): **kept**, estimate -0.522, t -5.57
- kept overall: 19 variables; rho2 0.237
