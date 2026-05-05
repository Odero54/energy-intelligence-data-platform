"""Download WRI Global Power Plant Database → RAW.POWER_PLANTS."""

import io
import zipfile
from pathlib import Path

import pandas as pd
import requests
from dotenv import load_dotenv

load_dotenv()

# WRI Global Power Plant Database v1.3.0
WRI_URL = (
    "https://datasets.wri.org/dataset/a60ac839-2016-4d65-9c00-0f48e6b8e5a6"
    "/resource/f23f1f22-68c7-4ab3-96e1-38d4ccf39e7a"
    "/download/globalpowerplantdatabasev130.zip"
)
# Fallback: direct GitHub mirror
WRI_URL_FALLBACK = (
    "https://raw.githubusercontent.com/wri/global-power-plant-database"
    "/master/output_database/global_power_plant_database.csv"
)

TARGET_COUNTRIES = {"KEN", "NGA", "IND", "TZA", "RWA", "CIV", "PAK"}

RAW_DIR = Path(__file__).parents[2] / "data" / "raw" / "power_plants"

OUTPUT_COLS = [
    "plant_id",
    "country",
    "country_long",
    "name",
    "capacity_mw",
    "latitude",
    "longitude",
    "primary_fuel",
    "other_fuel1",
    "other_fuel2",
    "other_fuel3",
    "commissioning_year",
    "owner",
    "source",
    "url",
    "geolocation_source",
    "wepp_id",
    "year_of_capacity_data",
    "generation_gwh_2013",
    "generation_gwh_2014",
    "generation_gwh_2015",
    "generation_gwh_2016",
    "generation_gwh_2017",
    "generation_gwh_2018",
    "generation_gwh_2019",
    "_source_file",
]


def _download_zip(url: str) -> pd.DataFrame:
    resp = requests.get(url, timeout=180)
    resp.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        csv_name = next(n for n in zf.namelist() if n.endswith(".csv"))
        with zf.open(csv_name) as f:
            return pd.read_csv(f, low_memory=False)


def extract() -> pd.DataFrame:
    cache = RAW_DIR / "global_power_plants_raw.parquet"
    if cache.exists():
        print("  Using cached WRI power plants data")
        return pd.read_parquet(cache)

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    print("  Downloading WRI Global Power Plant Database v1.3.0...")
    try:
        raw = _download_zip(WRI_URL)
    except Exception as e:
        print(f"  Primary URL failed ({e}), trying fallback...")
        resp = requests.get(WRI_URL_FALLBACK, timeout=180)
        resp.raise_for_status()
        raw = pd.read_csv(io.StringIO(resp.text), low_memory=False)

    raw.to_parquet(cache, index=False)
    return raw


def transform(raw: pd.DataFrame) -> pd.DataFrame:
    df = raw[raw["country"].isin(TARGET_COUNTRIES)].copy()
    df = df.rename(columns={"gppd_idnr": "plant_id"})
    df["_source_file"] = "wri_global_power_plant_database_v130"

    for col in OUTPUT_COLS:
        if col not in df.columns:
            df[col] = ""

    df = df[OUTPUT_COLS].fillna("").astype(str).replace("nan", "")
    return df.reset_index(drop=True)


def run(dry_run: bool = False) -> None:
    raw = extract()
    df = transform(raw)

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    cache_path = RAW_DIR / "power_plants_filtered.parquet"
    df.to_parquet(cache_path, index=False)
    print(f"  Transformed: {len(df)} rows for {sorted(df['country'].unique())} → {cache_path}")

    if not dry_run:
        from ingestion._snowflake import upsert_dataframe

        n_ins, n_upd = upsert_dataframe(df, "POWER_PLANTS", merge_keys=["plant_id"])
        print(f"  Upserted → RAW.POWER_PLANTS: {n_ins} inserted, {n_upd} updated")
    else:
        print("  Dry run — skipping Snowflake load")


if __name__ == "__main__":
    run()
