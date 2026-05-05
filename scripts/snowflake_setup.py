"""
Run Snowflake DDL scripts in order.
Usage: uv run python scripts/snowflake_setup.py
"""

import os
import re
from pathlib import Path

import snowflake.connector
from dotenv import load_dotenv

load_dotenv()

DDL_DIR = Path(__file__).parent.parent / "snowflake" / "schemas"
DDL_FILES = sorted(DDL_DIR.glob("*.sql"))


def get_connection() -> snowflake.connector.SnowflakeConnection:
    return snowflake.connector.connect(
        account=os.environ["SNOWFLAKE_ACCOUNT"],
        user=os.environ["SNOWFLAKE_USER"],
        password=os.environ["SNOWFLAKE_PASSWORD"],
        role=os.environ.get("SNOWFLAKE_ROLE", "ENERGY_ROLE"),
    )


def run_ddl(conn: snowflake.connector.SnowflakeConnection, path: Path) -> None:
    sql = path.read_text()
    statements = [
        s.strip() for s in sql.split(";") if s.strip() and re.sub(r"--[^\n]*", "", s).strip()
    ]
    with conn.cursor() as cur:
        for stmt in statements:
            print(f"  → {stmt[:80].replace(chr(10), ' ')}…")
            cur.execute(stmt)


def main() -> None:
    print(f"Connecting to Snowflake account: {os.environ['SNOWFLAKE_ACCOUNT']}")
    conn = get_connection()
    try:
        for ddl_file in DDL_FILES:
            print(f"\nRunning {ddl_file.name}")
            run_ddl(conn, ddl_file)
        print("\nSnowflake setup complete.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
