# Archived write-ups

These are the stage-by-stage write-ups of the land-use change work, written as the work went along. Their
results are all in **`DISCRETE_CHOICE_MODELS_REPORT.md`** at the repository root, which is the document to
read; §21 of that report says which of its sections each file here sits behind. They are kept because they
hold extra detail (full tables, elimination orders, side checks) that the report does not repeat.

They are kept **as written**, so paths and status notes inside them are as of the date they were written:
- paths like `outputs/change/hmda/HMDA_RESULTS.md` or `CHANGE_MODEL_PLAN.md` now point here;
- `CHANGE_MODEL_DEEP_DIVE.md` (cited in `HMDA_RESULTS.md`) and `VOTER_DATA_FEASIBILITY.md` (cited in the plan)
  were never in the repository.

| file | was at | what it is |
|---|---|---|
| `CHANGE_MODEL_PLAN_2026-11-02.md` | `CHANGE_MODEL_PLAN.md` | the original design of the change model (2 Nov), with a status note of 17 Nov. Its "~0.1% of open land per year" estimate was later found wrong (report §7) |
| `CHANGE_OVERVIEW_2026-11-17.md` | `outputs/change/README.md` | the one-page overview of the change model as of 17 Nov; `outputs/change/README.md` is now only a guide to the results folders |
| `CHOICE_MODEL_RESULTS_10m_Oct.md` | `CHOICE_MODEL_RESULTS.md` | the October 10 m transition / choice models (report §17) |
| `HMDA_RESULTS.md` | `outputs/change/hmda/` | all of HMDA, strict rule (report §6) |
| `PERSIST_RESULTS.md` | `outputs/change/hmda_persist/` | all of HMDA, persistence rule (report §7) |
| `trial/TRIAL_RESULTS.md` | `outputs/change/trial/` | trial C1: booth votes as population (report §18.1) |
| `trial/FULL_MODEL_RESULTS.md` | `outputs/change/trial/` | trial C2: full model and tests (report §18.2) |
| `trial/TABLE18_RESULTS.md` | `outputs/change/trial/` | trial C3: Table 18 without census (report §18.3) |
| `trial/TABLE18_CENSUS.md` | `outputs/change/trial/` | trial C4–C5: with jobs and census; the final trial table (report §18.4–18.5) |
| `change_trial_first_run/` | `experiments/change_trial/` | the very first trial run and its result tables, superseded by the `trial/` files |
| `EYEBALL_GUIDE_short.md` | `data/processed/change/EYEBALL_GUIDE.md` | an older short version of `EYEBALL_CHECK_HOWTO.md`. **Out of date:** it says "mostly N → strict rule"; the current plan is "mostly N → middle rule" |
