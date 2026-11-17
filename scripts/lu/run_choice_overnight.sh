#!/bin/bash
# Overnight chain for the transition / choice models. Waits for its inputs, then runs 21 and 22.
cd "$(dirname "$0")"
L=../../outputs/lu/logs
log() { echo "$(date +%H:%M:%S) $*" | tee -a $L/choice_overnight.log; }
log "20 proximity (roads 2017 via Overpass history, with fallbacks)"
python 20_proximity.py > $L/20_proximity.log 2>&1 || { log "20 failed"; exit 1; }
log "dry run of 21 + 22 on the central tiles downloaded so far"
DRY=1 python 21_transition_data.py > $L/21_transition_dryrun.log 2>&1 && DRY=1 python 22_choice_models.py > $L/22_choice_dryrun.log 2>&1 && log "dry run OK" || log "DRY RUN FAILED (see logs)"
log "waiting for SIS-DP tiles and all 2017 physical tiles"
until grep -q "rasterisation done" $L/23_sisdp.log; do sleep 60; done
until [ "$(ls ../../data/raw/lu/phys_2017/*.tif 2>/dev/null | grep -v '\.b' | wc -l)" -ge 556 ] || \
      { grep -q "^.*done; failed" $L/03d_phys_2017.log && grep -q "done; failed" $L/03d_phys_2017_rev.log; }; do sleep 120; done
log "inputs ready; checking tile integrity"
python - <<'PY' 2>&1 | tee -a $L/choice_overnight.log
import glob, rasterio, os
bad = []
for f in glob.glob("../../data/raw/lu/phys_2017/x*.tif"):
    if ".b" in os.path.basename(f): continue
    try:
        with rasterio.open(f) as s:
            if s.count != 12 or s.width != 400: bad.append(f)
            s.read(12)
    except Exception: bad.append(f)
for f in bad: os.remove(f)
print(f"removed {len(bad)} corrupt tiles: {bad}")
PY
log "21 transition data"
python 21_transition_data.py > $L/21_transition.log 2>&1 || { log "21 failed"; exit 1; }
log "22 choice models"
python 22_choice_models.py > $L/22_choice.log 2>&1 || { log "22 failed"; exit 1; }
log "ALL DONE"
