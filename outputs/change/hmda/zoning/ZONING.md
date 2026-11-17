Zoning: HMDA Master Plan 2031 (approved 2013), read from all 30 district sheets; base = conservation (agriculture).

## 1. Development rate by zone (% of open land per 3 years, population scale)

| zone | 2017-20 cells | changes | rate | 2020-23 cells | changes | rate |
|---|---|---|---|---|---|---|
| residential zone | 7,381 | 818 | 0.26% | 7,757 | 1,025 | 0.30% |
| peri-urban zone | 3,331 | 166 | 0.11% | 3,323 | 191 | 0.12% |
| commercial / multiple-use zone | 2,901 | 618 | 0.57% | 2,990 | 725 | 0.63% |
| manufacturing zone | 1,817 | 276 | 0.38% | 1,881 | 281 | 0.35% |
| public / semi-public zone | 849 | 84 | 0.23% | 807 | 77 | 0.21% |
| protected green / water / special | 7,330 | 165 | 0.05% | 6,819 | 184 | 0.06% |
| GO 111 bio-conservation zone | 2,718 | 244 | 0.21% | 2,881 | 380 | 0.30% |
| not covered by the 2031 sheets | 15,057 | 3,133 | 0.55% | 14,452 | 2,680 | 0.45% |
| conservation (agriculture), base | 18,616 | 530 | 0.06% | 19,090 | 737 | 0.08% |

## 2. Zone dummies added to the final specification

| sample | zone | share of cells | estimate | t | odds ratio [95%] |
|---|---|---|---|---|---|
| pooled | residential zone | 12.6% | 0.568 | 5.69 | 1.76 [1.45, 2.15] |
| pooled | peri-urban zone | 5.5% | 0.122 | 0.99 | 1.13 [0.89, 1.44] |
| pooled | commercial / multiple-use zone | 4.9% | 0.403 | 3.32 | 1.50 [1.18, 1.90] |
| pooled | manufacturing zone | 3.1% | 1.096 | 8.40 | 2.99 [2.32, 3.86] |
| pooled | public / semi-public zone | 1.4% | 0.569 | 3.90 | 1.77 [1.33, 2.35] |
| pooled | protected green / water / special | 11.8% | -0.402 | -3.67 | 0.67 [0.54, 0.83] |
| pooled | GO 111 bio-conservation zone | 4.7% | 0.522 | 4.37 | 1.69 [1.33, 2.13] |
| pooled | not covered by the 2031 sheets | 24.6% | 0.396 | 3.68 | 1.49 [1.20, 1.83] |
| 2017-2020 | residential zone | 12.3% | 0.652 | 5.10 | 1.92 [1.49, 2.47] |
| 2017-2020 | peri-urban zone | 5.6% | 0.200 | 1.33 | 1.22 [0.91, 1.64] |
| 2017-2020 | commercial / multiple-use zone | 4.8% | 0.539 | 3.36 | 1.71 [1.25, 2.35] |
| 2017-2020 | manufacturing zone | 3.0% | 1.274 | 8.32 | 3.57 [2.65, 4.83] |
| 2017-2020 | public / semi-public zone | 1.4% | 0.702 | 3.60 | 2.02 [1.38, 2.96] |
| 2017-2020 | protected green / water / special | 12.2% | -0.269 | -1.87 | 0.76 [0.58, 1.01] |
| 2017-2020 | GO 111 bio-conservation zone | 4.5% | 0.542 | 4.10 | 1.72 [1.33, 2.23] |
| 2017-2020 | not covered by the 2031 sheets | 25.1% | 0.605 | 4.83 | 1.83 [1.43, 2.34] |
| 2020-2023 | residential zone | 12.9% | 0.497 | 4.44 | 1.64 [1.32, 2.05] |
| 2020-2023 | peri-urban zone | 5.5% | 0.065 | 0.46 | 1.07 [0.81, 1.41] |
| 2020-2023 | commercial / multiple-use zone | 5.0% | 0.289 | 2.15 | 1.34 [1.03, 1.74] |
| 2020-2023 | manufacturing zone | 3.1% | 0.941 | 5.50 | 2.56 [1.83, 3.58] |
| 2020-2023 | public / semi-public zone | 1.3% | 0.453 | 2.26 | 1.57 [1.06, 2.33] |
| 2020-2023 | protected green / water / special | 11.4% | -0.511 | -3.81 | 0.60 [0.46, 0.78] |
| 2020-2023 | GO 111 bio-conservation zone | 4.8% | 0.489 | 3.49 | 1.63 [1.24, 2.15] |
| 2020-2023 | not covered by the 2031 sheets | 24.1% | 0.203 | 1.64 | 1.22 [0.96, 1.56] |

| sample | zones jointly (robust Wald) | rho2 gain | AUC gain (base) |
|---|---|---|---|
| pooled | chi2 184.8 on 8 df, p = 1e-35 | 0.0077 | +0.0038 (0.841) |
| 2017-2020 | chi2 128.5 on 8 df, p = 5.7e-24 | 0.0086 | +0.0040 (0.847) |
| 2020-2023 | chi2 108.2 on 8 df, p = 9e-20 | 0.0073 | +0.0031 (0.837) |

## 3. Backward elimination from every candidate plus the zone dummies

- residential zone: **kept**, estimate 0.548, t 6.15
- peri-urban zone: eliminated
- commercial / multiple-use zone: **kept**, estimate 0.389, t 3.27
- manufacturing zone: **kept**, estimate 1.081, t 8.74
- public / semi-public zone: **kept**, estimate 0.545, t 3.86
- protected green / water / special: **kept**, estimate -0.424, t -4.02
- GO 111 bio-conservation zone: **kept**, estimate 0.516, t 4.35
- not covered by the 2031 sheets: **kept**, estimate 0.377, t 3.61
- kept overall: 25 variables; rho2 0.244, AUC 0.845
