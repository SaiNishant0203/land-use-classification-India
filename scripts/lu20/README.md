# 20 m land-use model with year-dated OSM labels

Production version of the classifier: 20 m cells (after Ethan's resolution experiment), the
53 physical features, and training labels for each year built from **OSM as mapped on
31 December of that year**, from Geofabrik's dated snapshots. Earlier models all used OSM
downloaded in September 2026.

```
powershell -ExecutionPolicy Bypass -File scripts/lu20/download_snapshots.ps1   # 1.7 GB, resumable
python scripts/lu20/run_all.py        # whole chain; finished steps are skipped, so reruns resume
```

Snapshots (download.geofabrik.de, no login), each OSM as of 1 January of the next year:
`india-180101.osm.pbf` (2017), `india-210101.osm.pbf` (2020), `southern-zone-240101.osm.pbf` (2023).
They are not in git. The extracted polygons are: `data/processed/lu20/osm_<year>/geofabrik.gpkg`
(force-added, because `data/processed` is otherwise ignored).

| step | script | output |
|---|---|---|
| OSM per year | `01b_osm_geofabrik.py` | `data/processed/lu20/osm_<year>/geofabrik.gpkg` (`01_osm_dated.py` is the older Overpass route, used only if `data/raw/osm_snapshots/` is missing; overpass-api.de was at capacity, then unreachable) |
| labels per year | `02_labels.py <year>` | `data/raw/lu/lu20/lab_<year>/` (10 m, same rules as `scripts/lu/04_labels.py`; water before 2021 also needs JRC) |
| 20 m grid per year | `03_build_grid.py <year>` | `data/raw/lu/lu20/grid_<year>/` (adapted from `experiments/res100/build_grid.py`) |
| models + CV | `04_train.py` | `outputs/lu20/models/` (`year_<y>`, `pooled`, control `osm2026_2023`), `cv_scores.csv` |
| maps | `06_maps.py` | `outputs/lu20/maps/landuse_<year>_20m_{pooled,year}.tif`, `map_stats.csv` |
| scores + summary | `05_eval.py` | `handlabel_scores.csv`, `handlabel_paired.csv`, `label_change_2023.csv`, **`RESULTS.md`** |
| WorldPop check | `07_worldpop_check.py` | `outputs/lu20/worldpop/` |
| external validation | `08_external.py` | `outputs/lu20/external/` |
| Esri check | `08_esri_check.py` | `outputs/lu20/esri_check/` |
| Ethan's 281 cells | `10_ethan_cells_check.py` | `outputs/lu20/ethan_cells/` (`NOTE.md`) |
| fixes across seeds | `11_retrain_variants.py` | `outputs/lu20/retrain/RESULTS.md` |

Log: `outputs/lu20/logs/run_<date>.log`. `LU20_TEST=1` runs everything on 12 tiles around
Gachibowli into `*_test` folders (50 boosting rounds), to check the code path in a few minutes.

Measured run time on an i7-13620H, 18 Oct 2026: OSM extraction 2 min, labels and grids 4 min,
training 9 min, maps 40 min.
