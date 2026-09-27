"""
Our model, version 2: a U-Net (ResNet-34 encoder, ImageNet-initialised, first conv adapted to
76 input bands) trained on the same OSM labels, on the Intel Arc GPU (torch.xpu).
Unlike the pixel LightGBM it sees spatial layout (block shapes, road grain, building
arrangement) inside a 1.28 km window.

Fair comparison with LightGBM: identical spatial split. The test blocks are fold 0 of the
same GroupKFold over 12 km blocks that 06_train_eval.py uses, and both models are scored on
the same held-out sample pixels (06's out-of-fold LightGBM predictions on those pixels
come from a model that never saw those blocks either).

Run with .venv-xpu. Outputs: outputs/lu/unet_vs_lgbm.csv, data/raw/lu/unet_2023/<tile>.tif
"""
import sys, time
from pathlib import Path
import numpy as np, pandas as pd, rasterio, torch, torch.nn as nn
import segmentation_models_pytorch as smp
from rasterio.transform import from_origin
from sklearn.model_selection import GroupKFold
from sklearn.metrics import f1_score

sys.path.insert(0, str(Path(__file__).parent))
from lu_common import LU, LURAW, LUOUT, BANDS, log
import lu_features as F

CROP, BATCH, CROPS_PER_TILE = 128, 16, 6
EPOCHS = int(sys.argv[1]) if len(sys.argv) > 1 else 20
DEV = "xpu" if torch.xpu.is_available() else "cpu"
OUT = LURAW / "unet_2023"; OUT.mkdir(exist_ok=True)


def block_of(k):
    x, y = k[1:].split("_y")
    return f"{int(x) // 12}_{int(y) // 12}"


def split():
    s = pd.read_parquet(LU / "samples.parquet")
    s["block"] = s.tile.map(block_of)
    folds = list(GroupKFold(n_splits=min(5, s.block.nunique())).split(s, s.label, s.block))
    test_blocks = set(s.block.iloc[folds[0][1]])
    return s, test_blocks


def load_tile(k):
    with rasterio.open(LURAW / "feat_2023" / f"{k}.tif") as r:
        x = r.read()
    with rasterio.open(LURAW / "lab" / f"{k}.tif") as r:
        y = r.read(1)
    return x, y


def main():
    s, test_blocks = split()
    T = F.tiles()
    have = [k for k in T if (LURAW / "feat_2023" / f"{k}.tif").exists() and (LURAW / "lab" / f"{k}.tif").exists()]
    train = [k for k in have if block_of(k) not in test_blocks]
    test = [k for k in have if block_of(k) in test_blocks]
    log(f"device {DEV}; {len(train)} train tiles, {len(test)} test tiles, test blocks {sorted(test_blocks)}")

    cache = {k: load_tile(k) for k in train}
    sub = np.stack([cache[k][0][:, ::8, ::8] for k in train[:: max(1, len(train) // 60)]]).astype(np.float32)
    mean = sub.mean((0, 2, 3)); std = sub.std((0, 2, 3)) + 1e-3
    np.save(LU / "unet_norm.npy", np.stack([mean, std]))
    counts = np.bincount(np.concatenate([cache[k][1].ravel() for k in train]), minlength=6)[1:6].astype(float)
    w = torch.tensor((counts.sum() / (5 * np.maximum(counts, 1))) ** 0.5, dtype=torch.float32, device=DEV)
    log(f"label pixels per class {counts.astype(int).tolist()}, loss weights {w.cpu().numpy().round(2).tolist()}")

    net = smp.Unet("resnet34", encoder_weights="imagenet", in_channels=len(BANDS), classes=5).to(DEV)
    opt = torch.optim.AdamW(net.parameters(), lr=1e-3, weight_decay=1e-4)
    steps = EPOCHS * len(train) * CROPS_PER_TILE // BATCH
    sched = torch.optim.lr_scheduler.OneCycleLR(opt, max_lr=1e-3, total_steps=steps)
    lossf = nn.CrossEntropyLoss(weight=w, ignore_index=255)
    mt = torch.tensor(mean, device=DEV)[None, :, None, None]; st = torch.tensor(std, device=DEV)[None, :, None, None]
    rng = np.random.default_rng(0)

    def batches():
        order = [k for k in train for _ in range(CROPS_PER_TILE)]
        rng.shuffle(order)
        for i in range(0, len(order) - BATCH + 1, BATCH):
            X, Y = [], []
            for k in order[i:i + BATCH]:
                x, y = cache[k]
                r, c = rng.integers(0, 400 - CROP, 2)
                xx, yy = x[:, r:r + CROP, c:c + CROP], y[r:r + CROP, c:c + CROP].astype(np.int64) - 1
                yy[yy < 0] = 255
                if rng.random() < .5: xx, yy = xx[:, :, ::-1], yy[:, ::-1]
                if rng.random() < .5: xx, yy = xx[:, ::-1], yy[::-1]
                X.append(np.ascontiguousarray(xx)); Y.append(np.ascontiguousarray(yy))
            yield torch.from_numpy(np.stack(X).astype(np.float32)), torch.from_numpy(np.stack(Y))

    for ep in range(EPOCHS):
        net.train(); t0 = time.time(); tot = n = 0
        for X, Y in batches():
            X = (X.to(DEV) - mt) / st; Y = Y.to(DEV)
            with torch.autocast(device_type=DEV, dtype=torch.bfloat16):
                loss = lossf(net(X).float(), Y)
            opt.zero_grad(); loss.backward(); opt.step(); sched.step()
            tot += loss.item(); n += 1
        log(f"  epoch {ep + 1}/{EPOCHS} loss {tot / max(n, 1):.4f} ({time.time() - t0:.0f}s)")
    torch.save(net.state_dict(), LU / "unet_2023.pt")

    # predict test tiles with neighbour context (480 px padded window -> centre 400)
    net.eval(); del cache
    for k in test:
        x = F.read_padded(k).astype(np.float32)
        with torch.no_grad(), torch.autocast(device_type=DEV, dtype=torch.bfloat16):
            p = net((torch.from_numpy(x[None]).to(DEV) - mt) / st).float().softmax(1)[0].cpu().numpy()
        cls = (p.argmax(0) + 1)[F.PAD:F.PAD + 400, F.PAD:F.PAD + 400].astype(np.uint8)
        minx, miny, maxx, maxy = T[k]
        with rasterio.open(OUT / f"{k}.tif", "w", driver="GTiff", width=400, height=400, count=1, dtype="uint8",
                           crs="EPSG:32644", transform=from_origin(minx, maxy, 10, 10), compress="deflate") as d:
            d.write(cls, 1)

    # score both models on the same held-out sample pixels
    te = s[s.block.isin(test_blocks)].copy()
    te["unet"] = 0
    for k, idx in te.groupby("tile").groups.items():
        fp = OUT / f"{k}.tif"
        if fp.exists():
            with rasterio.open(fp) as r:
                a = r.read(1)
            te.loc[idx, "unet"] = a[te.loc[idx, "row"].values, te.loc[idx, "col"].values]
    oof = pd.read_parquet(LU / "oof_predictions.parquet")
    te = te.merge(oof[["tile", "x", "y", "oof_ALL"]], on=["tile", "x", "y"], how="left")
    rows = []
    for name, col in [("LightGBM pixel [ALL]", "oof_ALL"), ("U-Net ResNet-34", "unet")]:
        ok = te[col].notna() & (te[col] > 0)
        yv, pv = te.label[ok].values, te[col][ok].astype(int).values
        b = np.isin(yv, [1, 2]) & np.isin(pv, [1, 2])
        rows.append({"model": name, "n": int(ok.sum()),
                     "macro_f1": f1_score(yv, pv, labels=[1, 2, 3, 4, 5], average="macro"),
                     **{f"f1_{c}": f1_score(yv, pv, labels=[c], average="macro") for c in range(1, 6)},
                     "resnonres_macro_f1": f1_score(yv[b], pv[b], labels=[1, 2], average="macro")})
    out = pd.DataFrame(rows)
    out.to_csv(LUOUT / "unet_vs_lgbm.csv", index=False)
    log("\n" + out.round(3).to_string(index=False))


if __name__ == "__main__":
    main()
