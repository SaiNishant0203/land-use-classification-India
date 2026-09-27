#!/usr/bin/env bash
# EULUC extraction (from the unzipped GPKG), then re-run the audit and hand-label scoring
# once every model has produced its tiles, so all models appear in the same tables.
cd "$(dirname "$0")"
L=../../outputs/lu/logs
python -W ignore 12_euluc.py > $L/12_euluc.log 2>&1
echo "$(date) euluc done" >> $L/overnight.log
until grep -q "unet done" $L/overnight.log && grep -q "senclip done" $L/overnight.log && grep -q "ALL DONE" $L/overnight.log; do sleep 300; done
python -W ignore 06_train_eval.py > $L/06_train_eval_final.log 2>&1
python -W ignore 07_eval_handlabels.py > $L/07_handlabels_final.log 2>&1
echo "$(date) FINAL AUDIT DONE" >> $L/overnight.log
