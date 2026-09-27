#!/usr/bin/env bash
# Re-run after the water-label fix (JRC misses post-2021 reservoirs).
cd "$(dirname "$0")"
L=../../outputs/lu/logs
rm -f ../../data/raw/lu/lab/*.tif ../../data/processed/lu/samples/*.parquet ../../data/raw/lu/pred_2023/*.tif
python -W ignore 04_labels.py > $L/04_labels_v2.log 2>&1
python -W ignore 05_sample_pixels.py > $L/05_sample_v2.log 2>&1
echo "$(date) v2 labels+samples done" >> $L/overnight.log
python -W ignore 06_train_eval.py > $L/06_train_eval_v2.log 2>&1
echo "$(date) v2 train/eval done" >> $L/overnight.log
python -W ignore 09_predict_map.py > $L/09_predict_v2.log 2>&1
echo "$(date) v2 map done" >> $L/overnight.log
