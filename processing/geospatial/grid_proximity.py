"""Compute distance from each admin-region centroid to the nearest grid line.

Output: data/processed/grid_proximity.parquet
Schema: admin_gid, country_code, admin_name, admin_level,
        dist_to_grid_km, grid_proximity_category

Proximity tiers (based on rural electrification literature):
  on_grid   < 10 km
  near_grid  10 – 50 km
  off_grid  > 50 km

Pre-requisites:
  - make ingest-boundaries   (data/raw/admin_boundaries/admin_boundaries_all.parquet)
  - make ingest-grid         (data/raw/grid/grid_all.parquet)
"""

from pathlib import Path

import geopandas as gpd
import pandas as pd
from dotenv import load_dotenv
from shapely import wkt as shapely_wkt

load_dotenv()

BOUNDARIES_CACHE = (
    Path(__file__).parents[2] / "data" / "raw" / "admin_boundaries" / "admin_boundaries_all.parquet"
)
GRID_CACHE = Path(__file__).parents[2] / "data" / "raw" / "grid" / "grid_all.parquet"
PROCESSED_DIR = Path(__file__).parents[2] / "data" / "processed"

# Distance thresholds in km
TIER_ON_GRID = 10.0
TIER_NEAR_GRID = 50.0

OUTPUT_COLS = [
    "admin_gid",
    "country_code",
    "admin_name",
    "admin_level",
    "dist_to_grid_km",
    "grid_proximity_category",
]


def _proximity_category(dist_km: float) -> str:
    if dist_km < TIER_ON_GRID:
        return "on_grid"
    if dist_km < TIER_NEAR_GRID:
        return "near_grid"
    return "off_grid"


def compute_proximity(
    admin_gdf: gpd.GeoDataFrame,
    grid_gdf: gpd.GeoDataFrame,
) -> pd.DataFrame:
    """Return a DataFrame with dist_to_grid_km and category per admin region.

    Both GeoDataFrames must be in EPSG:4326. Computation is done in EPSG:3857
    (Web Mercator, metric) so distances come back in metres.
    """
    # Normalise: the boundaries parquet uses 'gid'; rename to 'admin_gid' for output
    gid_col = "gid" if "gid" in admin_gdf.columns else "admin_gid"

    # Project to metric CRS
    admin_proj = admin_gdf[
        [gid_col, "country_code", "admin_name", "admin_level", "geometry"]
    ].copy()
    admin_proj = admin_proj.rename(columns={gid_col: "admin_gid"})
    admin_proj = admin_proj.to_crs("EPSG:3857")

    grid_proj = grid_gdf[["geometry"]].copy()
    grid_proj = grid_proj[~grid_proj.geometry.isna() & ~grid_proj.geometry.is_empty]
    grid_proj = grid_proj.to_crs("EPSG:3857")

    # Replace polygon geometries with centroids for distance calculation
    centroids = admin_proj.copy()
    centroids["geometry"] = admin_proj.geometry.centroid

    # sjoin_nearest — finds nearest grid line per centroid (GeoPandas ≥ 0.10)
    joined = gpd.sjoin_nearest(
        centroids,
        grid_proj.reset_index(drop=True),
        how="left",
        distance_col="dist_m",
    )

    # Deduplicate: a centroid might match multiple equidistant lines
    joined = joined.groupby("admin_gid", as_index=False)["dist_m"].min()

    # Merge back to get full admin attributes
    result = admin_proj[["admin_gid", "country_code", "admin_name", "admin_level"]].merge(
        joined[["admin_gid", "dist_m"]], on="admin_gid", how="left"
    )

    result["dist_to_grid_km"] = (result["dist_m"] / 1000).round(3)
    result["grid_proximity_category"] = result["dist_to_grid_km"].apply(
        lambda d: _proximity_category(d) if pd.notna(d) else "unknown"
    )

    return result[OUTPUT_COLS]


def run(dry_run: bool = False) -> None:
    for path, name in [(BOUNDARIES_CACHE, "admin boundaries"), (GRID_CACHE, "grid data")]:
        if not path.exists():
            raise FileNotFoundError(
                f"{name} cache not found at {path}.\n"
                "Run `make ingest-boundaries` and `make ingest-grid` first."
            )

    print("  Loading admin boundaries...")
    df_admin = pd.read_parquet(BOUNDARIES_CACHE)
    df_admin["geometry"] = df_admin["geometry_wkt"].apply(
        lambda w: shapely_wkt.loads(w) if w else None
    )
    admin_gdf = gpd.GeoDataFrame(df_admin, geometry="geometry", crs="EPSG:4326")
    print(f"    {len(admin_gdf)} regions")

    print("  Loading grid infrastructure...")
    df_grid = pd.read_parquet(GRID_CACHE)
    df_grid["geometry"] = df_grid["geometry_wkt"].apply(
        lambda w: shapely_wkt.loads(w) if w else None
    )
    grid_gdf = gpd.GeoDataFrame(df_grid, geometry="geometry", crs="EPSG:4326")
    print(f"    {len(grid_gdf)} grid features")

    print("  Computing proximity (sjoin_nearest)...")
    result = compute_proximity(admin_gdf, grid_gdf)

    tiers = result["grid_proximity_category"].value_counts().to_dict()
    print(f"  Tiers: {tiers}")

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    out_path = PROCESSED_DIR / "grid_proximity.parquet"
    result.to_parquet(out_path, index=False)
    print(f"  Saved: {len(result)} rows → {out_path}")

    if not dry_run:
        print("  (Grid proximity is used as input to dbt — no direct Snowflake load needed)")
    else:
        print("  Dry run complete")


if __name__ == "__main__":
    run()
