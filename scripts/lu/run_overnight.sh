#!/usr/bin/env bash
# Overnight chain for the land-use pipeline. Logs in outputs/lu/logs/.
cd "$(dirname "$0")"
L=../../outputs/lu/logs
PY=python
XPU=../../.venv-xpu/Scripts/python
done_all() { grep -q "done; failed" $L/03_download_2023.log && grep -q " done$" $L/03b_products.log && grep -q " done$" $L/03c_s2extra.log 2>/dev/null; }
echo "$(date) start" >> $L/overnight.log
while ! done_all; do
  $PY -W ignore 04_labels.py >> $L/04_labels.log 2>&1
  $PY -W ignore 05_sample_pixels.py >> $L/05_sample.log 2>&1
  echo "$(date) interim: $(ls ../../data/raw/lu/feat_2023/*.tif | wc -l) feat, $(ls ../../data/raw/lu/prod/*.tif | wc -l) prod, $(ls ../../data/raw/lu/s2x_2023/*.tif 2>/dev/null | wc -l) s2x" >> $L/overnight.log
  sleep 900
done
echo "$(date) downloads finished; second pass for any failed tiles" >> $L/overnight.log
$PY -W ignore 03_download_features.py 2023 >> $L/03_download_2023_pass2.log 2>&1
$PY -W ignore 03b_download_products.py >> $L/03b_products_pass2.log 2>&1
$PY -W ignore 03c_download_s2extra.py >> $L/03c_s2extra_pass2.log 2>&1
$PY -W ignore 04_labels.py >> $L/04_labels.log 2>&1
$PY -W ignore 05_sample_pixels.py >> $L/05_sample.log 2>&1
$XPU -W ignore 08_bigearthnet.py >> $L/08_ben.log 2>&1
echo "$(date) BEN done" >> $L/overnight.log
$PY -W ignore 06_train_eval.py > $L/06_train_eval.log 2>&1
echo "$(date) train/eval done" >> $L/overnight.log
$PY -W ignore 09_predict_map.py > $L/09_predict.log 2>&1
echo "$(date) map done" >> $L/overnight.log
$PY -W ignore 07_eval_handlabels.py > $L/07_handlabels.log 2>&1
echo "$(date) ALL DONE" >> $L/overnight.log
