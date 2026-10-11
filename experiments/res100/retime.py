"""Re-time fit and whole-map cost for the current LU_CELL next to the 10 m reference, in one session
(use when a run was slowed by other load). Writes results/r<CELL>/cost_retimed.csv."""
import sys, time, pickle
import numpy as np, pandas as pd
from common import *
import features_coarse as FC
from run_experiment import fit

z = np.load(WORK / "cv.npz", allow_pickle=True)
names = list(z["names"]); X = np.load(WORK / "X_U.npy", mmap_mode="r")
pos = np.nonzero(z["in_rows"])[0]; y = z["maj"][pos]
grid = FC.open_grid(); ny = grid["meta"]["ny"]
Xr = np.asarray(X[pos])
out = []
for s, cols in (("ALL", list(range(len(names)))), ("PHYS", [i for i, n in enumerate(names) if not FC.is_aef(n)])):
    _, dt = fit(Xr[:, cols], y); out.append({"model": f"{CELL} m {s}", "metric": "fit_s", "value": dt, "train_rows": len(pos)})
m, _ = pickle.load(open(WORK / "model_ALL.pkl", "rb"))
tf = tp = 0.0; ncell = 0
for r0, r1 in FC.strips(ny):
    t = time.time(); gs, off = FC.load_strip(grid, r0, r1); nm, F = FC.compute(gs)
    v = gs["valid"][off:off + (r1 - r0)]
    Xm = np.stack([F[n][off:off + (r1 - r0)][v] for n in nm], 1); tf += time.time() - t
    t = time.time(); m.predict(Xm); tp += time.time() - t; ncell += len(Xm)
out.append({"model": f"{CELL} m ALL", "metric": "map_features_s", "value": tf, "train_rows": ncell})
out.append({"model": f"{CELL} m ALL", "metric": "map_predict_s", "value": tp, "train_rows": ncell})
log(f"{CELL} m map: {ncell:,} cells, features {tf:.0f}s + predict {tp:.0f}s")

sys.path.insert(0, str(REPO / "scripts" / "lu"))
import lu_features as LF
LF.LURAW = DATA
S = pd.concat([pd.read_parquet(p) for p in sorted((LUP / "samples_parts").glob("samples_part*.parquet"))], ignore_index=True)
m10, cols10 = pickle.load(open(LUP / "model_all_2023.pkl", "rb"))
_, t10 = fit(S[cols10], S.label.values)
phys10 = [c for c in cols10 if not FC.is_aef(c)]
_, t10p = fit(S[phys10], S.label.values)
k = "x228_y1920"; ts = []
for _ in range(3):
    t0 = time.time(); nm, arr = LF.compute(k); a = time.time() - t0
    t0 = time.time(); m10.predict(pd.DataFrame(arr.reshape(len(nm), -1).T, columns=nm)[cols10]); ts.append((a, time.time() - t0))
a, b = np.median([t[0] for t in ts]), np.median([t[1] for t in ts])
n_tiles = len(LF.tiles())
out += [{"model": "10 m ALL", "metric": "fit_s", "value": t10, "train_rows": len(S)},
        {"model": "10 m PHYS", "metric": "fit_s", "value": t10p, "train_rows": len(S)},
        {"model": "10 m ALL", "metric": "map_features_s", "value": a * n_tiles, "train_rows": n_tiles * 160000},
        {"model": "10 m ALL", "metric": "map_predict_s", "value": b * n_tiles, "train_rows": n_tiles * 160000}]
pd.DataFrame(out).to_csv(OUT / "cost_retimed.csv", index=False)
log("\n" + pd.DataFrame(out).round(1).to_string(index=False))
