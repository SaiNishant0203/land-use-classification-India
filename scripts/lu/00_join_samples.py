"""
Rebuild data/processed/lu/samples.parquet from the parts stored in the repo.

GitHub rejects files over 100 MB, so the 393,098-pixel training table is committed as two
parts in data/processed/lu/samples_parts/. Run this once after cloning:

    python scripts/lu/00_join_samples.py
"""
import pyarrow as pa, pyarrow.parquet as pq
from lu_common import LU, log

parts = sorted((LU / "samples_parts").glob("samples_part*.parquet"))
t = pa.concat_tables([pq.read_table(p) for p in parts])
pq.write_table(t, LU / "samples.parquet", compression="zstd")
log(f"samples.parquet rebuilt from {len(parts)} parts: {t.num_rows:,} rows x {t.num_columns} columns")
