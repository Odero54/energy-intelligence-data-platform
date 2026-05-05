"""Load data/processed/grid_proximity.parquet → RAW.GRID_PROXIMITY in Snowflake.

Run after `make grid-proximity` has produced the parquet file.
"""

from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

load_dotenv()

PARQUET_PATH = Path(__file__).parents[1] / "data" / "processed" / "grid_proximity.parquet"


def main() -> None:
    if not PARQUET_PATH.exists():
        raise FileNotFoundError(
            f"Grid proximity parquet not found at {PARQUET_PATH}.\nRun `make grid-proximity` first."
        )

    df = pd.read_parquet(PARQUET_PATH)
    print(f"Loaded {len(df)} rows from {PARQUET_PATH}")
    print(f"Proximity breakdown:\n{df['grid_proximity_category'].value_counts().to_string()}")

    from ingestion._snowflake import upsert_dataframe

    n_ins, n_upd = upsert_dataframe(df, "GRID_PROXIMITY", merge_keys=["admin_gid"])
    print(f"Upserted → RAW.GRID_PROXIMITY: {n_ins} inserted, {n_upd} updated")


if __name__ == "__main__":
    main()
