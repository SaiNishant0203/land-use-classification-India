"""
Rasterise NRSC SIS-DP Phase 2 LULC 1:10K (2016-19, Telangana) onto our 10 m tile grid, using
Bhuvan's public OGC WMS (bhuvan-vec2.nrsc.gov.in/bhuvan/wms).

The published style draws many classes in one colour (all Core Urban sub-classes are the same
red), so each request sends an SLD that gives every REG_DESCRI code a unique colour (code index
encoded in R*256+G, B = 0), with antialiasing off; the PNG is decoded back to the code index.
Polite: one request at a time, resumable.

Outputs: data/raw/lu/sisdp/<tile>.tif  uint8 band 1 = SIS-DP code index (see sisdp_codes.json,
         1-based; 0 = no polygon), band 2 = our 5-class mapping (0 = none / transport network)
"""
import json, time, io
import numpy as np, requests, rasterio
from rasterio.transform import from_origin
from PIL import Image
from lu_common import LU, LURAW, UTM, log

URL = "https://bhuvan-vec2.nrsc.gov.in/bhuvan/wms"
LAYER = "sisdp_phase2:SISDP_P2_LULC_10K_2016_2019_TS"
OUT = LURAW / "sisdp"; OUT.mkdir(exist_ok=True)


def codes():
    fp = LU / "sisdp_codes.json"
    if not fp.exists():
        j = requests.get(URL, params={"service": "WMS", "request": "GetLegendGraphic", "format": "application/json",
                                      "layer": LAYER, "version": "1.1.1"}, timeout=60).json()
        cs = [(ru["filter"].split("'")[1], ru.get("title") or ru.get("name"))
              for ru in j["Legend"][0]["rules"] if "REG_DESCRI = '" in ru.get("filter", "")]
        fp.write_text(json.dumps(cs))
    return json.loads(fp.read_text())


def to_ours(name):
    """SIS-DP class name -> our 5 classes (0 = no prediction)."""
    n = name.lower()
    if "transport network" in n:
        return 0
    if any(s in n for s in ("core urban residential", "core urban mixed", "peri urban", "village settlement",
                            "hamlet", "core urban\u0000")) or n.strip() == "built up - core urban":
        return 1
    if any(s in n for s in ("industr", "power plant", "solar", "cooling pond", "effluent", "commercial",
                            "institutional", "educational", "mandi", "transport infrastructure", "dumping")):
        return 2
    if n.startswith("water body") or "aquaculture" in n:
        return 3
    if "forest" in n or "plantation" in n or "agro forestry" in n or "urban green" in n or "park" in n:
        return 4
    return 5


def sld(cs):
    rules = "".join(
        f'<Rule><ogc:Filter><ogc:PropertyIsEqualTo><ogc:PropertyName>REG_DESCRI</ogc:PropertyName>'
        f'<ogc:Literal>{c}</ogc:Literal></ogc:PropertyIsEqualTo></ogc:Filter><PolygonSymbolizer><Fill>'
        f'<CssParameter name="fill">#{(i + 1) // 256:02x}{(i + 1) % 256:02x}00</CssParameter></Fill>'
        f'</PolygonSymbolizer></Rule>' for i, (c, _) in enumerate(cs))
    return (f'<?xml version="1.0"?><StyledLayerDescriptor version="1.0.0" xmlns="http://www.opengis.net/sld" '
            f'xmlns:ogc="http://www.opengis.net/ogc"><NamedLayer><Name>{LAYER}</Name><UserStyle><FeatureTypeStyle>'
            f'{rules}</FeatureTypeStyle></UserStyle></NamedLayer></StyledLayerDescriptor>')


def main():
    cs = codes(); body = sld(cs)
    lut = np.array([0] + [to_ours(n) for _, n in cs], np.uint8)
    T = json.loads((LURAW / "feat_2023" / "tiles.json").read_text())
    todo = [k for k in T if not (OUT / f"{k}.tif").exists()]
    log(f"SIS-DP: {len(todo)} of {len(T)} tiles to fetch")
    for i, k in enumerate(todo, 1):
        minx, miny, maxx, maxy = T[k]
        p = {"service": "WMS", "version": "1.1.1", "request": "GetMap", "layers": LAYER, "styles": "",
             "srs": f"EPSG:{UTM}", "bbox": f"{minx},{miny},{maxx},{maxy}", "width": 400, "height": 400,
             "format": "image/png", "transparent": "true", "format_options": "antialias:none", "SLD_BODY": body}
        for t in range(6):
            try:
                r = requests.post(URL, data=p, timeout=180)
                if "image" in r.headers.get("content-type", ""):
                    break
                raise RuntimeError(r.text[:200])
            except Exception as e:
                log(f"  {k} retry {t}: {str(e)[:120]}"); time.sleep(20 * (t + 1))
        else:
            log(f"  {k} FAILED"); continue
        a = np.array(Image.open(io.BytesIO(r.content)).convert("RGBA")).astype(int)
        idx = a[..., 0] * 256 + a[..., 1]
        idx[(a[..., 3] < 255) | (a[..., 2] != 0) | (idx > len(cs))] = 0
        idx = idx.astype(np.uint8)
        with rasterio.open(OUT / f"{k}.tif", "w", driver="GTiff", width=400, height=400, count=2, dtype="uint8",
                           crs=f"EPSG:{UTM}", transform=from_origin(minx, maxy, 10, 10), compress="deflate") as d:
            d.write(idx, 1); d.write(lut[idx], 2)
        if i % 50 == 0:
            log(f"  {i}/{len(todo)}")
        time.sleep(1)
    log("SIS-DP rasterisation done")


if __name__ == "__main__":
    main()
