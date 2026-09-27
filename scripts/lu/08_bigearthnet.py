"""
Zero-shot BigEarthNet v2.0 (reBEN) ResNet-50 on Hyderabad. No training: Europe-trained weights
from Hugging Face (BIFOLD-BigEarthNetv2-0/resnet50-s2-v0.2.0), used exactly as published.

Input: 120 x 120 px (1.2 km) patches, 10 bands in reBEN order B02 B03 B04 B05 B06 B07 B08 B8A
B11 B12, L2A reflectance normalised with the published BENv2 '120_nearest' mean/std.
Sliding window, stride 40 px: each patch's prediction is assigned to its central 40 x 40 px
(400 m) block, so every 10 m pixel gets the prediction of the patch centred on its block.

19 CORINE classes -> our 5 classes, picking the group with the highest max-probability:
  residential      Urban fabric
  non-residential  Industrial or commercial units
  water            Inland waters, Marine waters
  forest/trees     Broad-leaved / Coniferous / Mixed forest, Agro-forestry, Transitional woodland-shrub
  other open       every agricultural, grassland, heath, beach and wetland class

Run with .venv-xpu (Intel Arc via torch.xpu). Output: data/raw/lu/ben/<tile>.tif (uint8 class)
and data/raw/lu/ben/<tile>_prob.npy (10 x 10 x 19 sigmoid scores).
"""
import sys
from pathlib import Path
import numpy as np, torch, timm, rasterio
from rasterio.transform import from_origin
from safetensors.torch import load_file

sys.path.insert(0, str(Path(__file__).parent))
import lu_features as F
from lu_common import LURAW, BANDS, log

MODEL_DIR = LURAW / "models" / "ben_resnet50"
OUT = LURAW / "ben"; OUT.mkdir(exist_ok=True)
ORDER = ["B02", "B03", "B04", "B05", "B06", "B07", "B08", "B8A", "B11", "B12"]
LABELS_ORIG = ["Urban fabric", "Industrial or commercial units", "Arable land", "Permanent crops", "Pastures",
               "Complex cultivation patterns",
               "Land principally occupied by agriculture, with significant areas of natural vegetation",
               "Agro-forestry areas", "Broad-leaved forest", "Coniferous forest", "Mixed forest",
               "Natural grassland and sparsely vegetated areas", "Moors, heathland and sclerophyllous vegetation",
               "Transitional woodland, shrub", "Beaches, dunes, sands", "Inland wetlands", "Coastal wetlands",
               "Inland waters", "Marine waters"]
LABELS = sorted(LABELS_ORIG)                      # model output order (configilm NEW_LABELS)
GROUP = {"Urban fabric": 1, "Industrial or commercial units": 2, "Inland waters": 3, "Marine waters": 3,
         "Broad-leaved forest": 4, "Coniferous forest": 4, "Mixed forest": 4, "Agro-forestry areas": 4,
         "Transitional woodland, shrub": 4}
GROUP_IDX = np.array([GROUP.get(l, 5) for l in LABELS])


def stats():
    import re
    src = (Path(sys.prefix) / "Lib/site-packages/configilm/extra/BENv2_utils.py").read_text()
    out = []
    for name in ("means", "stds"):
        blk = src[src.index(f"{name} = {{"):]
        blk = blk[blk.index('"120_nearest"'):]
        blk = blk[:blk.index("}")]
        d = dict(re.findall(r'"(\w+)": ([-\d.e]+)', blk))
        out.append(np.array([float(d[b]) for b in ORDER], np.float32))
    return out


def model(dev):
    m = timm.create_model("resnet50", pretrained=False, in_chans=10, num_classes=19)
    sd = {k.replace("model.vision_encoder.", ""): v for k, v in load_file(MODEL_DIR / "model.safetensors").items()}
    missing, unexpected = m.load_state_dict(sd, strict=False)
    assert not missing, missing
    return m.eval().to(dev)


def tile_patches(k, mean, std):
    f = F.read_padded(k).astype(np.float32)                       # feat bands, padded 480 x 480
    x = F.read_padded(k, folder="s2x_2023", nb=3).astype(np.float32)
    b = {"B02": f[BANDS.index("B2")], "B03": f[BANDS.index("B3")], "B04": f[BANDS.index("B4")],
         "B05": f[BANDS.index("B5")], "B06": x[0], "B07": x[1], "B08": f[BANDS.index("B8")],
         "B8A": x[2], "B11": f[BANDS.index("B11")], "B12": f[BANDS.index("B12")]}
    img = (np.stack([b[o] for o in ORDER]) - mean[:, None, None]) / std[:, None, None]
    return np.stack([img[:, 40 * i:40 * i + 120, 40 * j:40 * j + 120] for i in range(10) for j in range(10)])


def main():
    dev = "xpu" if torch.xpu.is_available() else "cpu"
    mean, std = stats()
    net = model(dev)
    T = F.tiles()
    have = lambda k, d: (LURAW / d / f"{k}.tif").exists()
    todo = [k for k in T if have(k, "feat_2023") and have(k, "s2x_2023") and not (OUT / f"{k}.tif").exists()
            and all((have(n, "feat_2023") and have(n, "s2x_2023")) or n not in T
                    for n in (F.neighbour_key(k, dx, dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1)))]
    log(f"BigEarthNet on {dev}: {len(todo)} tiles")
    for i, k in enumerate(todo, 1):
        p = torch.from_numpy(tile_patches(k, mean, std)).to(dev)
        with torch.no_grad():
            prob = torch.sigmoid(net(p)).cpu().numpy()             # (100, 19)
        grp = np.stack([np.where(GROUP_IDX == g, prob, 0).max(1) for g in range(1, 6)], 1)
        cls = (grp.argmax(1) + 1).reshape(10, 10).astype(np.uint8)
        full = np.kron(cls, np.ones((40, 40), np.uint8))
        minx, miny, maxx, maxy = T[k]
        with rasterio.open(OUT / f"{k}.tif", "w", driver="GTiff", width=400, height=400, count=1, dtype="uint8",
                           crs="EPSG:32644", transform=from_origin(minx, maxy, 10, 10), compress="deflate") as d:
            d.write(full, 1)
        np.save(OUT / f"{k}_prob.npy", prob.reshape(10, 10, 19))
        if i % 25 == 0:
            log(f"  {i}/{len(todo)}")
    log("done")


if __name__ == "__main__":
    main()
