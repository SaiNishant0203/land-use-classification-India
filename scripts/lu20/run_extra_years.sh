#!/usr/bin/env bash
# Final maps for 2018, 2019, 2021 and 2022 (the other years are in outputs/lu20/maps_final already).
#   1. Earth Engine physical bands per year (scripts/lu/03d_download_phys.py, two processes per year,
#      two years at a time) while the four Geofabrik OSM snapshots download
#   2. per year: OSM polygons -> 10 m labels -> 20 m grid -> training cache (12_final_maps.py --prep)
#   3. maps on the remote machine (5 seeds per year), copied back to outputs/lu20/maps_final/
# Every step skips finished work, so a rerun resumes. Log: outputs/lu20/logs/extra_years.log
# Usage (from the repo root): LU20_REMOTE=user@host LU20_RDIR=<dir> bash scripts/lu20/run_extra_years.sh
# The remote copy needs the repo layout and a Python env at <dir>/env (lightgbm, rasterio, geopandas, pyarrow).
set -u
cd "$(dirname "$0")/../.."
PY=.venv-xpu/Scripts/python.exe
LOG=outputs/lu20/logs/extra_years.log
REMOTE=${LU20_REMOTE:?set LU20_REMOTE=user@host, the machine that makes the maps}
RDIR=${LU20_RDIR:?set LU20_RDIR, the repo copy on that machine (relative to its home)}
NEW="2018 2019 2021 2022"
mkdir -p outputs/lu20/logs
say() { echo "$(date +%H:%M:%S) $*" | tee -a "$LOG"; }

say "start: years $NEW"
(for f in india-190101 india-200101 india-220101 india-230101; do      # same files as download_snapshots.ps1
    for k in 1 2 3 4 5; do
        curl -s -L -C - --retry 5 -o data/raw/osm_snapshots/$f.osm.pbf https://download.geofabrik.de/asia/$f.osm.pbf && break
        sleep 30
    done
done) &
SNAP=$!

for pair in "2018 2019" "2021 2022"; do
    pids=()
    for y in $pair; do
        (cd scripts/lu && ../../$PY 03d_download_phys.py $y >> ../../outputs/lu/logs/03d_phys_$y.log 2>&1) & pids+=($!)
        sleep 20   # the first process writes tiles.json
        (cd scripts/lu && ../../$PY 03d_download_phys.py $y rev >> ../../outputs/lu/logs/03d_phys_${y}_rev.log 2>&1) & pids+=($!)
    done
    wait "${pids[@]}"
    for y in $pair; do      # one more pass picks up tiles that failed
        (cd scripts/lu && ../../$PY 03d_download_phys.py $y >> ../../outputs/lu/logs/03d_phys_$y.log 2>&1)
        n=$(ls data/raw/lu/phys_$y/*.tif 2>/dev/null | wc -l)
        say "EE $y: $n of 556 tiles"
    done
done
wait $SNAP; say "OSM snapshots downloaded: $(ls data/raw/osm_snapshots | tr '\n' ' ')"

cd scripts/lu20
for y in $NEW; do
    n=$(ls ../../data/raw/lu/phys_$y/*.tif 2>/dev/null | wc -l)
    if [ "$n" -lt 556 ]; then say "SKIP $y: only $n tiles"; continue; fi
    [ -f ../../data/raw/lu/lu20/osm_$y.done ] || ../../$PY 01b_osm_geofabrik.py $y >> ../../$LOG 2>&1
    [ -f ../../data/raw/lu/lu20/labels_$y.done ] || ../../$PY 02_labels.py $y >> ../../$LOG 2>&1
    [ -f ../../data/raw/lu/lu20/grid_$y.done ] || ../../$PY 03_build_grid.py $y >> ../../$LOG 2>&1
    [ -f ../../outputs/lu20/retrain/cache/rows_$y.pkl ] || ../../$PY 12_final_maps.py --prep $y >> ../../$LOG 2>&1
    [ -f ../../outputs/lu20/retrain/cache/rows_$y.pkl ] && say "$y ready for mapping" || say "FAILED $y before mapping"
done
cd ../..

READY=""; for y in $NEW; do [ -f outputs/lu20/retrain/cache/rows_$y.pkl ] && READY="$READY $y"; done
[ -z "$READY" ] && { say "nothing to map"; exit 1; }
say "copying to remote:$READY"
scp -q -o BatchMode=yes scripts/lu20/common20.py scripts/lu20/features20.py scripts/lu20/12_final_maps.py $REMOTE:$RDIR/scripts/lu20/
for y in $READY; do
    ssh -o BatchMode=yes $REMOTE "mkdir -p $RDIR/data/raw/lu/lu20/grid_$y"
    scp -q -o BatchMode=yes data/raw/lu/lu20/grid_$y/{meta.json,mean.npy,hw.npy,hmax.npy,valid.npy} $REMOTE:$RDIR/data/raw/lu/lu20/grid_$y/
    scp -q -o BatchMode=yes outputs/lu20/retrain/cache/{rows_$y.pkl,feat_$y.npz,feat_${y}_names.json} $REMOTE:$RDIR/outputs/lu20/retrain/cache/
done
say "mapping on remote"
ssh -o BatchMode=yes -o ServerAliveInterval=60 $REMOTE \
    "cd $RDIR && N_JOBS=24 nice -n 10 ./env/bin/python scripts/lu20/12_final_maps.py$READY > run_extra.log 2>&1; tail -3 run_extra.log" >> "$LOG" 2>&1
for y in $READY; do
    scp -q -o BatchMode=yes $REMOTE:$RDIR/outputs/lu20/maps_final/landuse_${y}_20m.tif outputs/lu20/maps_final/ \
        && say "map $y copied back" || say "FAILED copying map $y"
done
say "ALL DONE"
