"""
Zero-shot SenCLIP (Jain et al., WACV 2025; CLIP ViT-B/32 aligned to Sentinel-2 via LUCAS ground
photos, published checkpoint SenCLIP_AvgPool_ViTB32) on Hyderabad. No training.

Follows the authors' zeroshot.py: EuroSAT class names, their ground+aerial prompt ensemble,
RGB input resized to 224 with their normalisation, and logits divided by the per-class mean
over all evaluated images before argmax.

Patches: 64 x 64 px (640 m, EuroSAT size) RGB, one per 40 x 40 px (400 m) block, centred on it.
RGB = B4 B3 B2 surface reflectance / 3000, clipped to [0, 1] (EuroSAT-style 8-bit stretch).

EuroSAT -> our classes: Residential Buildings 1; Industrial Buildings 2; River, Sea or Lake 3;
Forest 4; crops, pasture, herbaceous vegetation 5; Highway or Road 0 (no land-use call).

Run with .venv-xpu. Output: data/raw/lu/senclip/<tile>.tif and <tile>_logits.npy
"""
import sys, json
from pathlib import Path
import numpy as np, torch, clip, rasterio
import torch.nn.functional as TF
from rasterio.transform import from_origin

sys.path.insert(0, str(Path(__file__).parent))
import lu_features as F
from lu_common import LURAW, BANDS, log

M = LURAW / "models"
OUT = LURAW / "senclip"; OUT.mkdir(exist_ok=True)
CLASSES = ["Annual Crop Land", "Forest", "Herbaceous Vegetation Land", "Highway or Road", "Industrial Buildings",
           "Pasture Land", "Permanent Crop Land", "Residential Buildings", "River", "Sea or Lake"]
OURS = np.array([5, 4, 5, 0, 2, 5, 5, 1, 3, 3])
MEAN = torch.tensor([0.347, 0.376, 0.296])[:, None, None]; STD = torch.tensor([0.269, 0.261, 0.276])[:, None, None]


def main():
    dev = "xpu" if torch.xpu.is_available() else "cpu"
    model, _ = clip.load("ViT-B/32", device="cpu")
    model.load_state_dict(torch.load(M / "senclip" / "SenCLIP_AvgPool_ViTB32.ckpt", map_location="cpu"), strict=True)
    model = model.float().to(dev).eval()
    prompts = json.load(open(M / "senclip_src" / "prompt_eurosat_ground_aerial_mixed.json"))
    with torch.no_grad():
        W = []
        for c in CLASSES:
            e = model.encode_text(clip.tokenize(prompts[c], truncate=True).to(dev))
            e = e / e.norm(dim=-1, keepdim=True); e = e.mean(0); W.append(e / e.norm())
        W = torch.stack(W).T                                          # (512, 10)
    T = F.tiles()
    have = lambda k: (LURAW / "feat_2023" / f"{k}.tif").exists()
    todo = [k for k in T if have(k) and not (OUT / f"{k}_logits.npy").exists()
            and all(have(n) or n not in T for n in (F.neighbour_key(k, dx, dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1)))]
    log(f"SenCLIP on {dev}: {len(todo)} tiles")
    for i, k in enumerate(todo, 1):
        f = F.read_padded(k).astype(np.float32)
        rgb = np.clip(np.stack([f[BANDS.index(b)] for b in ("B4", "B3", "B2")]) / 3000, 0, 1)
        P = torch.from_numpy(np.stack([rgb[:, F.PAD + 40 * r - 12:F.PAD + 40 * r + 52, F.PAD + 40 * c - 12:F.PAD + 40 * c + 52]
                                       for r in range(10) for c in range(10)]))
        P = (TF.interpolate(P, size=(224, 224), mode="bicubic", align_corners=False).clamp(0, 1) - MEAN) / STD
        with torch.no_grad():
            z = model.encode_image(P.to(dev)); z = z / z.norm(dim=-1, keepdim=True)
            np.save(OUT / f"{k}_logits.npy", (z @ W).cpu().numpy())
        if i % 50 == 0:
            log(f"  {i}/{len(todo)}")
    finalize(T)


def finalize(T):
    """Authors' calibration: divide logits by their per-class mean over all evaluated images."""
    files = sorted(OUT.glob("*_logits.npy"))
    L = {p.name[:-len("_logits.npy")]: np.load(p) for p in files}
    colmean = np.concatenate(list(L.values())).mean(0, keepdims=True)
    for k, lg in L.items():
        cls = OURS[(lg / (colmean + 1e-6)).argmax(1)].reshape(10, 10).astype(np.uint8)
        minx, miny, maxx, maxy = T[k]
        with rasterio.open(OUT / f"{k}.tif", "w", driver="GTiff", width=400, height=400, count=1, dtype="uint8",
                           crs="EPSG:32644", transform=from_origin(minx, maxy, 10, 10), compress="deflate") as d:
            d.write(np.kron(cls, np.ones((40, 40), np.uint8)), 1)
    log(f"finalized {len(L)} tiles")


if __name__ == "__main__":
    main()
