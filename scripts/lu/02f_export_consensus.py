"""
Merge the reviewed consensus 20 m cells (set 1 = 02d top 30 per class, set 2 = 02e) into one
labelled set. Review labels come from the CSVs downloaded from the review pages.

`true_class` 0 = rejected by the reviewer (mixed / unclear); those cells are kept in the
GeoPackage for the record and left out of the CSV.

Outputs (data/processed/lu/):
  consensus20_labels.gpkg  - all reviewed cells, EPSG:32644, with `set`, `proposed_class`,
                             `true_class`, `accepted`
  handlabelled_ethan.csv   - accepted cells only: id, centre lon/lat (WGS84), centre x/y
                             (EPSG:32644), class (1 residential, 2 non-residential built,
                             3 water, 4 forest/trees, 5 other open)
Usage: python 02f_export_consensus.py
"""
import importlib, json, os
from pathlib import Path
import numpy as np, pandas as pd, geopandas as gpd
from lu_common import LU, LURAW, log

C = importlib.import_module("02c_consensus_cells_20m")
RAW = Path(os.environ.get("LU_RAW", LURAW))
SETS = [(1, "consensus20_top30.gpkg", "review30/review30_labels.csv"),
        (2, "consensus20_set2.gpkg", "review_set2/review_set2_labels.csv")]


def main():
    tiles = json.loads((RAW / "feat_2023" / "tiles.json").read_text())
    parts = []
    for s, gp, lab in SETS:
        u = gpd.read_file(LU / gp, layer="consensus_cells")
        r = pd.read_csv(LU / lab)[["pid", "true_class", "checked", "notes"]]
        assert len(r) == len(u) and set(r.pid) == set(u.pid), f"set {s}: labels do not match cells"
        u = u.drop(columns=["true_class", "checked", "notes"]).merge(r, on="pid")
        u.insert(0, "set", s); u = u.rename(columns={"pid": "set_pid"})
        parts.append(u)
    a = pd.concat(parts, ignore_index=True)
    a.insert(0, "cell_id", np.arange(1, len(a) + 1))
    a["accepted"] = (a.true_class > 0).astype(int)
    a["class_name"] = a.true_class.map({0: "rejected", **C.NAMES})
    c = a.geometry.centroid
    a["x"], a["y"] = c.x.round(1), c.y.round(1)
    b = a.geometry.bounds
    a["row"] = [int((tiles[t][3] - y1) // 10) for t, y1 in zip(a.tile, b.maxy)]
    a["col"] = [int((x0 - tiles[t][0]) // 10) for t, x0 in zip(a.tile, b.minx)]
    assert a.geometry.to_wkb().is_unique
    a["notes"] = a.notes.fillna("")
    cols = ["cell_id", "set", "set_pid", "true_class", "class_name", "proposed_class", "accepted",
            "lon", "lat", "x", "y", "tile", "row", "col", "osm2023", "purity", "model_prob", "score",
            "confidence", "notes", "checked", "geometry"]
    a = gpd.GeoDataFrame(a[cols], geometry="geometry", crs=parts[0].crs)
    fp = LU / "consensus20_labels.gpkg"
    fp.unlink(missing_ok=True)
    a.to_file(fp, layer="consensus_cells", driver="GPKG")
    C.add_style(fp)
    ok = a[a.accepted == 1].sort_values("cell_id")
    pd.DataFrame({"id": np.arange(1, len(ok) + 1), "lon": ok.lon.round(6), "lat": ok.lat.round(6),
                  "x": ok.x.round().astype(int), "y": ok.y.round().astype(int), "class": ok.true_class.astype(int)})       .to_csv(LU / "handlabelled_ethan.csv", index=False)
    log(f"wrote {fp} ({len(a)} cells) and handlabelled_ethan.csv ({len(ok)} accepted)")
    log("\n" + pd.crosstab([a.set], a.class_name, margins=True).to_string())
    log("proposed vs reviewed:\n" + pd.crosstab(a.proposed_class.map(C.NAMES), a.class_name).to_string())


if __name__ == "__main__":
    main()
