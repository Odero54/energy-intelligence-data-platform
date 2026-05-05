import os

import pytest
import snowflake.connector
from dotenv import load_dotenv

load_dotenv()

REQUIRED = ["SNOWFLAKE_ACCOUNT", "SNOWFLAKE_USER", "SNOWFLAKE_PASSWORD"]
missing = [k for k in REQUIRED if not os.getenv(k)]


@pytest.mark.skipif(bool(missing), reason=f"Snowflake credentials not set: {missing}")
def test_snowflake_connection():
    conn = snowflake.connector.connect(
        account=os.environ["SNOWFLAKE_ACCOUNT"],
        user=os.environ["SNOWFLAKE_USER"],
        password=os.environ["SNOWFLAKE_PASSWORD"],
        warehouse=os.getenv("SNOWFLAKE_WAREHOUSE", "ENERGY_WH"),
        database=os.getenv("SNOWFLAKE_DATABASE", "ENERGY_INTELLIGENCE"),
        role=os.getenv("SNOWFLAKE_ROLE", "ENERGY_ROLE"),
    )
    try:
        cur = conn.cursor()
        cur.execute("SELECT CURRENT_USER(), CURRENT_WAREHOUSE(), CURRENT_DATABASE()")
        row = cur.fetchone()
        assert row is not None, "No result returned from Snowflake"
        print(f"\nConnected as: {row[0]} | warehouse: {row[1]} | database: {row[2]}")
    finally:
        conn.close()
