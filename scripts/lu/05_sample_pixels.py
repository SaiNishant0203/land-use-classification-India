"""
Sample labelled pixels from every tile that has features + products + labels, and attach
(a) our feature vector and (b) every existing product's value at that pixel, so the audit
of existing models and our own model are scored on exactly the same pixels.

Per tile: up to N_PER_CLASS random pixels of each class present. Also samples the same
pixels' GULU class from data/raw/lu/gulu/IND.tif (EPSG:3857 despite its broken CRS tag).

Output: data/processed/lu/samples/<tile>.parquet  (resumable), merged -> samples.parquet
"""
import sys
import numpy as np, pandas as pd, rasterio
from pyproj import Transformer
from lu_common import LU, LURAW, log
import lu_features as F

N_PER_CLASS = 200
PROD = ["dw", "wc", "jrc", "ghsc", "wri", "ind"]
OUT = LU / "samples"; OUT.mkdir(exist_ok=True)
to3857 = Transformer.from_crs(32644, 3857, always_xy=True)


def gulu_at(xs, ys):
    mx, my = to3857.transform(xs, ys)
    with rasterio.open(LURAW / "gulu" / "IND.tif") as s:
        return np.array([v[0] for v in s.sample(zip(mx, my))], np.uint8)


def one(k, rng):
    fp = OUT / f"{k}.parquet"
    if fp.exists():
        return
    with rasterio.open(LURAW / "lab" / f"{k}.tif") as s:
        lab = s.read(1); tr = s.transform
    idx = []
    for c in range(1, 6):
        r, cc = np.nonzero(lab == c)
        if len(r):
            j = rng.choice(len(r), size=min(N_PER_CLASS, len(r)), replace=False)
            idx.append(np.stack([r[j], cc[j]], 1))
    if not idx:
        pd.DataFrame().to_parquet(fp); return
    idx = np.concatenate(idx)
    names, arr = F.compute(k)
    X = arr[:, idx[:, 0], idx[:, 1]].T
    df = pd.DataFrame(X, columns=names)
    df["label"] = lab[idx[:, 0], idx[:, 1]]
    df["tile"] = k
    df["x"] = tr.c + (idx[:, 1] + 0.5) * 10
    df["y"] = tr.f - (idx[:, 0] + 0.5) * 10
    df["row"], df["col"] = idx[:, 0], idx[:, 1]
    with rasterio.open(LURAW / "prod" / f"{k}.tif") as s:
        P = s.read()
    for i, n in enumerate(PROD):
        df[f"p_{n}"] = P[i, idx[:, 0], idx[:, 1]]
    df["p_gulu"] = gulu_at(df.x.values, df.y.values)
    df.to_parquet(fp)


def main():
    rng = np.random.default_rng(7)
    T = F.tiles()
    have = lambda k: (LURAW / "feat_2023" / f"{k}.tif").exists()
    # neighbours must be present (or outside HMDA), else edge features would be zero-padded
    nb_ok = lambda k: all(have(n) or n not in T for n in
                          (F.neighbour_key(k, dx, dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1)))
    ready = [k for k in T if all((LURAW / d / f"{k}.tif").exists() for d in ("feat_2023", "prod", "lab"))
             and nb_ok(k)]
    todo = [k for k in ready if not (OUT / f"{k}.parquet").exists()]
    log(f"{len(ready)} tiles ready, {len(todo)} to sample")
    for i, k in enumerate(todo, 1):
        one(k, rng)
        if i % 25 == 0:
            log(f"  {i}/{len(todo)}")
    parts = [pd.read_parquet(p) for p in OUT.glob("*.parquet")]
    s = pd.concat([p for p in parts if len(p)], ignore_index=True)
    s.to_parquet(LU / "samples.parquet")
    log(f"samples: {len(s)} from {s.tile.nunique()} tiles\n{s.label.value_counts().sort_index().to_string()}")


if __name__ == "__main__":
    main()
