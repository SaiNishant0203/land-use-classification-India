"""Merge results/r20, r50, r100 into results/scores.csv, paired_differences.csv, cost.csv."""
import pandas as pd
from common import HERE

R = HERE / "results"
S, D = [], []
for r in (20, 50, 100):
    s = pd.read_csv(R / f"r{r}" / "scores.csv"); s.insert(0, "cell_m", r); S.append(s)
    d = pd.read_csv(R / f"r{r}" / "paired_differences.csv"); d.insert(0, "cell_m", r); D.append(d)
S = pd.concat(S)
ten = S[S.model.str.startswith("10 m")].drop_duplicates(["experiment", "model", "subset"]).assign(cell_m=10)   # identical in every run
S = pd.concat([ten, S[~S.model.str.startswith("10 m")]]).sort_values(["experiment", "subset", "cell_m", "model"])
S.to_csv(R / "scores.csv", index=False)
pd.concat(D).to_csv(R / "paired_differences.csv", index=False)

C = []
for r in (20, 50, 100):
    f = R / f"r{r}" / ("cost_retimed.csv" if (R / f"r{r}" / "cost_retimed.csv").exists() else "cost.csv")
    c = pd.read_csv(f)
    if "metric" in c:                                      # retimed format -> same columns as cost.csv
        p = c.pivot_table(index="model", columns="metric", values="value", aggfunc="first")
        rows = c.drop_duplicates("model").set_index("model")["train_rows"]
        c = pd.DataFrame({"model": p.index, "fit_s": p["fit_s"].values,
                          "map_s_estimate": (p.get("map_features_s", 0).fillna(0) + p.get("map_predict_s", 0).fillna(0)).replace(0, float("nan")).values})
    c = c[["model", "fit_s", "map_s_estimate"]].copy()
    c.insert(0, "cell_m", r); c.insert(1, "source", f.name); C.append(c)
C = pd.concat(C, ignore_index=True)
ref = C[C.model == "10 m ALL"].set_index(["cell_m", "source"])[["fit_s", "map_s_estimate"]]
C = C.join(ref.rename(columns={"fit_s": "ten_m_fit_s_same_run", "map_s_estimate": "ten_m_map_s_same_run"}), on=["cell_m", "source"])
C["map_speedup_vs_10m"] = C.ten_m_map_s_same_run / C.map_s_estimate
C["fit_speedup_vs_10m"] = C.ten_m_fit_s_same_run / C.fit_s
C.to_csv(R / "cost.csv", index=False)
print(C[~C.model.str.startswith("10 m")].round(2).to_string(index=False))
print("merged", len(S), "score rows")
