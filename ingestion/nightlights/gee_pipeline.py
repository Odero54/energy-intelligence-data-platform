"""Extract VIIRS nightlights via Google Earth Engine → RAW.NIGHTLIGHTS.

Strategy: annual median composite per country, zonal stats run server-side
via reduceRegions. Results fetched with getInfo() (no Drive export needed
for <5000 features).

Pre-requisite: Day 2 admin boundaries must be ingested so the parquet cache
at data/raw/admin_boundaries/admin_boundaries_all.parquet exists.
"""

from pathlib import Path

import ee
import geopandas as gpd
import pandas as pd
from dotenv import load_dotenv

from ingestion.nightlights.gee_auth import authenticate

load_dotenv()

VIIRS_COLLECTION = "NOAA/VIIRS/DNB/MONTHLY_V1/VCMSLCFG"
VIIRS_BAND = "avg_rad"
VIIRS_SCALE = 500  # native resolution ~463 m, 500 m is safe

YEARS = list(range(2019, 2024))  # 2019–2023 inclusive
BATCH_SIZE = 150  # features per reduceRegions call (keeps payloads manageable)

BOUNDARIES_CACHE = (
    Path(__file__).parents[2] / "data" / "raw" / "admin_boundaries" / "admin_boundaries_all.parquet"
)
RAW_DIR = Path(__file__).parents[2] / "data" / "raw" / "nightlights"

OUTPUT_COLS = [
    "admin_gid",
    "country_code",
    "admin_name",
    "admin_level",
    "year",
    "month",
    "mean_radiance",
    "max_radiance",
    "min_radiance",
    "sum_radiance",
    "pixel_count",
    "sensor",
    "product",
    "_source_file",
]


def _annual_composite(year: int) -> ee.Image:
    return (
        ee.ImageCollection(VIIRS_COLLECTION)
        .filterDate(f"{year}-01-01", f"{year}-12-31")
        .select(VIIRS_BAND)
        .median()
    )


def _gdf_to_ee_fc(gdf: gpd.GeoDataFrame) -> ee.FeatureCollection:
    """Convert a GeoDataFrame to a GEE FeatureCollection."""
    props_cols = ["gid", "country_code", "admin_name", "admin_level"]
    features = []
    for _, row in gdf.iterrows():
        if row.geometry is None or row.geometry.is_empty:
            continue
        geom_dict = row.geometry.__geo_interface__
        props = {col: str(row[col]) for col in props_cols if col in gdf.columns}
        features.append(ee.Feature(ee.Geometry(geom_dict), props))
    return ee.FeatureCollection(features)


def _reduce_regions(image: ee.Image, fc: ee.FeatureCollection) -> list[dict]:
    reducer = (
        ee.Reducer.mean()
        .combine(ee.Reducer.max(), "", True)
        .combine(ee.Reducer.min(), "", True)
        .combine(ee.Reducer.sum(), "", True)
        .combine(ee.Reducer.count(), "", True)
    )
    stats = image.reduceRegions(collection=fc, reducer=reducer, scale=VIIRS_SCALE)
    return stats.getInfo()["features"]


def extract_year(gdf: gpd.GeoDataFrame, year: int) -> pd.DataFrame:
    image = _annual_composite(year)
    records: list[dict] = []

    # Process in batches to keep GEE request sizes manageable
    for start in range(0, len(gdf), BATCH_SIZE):
        batch = gdf.iloc[start : start + BATCH_SIZE]
        fc = _gdf_to_ee_fc(batch)
        features = _reduce_regions(image, fc)

        for f in features:
            p = f["properties"]
            # avg_rad can be slightly negative (sensor noise) — clamp to 0
            mean_rad = max(0.0, p.get("mean") or 0.0)
            records.append(
                {
                    "admin_gid": p.get("gid", ""),
                    "country_code": p.get("country_code", ""),
                    "admin_name": p.get("admin_name", ""),
                    "admin_level": p.get("admin_level", ""),
                    "year": str(year),
                    "month": "annual",
                    "mean_radiance": str(round(mean_rad, 6)),
                    "max_radiance": str(round(max(0.0, p.get("max") or 0.0), 6)),
                    "min_radiance": str(round(max(0.0, p.get("min") or 0.0), 6)),
                    "sum_radiance": str(round(max(0.0, p.get("sum") or 0.0), 6)),
                    "pixel_count": str(int(p.get("count") or 0)),
                    "sensor": "VIIRS/DNB",
                    "product": "VCMSLCFG_annual_median",
                    "_source_file": f"gee_viirs_{year}",
                }
            )

    return pd.DataFrame(records)[OUTPUT_COLS] if records else pd.DataFrame(columns=OUTPUT_COLS)


def run(dry_run: bool = False) -> None:
    if not BOUNDARIES_CACHE.exists():
        raise FileNotFoundError(
            f"Admin boundaries cache not found at {BOUNDARIES_CACHE}. "
            "Run `make ingest-boundaries` first."
        )

    authenticate()

    from shapely import wkt as shapely_wkt

    df = pd.read_parquet(BOUNDARIES_CACHE)
    df["geometry"] = df["geometry_wkt"].apply(lambda w: shapely_wkt.loads(w) if w else None)
    gdf = gpd.GeoDataFrame(df, geometry="geometry", crs="EPSG:4326")

    print(f"  Loaded {len(gdf)} admin boundaries")

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    all_dfs: list[pd.DataFrame] = []

    for year in YEARS:
        print(f"  Extracting VIIRS {year}...")
        df = extract_year(gdf, year)
        print(f"    {len(df)} records")
        all_dfs.append(df)

    combined = pd.concat(all_dfs, ignore_index=True)
    cache_path = RAW_DIR / "nightlights_annual.parquet"
    combined.to_parquet(cache_path, index=False)
    print(f"  Total: {len(combined)} records → {cache_path}")

    if not dry_run:
        from ingestion._snowflake import upsert_dataframe

        # month is NULL for annual composites — upsert_dataframe uses a
        # NULL-safe join so annual rows are matched correctly on re-runs.
        n_ins, n_upd = upsert_dataframe(
            combined,
            "NIGHTLIGHTS",
            merge_keys=["admin_gid", "year", "month"],
        )
        print(f"  Upserted → RAW.NIGHTLIGHTS: {n_ins} inserted, {n_upd} updated")
    else:
        print("  Dry run — skipping Snowflake load")


if __name__ == "__main__":
    run()
