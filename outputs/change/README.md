# Change-model results: what is in each folder

The write-up of these results is **`DISCRETE_CHOICE_MODELS_REPORT.md`** at the repository root. This file
only says where each result lives. Everything here is written by `scripts/change/` and is overwritten on a
rerun; the run IDs (C1, D1, …) are those of the report's run register (§15).

| folder | run | report |
|---|---|---|
| `trial/` (`coefs.csv`, `fit.csv`, `checks.csv`, `rates.csv`) | C1: trial, 3 constituencies, base model ± booth votes / WorldPop | §18.1 |
| `trial/full/` | C2: trial, full 25-factor model and tests | §18.2 |
| `trial/table18/` | C3: trial, Table 18 without census | §18.3 |
| `trial/table18_census/` | C4: trial, Table 18 with jobs and census | §18.4 |
| `trial/table18_florida/` | C5: trial, Florida-style (the final trial table) | §18.5 |
| `hmda/table18_census/` | **D1: all of HMDA, strict rule, main table** | §6.2 |
| `hmda/table18_florida/`, `hmda/table18/` | D2: Florida-style and no-census variants | §6.4 |
| `hmda/consistency/` | D3: refits on five subregions | §6.5 |
| `hmda/full/` | D4: full 25-factor model and tests | §6.6 |
| `hmda_persist/table18_census/` | **E1: all of HMDA, persistence rule, main table** | §7.2 |
| `hmda_persist/table18_florida/`, `table18/`, `consistency/`, `full/` | the same variants and tests under the persistence rule | §7 |
| `hmda*/added_value/` | F: how much each group of factors adds | §8 |
| `hmda*/bus_stops/` | G: bus-stop factors | §9 |
| `hmda*/zoning/` | H: Master Plan 2031 zone dummies | §10 |

Each `table18*/` folder has `table18.csv` (the table), `elimination.csv` (the elimination order), `fit.csv`
and a generated `TABLE18.md`. The `full/` folders have `coefs.csv`, `effects.csv`, `groups.csv`, `checks.csv`
and `calibration.csv`.

**The samples behind every run** are in `data/processed/change/` (`trial_cells_*`, `hmda_cells_*`,
`hmda_persist_cells_*`; `_full` without and `_census` with the Economic Census and Census 2011 factors).
The commands to rerun everything are in §19 of the report; the pipeline and its switches (`REGION`,
`OUTCOME`) are in `scripts/change/README.md`.
