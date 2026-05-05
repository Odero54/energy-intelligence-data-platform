"""Local GeoTIFF nightlights processing pipeline.

Use this when VIIRS GeoTIFFs are already on disk (e.g., exported from GEE
to Google Drive and downloaded to data/raw/nightlights/).

Expected file naming convention:
    data/raw/nightlights/viirs_{country_code}_{year}.tif   (annual)
    data/raw/nightlights/viirs_{country_code}_{year}_{month:02d}.tif  (monthly)

All stats are computed via processing.raster.zonal_stats.
"""

import re
from pathlib import Path

import geopandas as gpd
import pandas as pd
from dotenv import load_dotenv

from processing.raster.zonal_stats import zonal_stats_gdf

load_dotenv()

NIGHTLIGHTS_DIR = Path(__file__).parents[2] / "data" / "raw" / "nightlights"
BOUNDARIES_CACHE = (
    Path(__file__).parents[2] / "data" / "raw" / "admin_boundaries" / "admin_boundaries_all.parquet"
)

# Filename pattern: viirs_KEN_2022.tif or viirs_KEN_2022_03.tif
_FNAME_RE = re.compile(r"viirs_([A-Z]{3})_(\d{4})(?:_(\d{2}))?\.tif$", re.IGNORECASE)

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


def _parse_filename(path: Path) -> tuple[str, str, str] | None:
    """Return (country_code, year, month) or None if filename doesn't match."""
    m = _FNAME_RE.match(path.name)
    if not m:
        return None
    country, year, month = m.group(1).upper(), m.group(2), m.group(3) or "annual"
    return country, year, month


def process_file(
    tif_path: Path,
    boundaries: gpd.GeoDataFrame,
) -> pd.DataFrame:
    parsed = _parse_filename(tif_path)
    if parsed is None:
        raise ValueError(f"Cannot parse filename: {tif_path.name}")

    country_code, year, month = parsed
    country_gdf = boundaries[boundaries["country_code"] == country_code].copy()
    if country_gdf.empty:
        raise ValueError(f"No admin boundaries found for {country_code}")

    stats_list = zonal_stats_gdf(tif_path, country_gdf, band=1, all_touched=False)

    rows = []
    for i, (_, row) in enumerate(country_gdf.iterrows()):
        if i >= len(stats_list):
            break
        s = stats_list[i]
        rows.append(
            {
                "admin_gid": str(row.get("gid", "")),
                "country_code": country_code,
                "admin_name": str(row.get("admin_name", "")),
                "admin_level": str(row.get("admin_level", "")),
                "year": year,
                "month": month,
                "mean_radiance": str(round(max(0.0, s["mean"]), 6)),
                "max_radiance": str(round(max(0.0, s["max"]), 6)),
                "min_radiance": str(round(max(0.0, s["min"]), 6)),
                "sum_radiance": str(round(max(0.0, s["sum"]), 6)),
                "pixel_count": str(s["count"]),
                "sensor": "VIIRS/DNB",
                "product": "local_geotiff",
                "_source_file": tif_path.name,
            }
        )

    return pd.DataFrame(rows)[OUTPUT_COLS]


def run(dry_run: bool = False) -> None:
    if not BOUNDARIES_CACHE.exists():
        raise FileNotFoundError(
            f"Admin boundaries cache not found at {BOUNDARIES_CACHE}. "
            "Run `make ingest-boundaries` first."
        )

    tif_files = sorted(NIGHTLIGHTS_DIR.glob("viirs_*.tif"))
    if not tif_files:
        print(
            f"  No VIIRS GeoTIFFs found in {NIGHTLIGHTS_DIR}.\n"
            "  Expected filenames: viirs_KEN_2022.tif or viirs_KEN_2022_03.tif\n"
            "  Use `make ingest-nightlights` (GEE) instead, or download and rename files."
        )
        return

    from shapely import wkt as shapely_wkt

    df = pd.read_parquet(BOUNDARIES_CACHE)
    df["geometry"] = df["geometry_wkt"].apply(lambda w: shapely_wkt.loads(w) if w else None)
    boundaries = gpd.GeoDataFrame(df, geometry="geometry", crs="EPSG:4326")
    all_dfs: list[pd.DataFrame] = []

    for tif in tif_files:
        print(f"  Processing {tif.name}...")
        try:
            df = process_file(tif, boundaries)
            all_dfs.append(df)
            print(f"    {len(df)} regions")
        except Exception as e:
            print(f"    ERROR: {e}")

    if not all_dfs:
        print("  No data processed.")
        return

    combined = pd.concat(all_dfs, ignore_index=True)
    out_path = NIGHTLIGHTS_DIR / "nightlights_local.parquet"
    combined.to_parquet(out_path, index=False)
    print(f"  Total: {len(combined)} records → {out_path}")

    if not dry_run:
        from ingestion._snowflake import load_dataframe

        nrows = load_dataframe(combined, "NIGHTLIGHTS")
        print(f"  Loaded: {nrows} rows → RAW.NIGHTLIGHTS")
    else:
        print("  Dry run — skipping Snowflake load")


if __name__ == "__main__":
    run()
