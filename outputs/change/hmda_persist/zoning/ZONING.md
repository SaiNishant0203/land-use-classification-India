Zoning: HMDA Master Plan 2031 (approved 2013), read from all 30 district sheets; base = conservation (agriculture).

## 1. Development rate by zone (% of open land per 3 years, population scale)

| zone | 2017-20 cells | changes | rate | 2020-23 cells | changes | rate |
|---|---|---|---|---|---|---|
| residential zone | 8,345 | 4,028 | 1.83% | 8,490 | 4,695 | 1.92% |
| peri-urban zone | 2,837 | 848 | 0.84% | 2,943 | 1,052 | 0.87% |
| commercial / multiple-use zone | 3,435 | 1,960 | 2.59% | 3,737 | 2,398 | 2.76% |
| manufacturing zone | 2,050 | 1,070 | 2.13% | 2,059 | 1,134 | 1.91% |
| public / semi-public zone | 859 | 402 | 1.73% | 908 | 461 | 1.61% |
| protected green / water / special | 5,632 | 1,134 | 0.50% | 5,134 | 1,288 | 0.53% |
| GO 111 bio-conservation zone | 2,549 | 916 | 1.11% | 2,636 | 1,288 | 1.49% |
| not covered by the 2031 sheets | 19,655 | 12,057 | 3.07% | 19,317 | 12,624 | 2.90% |
| conservation (agriculture), base | 14,638 | 3,149 | 0.54% | 14,776 | 4,094 | 0.60% |

## 2. Zone dummies added to the final specification

| sample | zone | share of cells | estimate | t | odds ratio [95%] |
|---|---|---|---|---|---|
| pooled | residential zone | 14.0% | 0.362 | 7.32 | 1.44 [1.30, 1.58] |
| pooled | peri-urban zone | 4.8% | -0.023 | -0.41 | 0.98 [0.87, 1.09] |
| pooled | commercial / multiple-use zone | 6.0% | 0.212 | 2.95 | 1.24 [1.07, 1.42] |
| pooled | manufacturing zone | 3.4% | 0.586 | 6.12 | 1.80 [1.49, 2.17] |
| pooled | public / semi-public zone | 1.5% | 0.305 | 3.37 | 1.36 [1.14, 1.62] |
| pooled | protected green / water / special | 9.0% | -0.341 | -5.55 | 0.71 [0.63, 0.80] |
| pooled | GO 111 bio-conservation zone | 4.3% | 0.273 | 3.59 | 1.31 [1.13, 1.52] |
| pooled | not covered by the 2031 sheets | 32.5% | 0.145 | 2.61 | 1.16 [1.04, 1.29] |
| 2017-2020 | residential zone | 13.9% | 0.365 | 6.34 | 1.44 [1.29, 1.61] |
| 2017-2020 | peri-urban zone | 4.7% | -0.025 | -0.33 | 0.98 [0.84, 1.13] |
| 2017-2020 | commercial / multiple-use zone | 5.7% | 0.171 | 1.85 | 1.19 [0.99, 1.42] |
| 2017-2020 | manufacturing zone | 3.4% | 0.705 | 6.25 | 2.02 [1.62, 2.52] |
| 2017-2020 | public / semi-public zone | 1.4% | 0.304 | 2.77 | 1.36 [1.09, 1.68] |
| 2017-2020 | protected green / water / special | 9.4% | -0.339 | -4.74 | 0.71 [0.62, 0.82] |
| 2017-2020 | GO 111 bio-conservation zone | 4.2% | 0.197 | 2.41 | 1.22 [1.04, 1.43] |
| 2017-2020 | not covered by the 2031 sheets | 32.8% | 0.210 | 3.24 | 1.23 [1.09, 1.40] |
| 2020-2023 | residential zone | 14.1% | 0.364 | 6.17 | 1.44 [1.28, 1.61] |
| 2020-2023 | peri-urban zone | 4.9% | -0.025 | -0.38 | 0.98 [0.86, 1.11] |
| 2020-2023 | commercial / multiple-use zone | 6.2% | 0.254 | 2.95 | 1.29 [1.09, 1.53] |
| 2020-2023 | manufacturing zone | 3.4% | 0.452 | 4.14 | 1.57 [1.27, 1.95] |
| 2020-2023 | public / semi-public zone | 1.5% | 0.298 | 2.61 | 1.35 [1.08, 1.68] |
| 2020-2023 | protected green / water / special | 8.6% | -0.347 | -4.91 | 0.71 [0.62, 0.81] |
| 2020-2023 | GO 111 bio-conservation zone | 4.4% | 0.351 | 3.88 | 1.42 [1.19, 1.70] |
| 2020-2023 | not covered by the 2031 sheets | 32.2% | 0.062 | 0.95 | 1.06 [0.94, 1.21] |

| sample | zones jointly (robust Wald) | rho2 gain | AUC gain (base) |
|---|---|---|---|
| pooled | chi2 172.9 on 8 df, p = 3.2e-33 | 0.0042 | +0.0012 (0.849) |
| 2017-2020 | chi2 128.4 on 8 df, p = 6.1e-24 | 0.0046 | +0.0012 (0.852) |
| 2020-2023 | chi2 139.8 on 8 df, p = 2.6e-26 | 0.0042 | +0.0006 (0.845) |

## 3. Backward elimination from every candidate plus the zone dummies

- residential zone: **kept**, estimate 0.413, t 8.99
- peri-urban zone: eliminated
- commercial / multiple-use zone: **kept**, estimate 0.262, t 3.65
- manufacturing zone: **kept**, estimate 0.617, t 6.49
- public / semi-public zone: **kept**, estimate 0.341, t 3.80
- protected green / water / special: **kept**, estimate -0.313, t -5.13
- GO 111 bio-conservation zone: **kept**, estimate 0.319, t 4.28
- not covered by the 2031 sheets: **kept**, estimate 0.136, t 2.28
- kept overall: 26 variables; rho2 0.297, AUC 0.850
