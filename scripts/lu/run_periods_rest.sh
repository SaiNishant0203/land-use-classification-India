#!/bin/bash
# Continues run_periods.sh after the panel is built (the original chain hit a time limit).
cd "$(dirname "$0")"
L=../../outputs/lu/logs
log() { echo "$(date +%H:%M:%S) $*" | tee -a $L/periods.log; }
until [ -f ../../data/processed/lu/transition_panel.parquet ] && ! grep -q "Traceback" $L/21_panel.log && \
      grep -q "2017->2023:" $L/21_panel.log; do
  grep -q "Traceback" $L/21_panel.log && { log "21 failed"; exit 1; }
  sleep 30
done
log "panel ready"
for p in "2017 2020" "2020 2023" "2017 2023"; do
  log "22 $p"; python 22_choice_models.py $p > $L/22_${p// /_}.log 2>&1 || log "22 $p failed"
done
log "24 compare"; python 24_period_compare.py > $L/24_compare.log 2>&1 || log "24 failed"
log "25 latent segmentation"; python 25_latent_segmentation.py 2017 2023 > $L/25_latent.log 2>&1 || log "25 failed"
log "ALL DONE"
