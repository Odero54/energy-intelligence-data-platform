"""Fetch electricity access % from World Bank SE4ALL API → RAW.WORLD_BANK_ELECTRICITY_ACCESS."""

from pathlib import Path

import pandas as pd
import wbgapi as wb
from dotenv import load_dotenv

load_dotenv()

INDICATOR = "EG.ELC.ACCS.ZS"
INDICATOR_NAME = "Access to electricity (% of population)"

TARGET_COUNTRIES = ["KEN", "NGA", "IND", "TZA", "RWA", "CIV", "PAK"]

COUNTRY_NAMES = {
    "KEN": "Kenya",
    "NGA": "Nigeria",
    "IND": "India",
    "TZA": "Tanzania",
    "RWA": "Rwanda",
    "CIV": "Cote d'Ivoire",
    "PAK": "Pakistan",
}

RAW_DIR = Path(__file__).parents[2] / "data" / "raw" / "world_bank"

OUTPUT_COLS = [
    "country_code",
    "country_name",
    "indicator_code",
    "indicator_name",
    "year",
    "value",
    "_source_file",
]


def extract() -> pd.DataFrame:
    print("  Fetching World Bank electricity access data...")
    return wb.data.DataFrame(INDICATOR, TARGET_COUNTRIES, mrv=30, numericTimeKeys=True)


def transform(raw: pd.DataFrame) -> pd.DataFrame:
    df = raw.reset_index().melt(id_vars=["economy"], var_name="year", value_name="value")
    df = df.rename(columns={"economy": "country_code"})
    df = df.dropna(subset=["value"])
    df["country_name"] = df["country_code"].map(COUNTRY_NAMES)
    df["indicator_code"] = INDICATOR
    df["indicator_name"] = INDICATOR_NAME
    df["year"] = df["year"].astype(str)
    df["value"] = df["value"].astype(str)
    df["_source_file"] = "worldbank_api"
    return df[OUTPUT_COLS]


def run(dry_run: bool = False) -> None:
    raw = extract()
    df = transform(raw)

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    cache_path = RAW_DIR / "electricity_access.parquet"
    df.to_parquet(cache_path, index=False)
    print(f"  Transformed: {len(df)} rows → {cache_path}")

    if not dry_run:
        from ingestion._snowflake import upsert_dataframe

        n_ins, n_upd = upsert_dataframe(
            df,
            "WORLD_BANK_ELECTRICITY_ACCESS",
            merge_keys=["country_code", "year"],
        )
        print(f"  Upserted → RAW.WORLD_BANK_ELECTRICITY_ACCESS: {n_ins} inserted, {n_upd} updated")
    else:
        print("  Dry run — skipping Snowflake load")


if __name__ == "__main__":
    run()
