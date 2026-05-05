"""Shared Snowflake loader used by all ingestion pipelines."""

import os
import uuid

import pandas as pd
import snowflake.connector
from dotenv import load_dotenv
from snowflake.connector.pandas_tools import write_pandas

load_dotenv()

DATABASE = "ENERGY_INTELLIGENCE"
SCHEMA = "RAW"
WAREHOUSE = "ENERGY_WH"


def get_connection() -> snowflake.connector.SnowflakeConnection:
    return snowflake.connector.connect(
        account=os.environ["SNOWFLAKE_ACCOUNT"],
        user=os.environ["SNOWFLAKE_USER"],
        password=os.environ["SNOWFLAKE_PASSWORD"],
        warehouse=WAREHOUSE,
        database=DATABASE,
        schema=SCHEMA,
        role=os.environ.get("SNOWFLAKE_ROLE", "ENERGY_ROLE"),
    )


def load_dataframe(df: pd.DataFrame, table_name: str, truncate: bool = True) -> int:
    """Upload df to RAW.<table_name>. Returns row count loaded."""
    # write_pandas double-quotes column names, so they must match Snowflake's
    # stored case (uppercase) exactly.
    df = df.rename(columns=str.upper).reset_index(drop=True)
    conn = get_connection()
    try:
        if truncate:
            with conn.cursor() as cur:
                cur.execute(f"TRUNCATE TABLE {SCHEMA}.{table_name}")
        success, _nchunks, nrows, _output = write_pandas(
            conn,
            df,
            table_name,
            database=DATABASE,
            schema=SCHEMA,
            auto_create_table=False,
            overwrite=False,
        )
        if not success:
            raise RuntimeError(f"write_pandas failed for {table_name}")
        return nrows
    finally:
        conn.close()


def upsert_dataframe(
    df: pd.DataFrame,
    table_name: str,
    merge_keys: list[str],
) -> tuple[int, int]:
    """MERGE df into RAW.<table_name> — no duplicates on repeated runs.

    Stages df to a throw-away temp table, then issues a Snowflake MERGE into
    the target.  Rows whose merge_keys already exist are UPDATEd; new rows are
    INSERTed.  The temp table is always dropped on exit.

    merge_keys must be column names as they appear in df (any case — they are
    uppercased internally to match Snowflake storage).

    NULL keys are handled with a NULL-safe join condition so that rows whose
    key column is NULL can still be matched (e.g. NIGHTLIGHTS.month = NULL
    for annual composites).

    Returns (rows_inserted, rows_updated).
    """
    df = df.rename(columns=str.upper).reset_index(drop=True)
    keys = [k.upper() for k in merge_keys]

    # Deduplicate on merge keys before staging — Snowflake MERGE requires the
    # source to have at most one matching row per target row.
    df = df.drop_duplicates(subset=keys, keep="last")

    cols = list(df.columns)
    non_keys = [c for c in cols if c not in keys]

    # NULL-safe join: (t.k = s.k OR (t.k IS NULL AND s.k IS NULL))
    join_parts = [f"(t.{k} = s.{k} OR (t.{k} IS NULL AND s.{k} IS NULL))" for k in keys]
    join_cond = " AND ".join(join_parts)
    update_set = ", ".join(f"t.{c} = s.{c}" for c in non_keys)
    ins_cols = ", ".join(cols)
    ins_vals = ", ".join(f"s.{c}" for c in cols)

    tmp = f"TMP_{table_name}_{uuid.uuid4().hex[:8].upper()}"
    conn = get_connection()
    try:
        write_pandas(
            conn,
            df,
            tmp,
            database=DATABASE,
            schema=SCHEMA,
            auto_create_table=True,
            overwrite=True,
        )

        merge_sql = f"""
            MERGE INTO {SCHEMA}.{table_name} t
            USING {SCHEMA}.{tmp} s
            ON {join_cond}
            WHEN MATCHED THEN UPDATE SET {update_set}
            WHEN NOT MATCHED THEN INSERT ({ins_cols}) VALUES ({ins_vals})
        """
        with conn.cursor() as cur:
            cur.execute(merge_sql)
            row = cur.fetchone()
            n_ins, n_upd = (int(row[0]), int(row[1])) if row else (0, 0)

        return n_ins, n_upd

    finally:
        with conn.cursor() as cur:
            cur.execute(f"DROP TABLE IF EXISTS {SCHEMA}.{tmp}")
        conn.close()
