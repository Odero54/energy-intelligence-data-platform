"""Download GADM 4.1 level-2 admin boundaries → RAW.ADMIN_BOUNDARIES."""

import io
import zipfile
from pathlib import Path

import geopandas as gpd
import pandas as pd
import requests
from dotenv import load_dotenv

load_dotenv()

# UC Davis GADM 4.1 download URL
GADM_URL = "https://geodata.ucdavis.edu/gadm/gadm4.1/json/gadm41_{iso3}_{level}.json.zip"
ADMIN_LEVEL = 2

TARGET_COUNTRIES = {
    "KEN": "Kenya",
    "NGA": "Nigeria",
    "IND": "India",
    "TZA": "Tanzania",
    "RWA": "Rwanda",
    "CIV": "Cote d'Ivoire",
    "PAK": "Pakistan",
}

RAW_DIR = Path(__file__).parents[2] / "data" / "raw" / "admin_boundaries"

OUTPUT_COLS = [
    "gid",
    "country_code",
    "country_name",
    "admin_level",
    "admin_name",
    "admin_name_alt",
    "area_km2",
    "geometry_wkt",
    "source_dataset",
    "_source_file",
]


def extract_country(iso3: str) -> gpd.GeoDataFrame:
    cache = RAW_DIR / f"gadm41_{iso3}_{ADMIN_LEVEL}.parquet"
    if cache.exists():
        print(f"    Using cached GADM data for {iso3}")
        return gpd.read_parquet(cache)

    url = GADM_URL.format(iso3=iso3, level=ADMIN_LEVEL)
    print(f"    Downloading GADM {iso3} level {ADMIN_LEVEL}...")
    resp = requests.get(url, timeout=300)
    resp.raise_for_status()

    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        geojson_name = next(n for n in zf.namelist() if n.endswith(".json"))
        with zf.open(geojson_name) as f:
            gdf = gpd.read_file(f)

    gdf.to_parquet(cache)
    return gdf


def transform_country(gdf: gpd.GeoDataFrame, iso3: str) -> pd.DataFrame:
    gdf = gdf.to_crs("EPSG:4326")

    rows = []
    for _, row in gdf.iterrows():
        geom = row["geometry"]
        # Simplify to reduce WKT size while preserving shape
        if geom is not None:
            geom = geom.simplify(0.001, preserve_topology=True)
            geometry_wkt = geom.wkt
        else:
            geometry_wkt = ""

        rows.append(
            {
                "gid": str(row.get("GID_2", row.get("GID_1", ""))),
                "country_code": iso3,
                "country_name": TARGET_COUNTRIES[iso3],
                "admin_level": str(ADMIN_LEVEL),
                "admin_name": str(row.get("NAME_2", row.get("NAME_1", ""))),
                "admin_name_alt": str(row.get("VARNAME_2", row.get("VARNAME_1", ""))),
                "area_km2": "",
                "geometry_wkt": geometry_wkt,
                "source_dataset": "GADM 4.1",
                "_source_file": f"gadm41_{iso3}_{ADMIN_LEVEL}.json",
            }
        )

    return pd.DataFrame(rows)[OUTPUT_COLS]


def run(dry_run: bool = False) -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    all_dfs: list[pd.DataFrame] = []

    for iso3, name in TARGET_COUNTRIES.items():
        print(f"  Processing {name} ({iso3})...")
        try:
            gdf = extract_country(iso3)
            df = transform_country(gdf, iso3)
            all_dfs.append(df)
            print(f"    {len(df)} admin-2 regions")
        except Exception as e:
            print(f"    ERROR for {iso3}: {e}")

    combined = pd.concat(all_dfs, ignore_index=True)
    cache_path = RAW_DIR / "admin_boundaries_all.parquet"
    combined.to_parquet(cache_path, index=False)
    print(f"  Total: {len(combined)} boundaries across {len(all_dfs)} countries → {cache_path}")

    if not dry_run:
        from ingestion._snowflake import upsert_dataframe

        n_ins, n_upd = upsert_dataframe(combined, "ADMIN_BOUNDARIES", merge_keys=["gid"])
        print(f"  Upserted → RAW.ADMIN_BOUNDARIES: {n_ins} inserted, {n_upd} updated")
    else:
        print("  Dry run — skipping Snowflake load")


if __name__ == "__main__":
    run()
