#!/bin/bash
# Two-period stability run: panel 2017/2020/2023 -> models per period -> comparison.
cd "$(dirname "$0")"
L=../../outputs/lu/logs
log() { echo "$(date +%H:%M:%S) $*" | tee -a $L/periods.log; }
log "dry run (15 central tiles)"
DRY=1 python 21_transition_data.py > $L/21_panel_dryrun.log 2>&1 || { log "21 DRY failed"; exit 1; }
for p in "2017 2020" "2020 2023"; do DRY=1 python 22_choice_models.py $p > $L/22_dryrun_${p// /_}.log 2>&1 || { log "22 DRY $p failed"; exit 1; }; done
DRY=1 python 24_period_compare.py > $L/24_dryrun.log 2>&1 || { log "24 DRY failed"; exit 1; }
log "dry run OK; full panel"
python 21_transition_data.py > $L/21_panel.log 2>&1 || { log "21 failed"; exit 1; }
for p in "2017 2020" "2020 2023" "2017 2023"; do
  log "22 $p"; python 22_choice_models.py $p > $L/22_${p// /_}.log 2>&1 || log "22 $p failed"
done
log "24 compare"; python 24_period_compare.py > $L/24_compare.log 2>&1 || { log "24 failed"; exit 1; }
log "25 latent segmentation"; python 25_latent_segmentation.py 2017 2023 > $L/25_latent.log 2>&1 || log "25 failed"
log "ALL DONE"
