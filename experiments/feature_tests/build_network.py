"""
Network travel time on the road network as mapped at the start of each period, at the sampled cells.

Road network: OSM highway ways inside the HMDA bounding box (+5 km) from the dated Geofabrik snapshots already
on disk: india-180101 (= as mapped at the end of 2017, for t0 = 2017) and india-210101 (end of 2020, t0 = 2020).
Same dating as the existing road factors, so no leakage beyond what the current model already accepts.

Free-flow speeds by class (km/h; no congestion data): motorway 70, trunk 50, primary 40, secondary 35,
tertiary 30, *_link 30, residential / unclassified / living_street / road 20, service / track 12.
A cell reaches the network at its nearest node, at 10 km/h over the straight-line gap.

  tt_cbd    minutes to the old CBD (Abids)
  tt_jobs   minutes to the nearer of HITEC City (Cyber Towers) / Financial District
  tt_orr    minutes to the nearest ORR interchange
  ln_* of each (+1) are the factors tested; detour_cbd = network km / straight km to the CBD (road
  circuity, a local network-quality measure).

Output: experiments/feature_tests/feat_network.parquet  keyed by (period, x, y)
"""
from pathlib import Path
import numpy as np, pandas as pd, geopandas as gpd, osmium
from pyproj import Transformer
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import dijkstra, connected_components
from scipy.spatial import cKDTree

ROOT = Path(__file__).resolve().parents[2]
SPEED = {"motorway": 70, "trunk": 50, "primary": 40, "secondary": 35, "tertiary": 30, "residential": 20,
         "unclassified": 20, "living_street": 20, "road": 20, "service": 12, "track": 12}
for k in ("motorway", "trunk", "primary", "secondary", "tertiary"):
    SPEED[f"{k}_link"] = 30
TR = Transformer.from_crs(4326, 32644, always_xy=True)
INV = Transformer.from_crs(32644, 4326, always_xy=True)

cells = pd.concat([pd.read_parquet(ROOT / "data/processed/change" / f, columns=["period", "t0", "x", "y"])
                   for f in ("hmda_cells_census.parquet", "hmda_persist_cells_census.parquet")]).drop_duplicates(["period", "x", "y"])
(lo0, la0), (lo1, la1) = INV.transform(cells.x.min() - 5000, cells.y.min() - 5000), INV.transform(cells.x.max() + 5000, cells.y.max() + 5000)
BOX = osmium.osm.Box(osmium.osm.Location(lo0, la0), osmium.osm.Location(lo1, la1))
orr = gpd.read_file(ROOT / "data/processed/lu/prox/orr_access.gpkg").to_crs(32644)
TARGETS = {"cbd": [TR.transform(78.4772, 17.3895)],
           "jobs": [TR.transform(78.3801, 17.4507), TR.transform(78.3410, 17.4180)],
           "orr": list(zip(orr.geometry.x, orr.geometry.y))}


def graph(pbf):
    ways = []
    fp = osmium.FileProcessor(str(pbf)).with_locations().with_filter(osmium.filter.KeyFilter("highway"))
    for o in fp:
        if o.is_way():
            h = o.tags.get("highway")
            if h in SPEED:
                try:
                    pts = [(n.ref, n.lon, n.lat) for n in o.nodes]
                except osmium.InvalidLocationError:
                    continue
                if any(BOX.contains(osmium.osm.Location(lo, la)) for _, lo, la in pts[:: max(1, len(pts) // 4)] + pts[-1:]):
                    ways.append((SPEED[h], pts))
    ids = {}; xy = []; a = []; b = []; w = []
    for sp, pts in ways:
        prev = None
        for ref, lo, la in pts:
            if ref not in ids:
                ids[ref] = len(xy); xy.append(TR.transform(lo, la))
            i = ids[ref]
            if prev is not None:
                d = np.hypot(xy[i][0] - xy[prev][0], xy[i][1] - xy[prev][1])
                a.append(prev); b.append(i); w.append(d / 1000 / sp * 60)   # minutes
            prev = i
    xy = np.array(xy); n = len(xy)
    G = coo_matrix((w + w, (a + b, b + a)), shape=(n, n)).tocsr()
    print(pbf.name, "ways", len(ways), "nodes", n, flush=True)
    return G, xy


out = []
for t0, snap in ((2017, "india-180101.osm.pbf"), (2020, "india-210101.osm.pbf")):
    G, nxy = graph(ROOT / "data/raw/osm_snapshots" / snap)
    # snap only to the largest connected component (isolated fragments would give infinite times)
    ncomp, lab = connected_components(G, directed=False)
    main = np.flatnonzero(lab == np.bincount(lab).argmax())
    print(t0, "components", ncomp, "main component nodes", len(main), "of", len(nxy), flush=True)
    sub = cKDTree(nxy[main])
    tree = type("T", (), {"query": lambda self, q: (lambda r: (r[0], main[r[1]]))(sub.query(q))})()
    c = cells[cells.t0 == t0].copy(); P = c[["x", "y"]].to_numpy()
    gap, near = tree.query(P)
    access = gap / 1000 / 10 * 60
    for k, pts in TARGETS.items():
        src = np.unique(tree.query(np.array(pts))[1])
        dist = dijkstra(G, indices=src, min_only=True)
        c[f"tt_{k}"] = dist[near] + access
        c[f"ln_tt_{k}"] = np.log1p(c[f"tt_{k}"])
    # circuity to the CBD: network km at 30 km/h-equivalent is not available, so use time ratio vs straight line at 30 km/h
    straight = np.hypot(P[:, 0] - TARGETS["cbd"][0][0], P[:, 1] - TARGETS["cbd"][0][1]) / 1000 / 30 * 60
    c["detour_cbd"] = c.tt_cbd / np.maximum(straight, 1)
    print(t0, c[["tt_cbd", "tt_jobs", "tt_orr", "detour_cbd"]].describe().T[["mean", "50%", "max"]], flush=True)
    out.append(c.drop(columns="t0"))
pd.concat(out).replace([np.inf, -np.inf], np.nan).to_parquet(ROOT / "experiments/feature_tests/feat_network.parquet", index=False)
