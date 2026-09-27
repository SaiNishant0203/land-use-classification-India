"""
Land-use CHANGE for 2 x 2 km windows (the project's original question): the same 2023-trained
model applied to each year's own inputs. Every input exists per year (Sentinel-2, Open
Buildings 2.5D Temporal, AlphaEarth, VIIRS), so nothing from a later year leaks into an
earlier map. Open Buildings Temporal stops at 2023, so 2017 -> 2023 is the longest valid pair.

Stability check (the earlier AlphaEarth-only panel failed this): with a middle year (2020),
pixels that change 2017 -> 2020 and change BACK by 2023 are model noise, not land-use change.
Run with two models: ALL features, and S2+BLD (no AlphaEarth) as a robustness check.

Outputs (outputs/lu/change/): <site>_maps.png, change_areas.csv, change_transitions.csv,
change_stability.csv, change_morphology.csv
"""
import json, pickle, sys
from concurrent.futures import ThreadPoolExecutor, as_completed
import numpy as np, pandas as pd, rasterio, lightgbm as lgb
from pyproj import Transformer
from shapely.geometry import box
from lu_common import ee_init, base_stack, download_tile_parts, LU, LURAW, LUOUT, BANDS, log
import lu_features as F

SITES = {"Lingampally": (17.4930, 78.3170), "Gachibowli_FinancialDistrict": (17.4180, 78.3410)}
YEARS = [2017, 2020, 2023]
HALF = 1000                                                    # 2 x 2 km window
OUT = LUOUT / "change"; OUT.mkdir(exist_ok=True)
NAMES = {1: "residential", 2: "non-residential", 3: "water", 4: "forest/trees", 5: "other open"}
COLORS = {1: "#e8a33d", 2: "#c0392b", 3: "#2e86c1", 4: "#1e8449", 5: "#e5e1c9"}
to_utm = Transformer.from_crs(4326, 32644, always_xy=True)


def windows():
    out = {}
    for n, (lat, lon) in SITES.items():
        x, y = to_utm.transform(lon, lat)
        out[n] = (round(x, -1) - HALF, round(y, -1) - HALF, round(x, -1) + HALF, round(y, -1) + HALF)
    return out


def tiles_for(win):
    """Tiles intersecting the window, plus their neighbours (needed for neighbourhood features)."""
    T = F.tiles(); w = box(*win)
    core = [k for k, b in T.items() if box(*b).intersects(w)]
    return core, sorted({F.neighbour_key(k, dx, dy) for k in core for dx in (-1, 0, 1) for dy in (-1, 0, 1)} & set(T))


def download(years, W):
    ee = ee_init(); T = F.tiles()
    need = sorted({k for win in W.values() for k in tiles_for(win)[1]})
    for yr in years:
        d = LURAW / f"feat_{yr}"; d.mkdir(exist_ok=True)
        img = base_stack(ee, yr)
        todo = [k for k in need if not (d / f"{k}.tif").exists()]
        log(f"{yr}: {len(todo)} of {len(need)} tiles to download")
        with ThreadPoolExecutor(2) as ex:
            futs = {ex.submit(download_tile_parts, ee, img, box(*T[k]), d / f"{k}.tif"): k for k in todo}
            for f in as_completed(futs):
                f.result()


def models():
    m_all, cols_all = pickle.load(open(LU / "model_all_2023.pkl", "rb"))
    fp = LU / "model_s2bld_2023.pkl"
    if not fp.exists():
        s = pd.read_parquet(LU / "samples.parquet")
        cols = [c for c in cols_all if not (c.startswith("A") and c[1:3].isdigit())]
        m = lgb.LGBMClassifier(n_estimators=400, learning_rate=0.05, num_leaves=63, subsample=0.8,
                               subsample_freq=1, colsample_bytree=0.6, class_weight="balanced", n_jobs=14, verbose=-1)
        m.fit(s[cols], s.label.values)
        pickle.dump((m, cols), open(fp, "wb"))
    return {"ALL": (m_all, cols_all), "S2+BLD (no AlphaEarth)": pickle.load(open(fp, "rb"))}


def window_arrays(win, year, mdl):
    """Predicted class map, Sentinel-2 RGB and building layers cropped to the window."""
    T = F.tiles(); core, _ = tiles_for(win)
    n = int(2 * HALF / 10)
    cls = np.zeros((n, n), np.uint8); rgb = np.zeros((3, n, n), np.float32)
    cov = np.zeros((n, n), np.float32); hgt = np.zeros((n, n), np.float32)
    for k in core:
        names, arr = F.compute(k, folder=f"feat_{year}")
        X = pd.DataFrame(arr.reshape(len(names), -1).T, columns=names)[mdl[1]]
        p = mdl[0].predict(X).reshape(400, 400).astype(np.uint8)
        minx, miny, maxx, maxy = T[k]
        # overlap of tile and window in pixel coordinates (rows run north -> south)
        c0, c1 = int((max(minx, win[0]) - minx) / 10), int((min(maxx, win[2]) - minx) / 10)
        r0, r1 = int((maxy - min(maxy, win[3])) / 10), int((maxy - max(miny, win[1])) / 10)
        wc0 = int((max(minx, win[0]) - win[0]) / 10); wr0 = int((win[3] - min(maxy, win[3])) / 10)
        sl = (slice(wr0, wr0 + r1 - r0), slice(wc0, wc0 + c1 - c0))
        cls[sl] = p[r0:r1, c0:c1]
        for i, b in enumerate(["B4", "B3", "B2"]):
            rgb[i][sl] = arr[names.index(b), r0:r1, c0:c1]
        cov[sl] = arr[names.index("ob_cov"), r0:r1, c0:c1]
        hgt[sl] = arr[names.index("ob_h"), r0:r1, c0:c1]
    return cls, rgb, cov, hgt


def main():
    W = windows()
    if "--no-download" not in sys.argv:
        download([y for y in YEARS if y != 2023], W)
    M = models()
    areas, trans, stab, morph, maps = [], [], [], [], {}
    for site, win in W.items():
        for mname, mdl in M.items():
            per_year = {}
            for yr in YEARS:
                cls, rgb, cov, hgt = window_arrays(win, yr, mdl)
                per_year[yr] = cls
                maps[(site, mname, yr)] = (cls, rgb)
                for c in NAMES:
                    areas.append({"site": site, "model": mname, "year": yr, "class": NAMES[c],
                                  "hectares": float((cls == c).sum() / 100)})
                if mname == "ALL":
                    b = cov > 0
                    morph.append({"site": site, "year": yr, "building_cover_pct": float(100 * cov.mean()),
                                  "mean_height_m": float(hgt[b].mean()) if b.any() else 0.0,
                                  "built_volume_proxy_m3_per_m2": float((cov * hgt).mean())})
            a, m_, b = per_year[2017], per_year[2020], per_year[2023]
            stab.append({"site": site, "model": mname,
                         "changed_2017_2023_pct": 100 * float((a != b).mean()),
                         "changed_2017_2020_pct": 100 * float((a != m_).mean()),
                         "changed_2020_2023_pct": 100 * float((m_ != b).mean()),
                         "flip_flop_pct": 100 * float(((a != m_) & (a == b)).mean()),
                         "monotone_change_pct": 100 * float(((a != b) & ((m_ == a) | (m_ == b))).mean())})
            t = pd.crosstab(pd.Series(a.ravel(), name="2017").map(NAMES),
                            pd.Series(b.ravel(), name="2023").map(NAMES)) / 100
            t["site"], t["model"] = site, mname
            trans.append(t.reset_index())
    pd.DataFrame(areas).to_csv(OUT / "change_areas.csv", index=False)
    pd.concat(trans).to_csv(OUT / "change_transitions.csv", index=False)
    pd.DataFrame(stab).to_csv(OUT / "change_stability.csv", index=False)
    pd.DataFrame(morph).to_csv(OUT / "change_morphology.csv", index=False)
    log("\n" + pd.DataFrame(stab).round(1).to_string(index=False))
    log("\n" + pd.DataFrame(morph).round(2).to_string(index=False))
    plot(W, maps)


def plot(W, maps):
    import matplotlib; matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import ListedColormap
    from matplotlib.patches import Patch
    cm = ListedColormap(["#ffffff"] + [COLORS[c] for c in range(1, 6)])
    for site in W:
        fig, ax = plt.subplots(2, 4, figsize=(20, 10.5))
        for j, yr in enumerate(YEARS):
            cls, rgb = maps[(site, "ALL", yr)]
            img = np.clip(rgb.transpose(1, 2, 0) / 0.25, 0, 1)
            ax[0, j].imshow(img); ax[0, j].set_title(f"Sentinel-2 {yr}")
            ax[1, j].imshow(cls, cmap=cm, vmin=0, vmax=5, interpolation="nearest"); ax[1, j].set_title(f"Land use {yr}")
        a, b = maps[(site, "ALL", 2017)][0], maps[(site, "ALL", 2023)][0]
        ch = np.zeros(a.shape, np.uint8)
        ch[(a != b)] = 1                                             # other change
        ch[np.isin(a, [3, 4, 5]) & (b == 1)] = 2                     # open/green -> residential
        ch[np.isin(a, [3, 4, 5]) & (b == 2)] = 3                     # open/green -> non-residential
        ch[(a == 1) & (b == 2)] = 4                                  # residential -> non-residential
        ccm = ListedColormap(["#f2f2f2", "#9e9e9e", "#e8a33d", "#c0392b", "#7d3c98"])
        ax[0, 3].imshow(ch, cmap=ccm, vmin=0, vmax=4, interpolation="nearest"); ax[0, 3].set_title("Change 2017 -> 2023")
        ax[0, 3].legend(handles=[Patch(color=c, label=l) for c, l in zip(
            ["#f2f2f2", "#9e9e9e", "#e8a33d", "#c0392b", "#7d3c98"],
            ["no change", "other change", "open/green -> residential", "open/green -> non-residential",
             "residential -> non-residential"])], loc="lower left", fontsize=8)
        ax[1, 3].axis("off")
        ax[1, 3].legend(handles=[Patch(color=COLORS[c], label=NAMES[c]) for c in NAMES], loc="center", fontsize=12)
        for x in ax.ravel():
            x.set_xticks([]); x.set_yticks([])
        fig.suptitle(f"{site.replace('_', ' / ')}: 2 x 2 km, 10 m, same model applied to each year's own inputs", fontsize=14)
        fig.tight_layout(); fig.savefig(OUT / f"{site}_maps.png", dpi=110); plt.close(fig)


if __name__ == "__main__":
    main()
