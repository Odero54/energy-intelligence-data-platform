"""Download WorldPop 1km population rasters and aggregate to admin-2 level.

Source:  WorldPop Global 2015-2030, 1km, constrained (R2025A)
URL:     https://hub.worldpop.org/geodata/listing?id=136

Strategy
--------
- Download rasters for SOURCE_YEARS (2019–2023) from the constrained R2025A dataset,
  which provides modelled population estimates for all years up to 2030.
- For each country × year, sum pixel values within every admin-2 polygon to get
  total_population, then derive area_km2 and pop_density_km2.
- Rasters and processed parquets are cached so re-runs skip already-done work.
"""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import pyproj
import rasterio
import requests
from dotenv import load_dotenv
from rasterio.mask import mask as rio_mask
from shapely import wkt as shapely_wkt

load_dotenv()

# WorldPop Hub API — constrained 2015-2030 1km resolution (R2025A)
WORLDPOP_HUB_API = "https://hub.worldpop.org/rest/data/pop/G2_CN_POP_R25A_1km"

SOURCE_YEARS = [2019, 2020, 2021, 2022, 2023]
TARGET_YEARS = [2019, 2020, 2021, 2022, 2023]

TARGET_COUNTRIES = {
    "KEN": "Kenya",
    "NGA": "Nigeria",
    "IND": "India",
    "TZA": "Tanzania",
    "RWA": "Rwanda",
    "CIV": "Cote d'Ivoire",
    "PAK": "Pakistan",
}

BOUNDARIES_CACHE = (
    Path(__file__).parents[2] / "data" / "raw" / "admin_boundaries" / "admin_boundaries_all.parquet"
)
RAW_DIR = Path(__file__).parents[2] / "data" / "raw" / "population"

OUTPUT_COLS = [
    "admin_gid",
    "country_code",
    "admin_name",
    "admin_level",
    "year",
    "total_population",
    "area_km2",
    "pop_density_km2",
    "source_dataset",
    "_source_file",
]

_GEOD = pyproj.Geod(ellps="WGS84")


def _worldpop_url(iso3: str, year: int) -> str:
    """Discover the download URL via the WorldPop Hub REST API."""
    resp = requests.get(WORLDPOP_HUB_API, params={"iso3": iso3}, timeout=30)
    resp.raise_for_status()
    for item in resp.json().get("data", []):
        if str(item.get("popyear")) == str(year):
            files = item.get("files", [])
            if files:
                return files[0]
    raise ValueError(f"No WorldPop R2025A file found for {iso3} {year}")


def _download_raster(iso3: str, year: int, dest: Path) -> None:
    url = _worldpop_url(iso3, year)
    print(f"    Downloading {url}")
    with requests.get(url, stream=True, timeout=600) as r:
        r.raise_for_status()
        total_bytes = int(r.headers.get("content-length", 0))
        downloaded = 0
        with open(dest, "wb") as f:
            for chunk in r.iter_content(chunk_size=1024 * 1024):
                f.write(chunk)
                downloaded += len(chunk)
                if total_bytes:
                    print(
                        f"\r      {downloaded / 1e6:.1f} / {total_bytes / 1e6:.1f} MB",
                        end="",
                        flush=True,
                    )
        print()


def _geodesic_area_km2(geom) -> float:
    """Geodesic polygon area in km² via pyproj Geod (WGS84 ellipsoid)."""
    area_m2, _ = _GEOD.geometry_area_perimeter(geom)
    return abs(area_m2) / 1e6


def _zonal_pop(raster_path: Path, gdf: gpd.GeoDataFrame) -> list[float]:
    """Sum raster pixel values within each polygon = population count."""
    results: list[float] = []
    with rasterio.open(raster_path) as src:
        nodata = src.nodata
        for geom in gdf.geometry:
            if geom is None or geom.is_empty:
                results.append(0.0)
                continue
            try:
                masked, _ = rio_mask(src, [geom], crop=True, all_touched=False)
                data = masked[0].astype(np.float64)
                if nodata is not None:
                    data[data == nodata] = np.nan
                # WorldPop can have tiny negatives from resampling — clamp to 0
                data = np.where(data < 0, 0.0, data)
                results.append(float(np.nansum(data)))
            except Exception:
                results.append(0.0)
    return results


def _compute_country_year(iso3: str, src_year: int, admin_gdf: gpd.GeoDataFrame) -> pd.DataFrame:
    """Run zonal stats for one country × year; return DataFrame."""
    raster_path = RAW_DIR / f"{iso3.lower()}_{src_year}.tif"
    if not raster_path.exists():
        _download_raster(iso3, src_year, raster_path)

    country_gdf = admin_gdf[
        (admin_gdf["country_code"] == iso3) & (admin_gdf["admin_level"].astype(str) == "2")
    ].copy()

    if country_gdf.empty:
        print(f"    No admin-2 boundaries for {iso3}")
        return pd.DataFrame(columns=OUTPUT_COLS)

    print(f"    Zonal stats: {len(country_gdf)} admin-2 regions ...")
    populations = _zonal_pop(raster_path, country_gdf)

    gid_col = "gid" if "gid" in country_gdf.columns else "admin_gid"
    rows = []
    for i, (_, row) in enumerate(country_gdf.iterrows()):
        total_pop = populations[i]
        area = _geodesic_area_km2(row.geometry) if row.geometry else 0.0
        density = total_pop / area if area > 0 else 0.0
        rows.append(
            {
                "admin_gid": str(row[gid_col]),
                "country_code": iso3,
                "admin_name": str(row.get("admin_name", "")),
                "admin_level": "2",
                "year": str(src_year),
                "total_population": str(round(total_pop)),
                "area_km2": str(round(area, 4)),
                "pop_density_km2": str(round(density, 6)),
                "source_dataset": f"WorldPop 1km constrained R2025A {src_year}",
                "_source_file": f"worldpop_R2025A_{iso3.lower()}_{src_year}",
            }
        )

    return pd.DataFrame(rows)[OUTPUT_COLS]


def extract_country(iso3: str, admin_gdf: gpd.GeoDataFrame) -> pd.DataFrame:
    """Return population rows for all TARGET_YEARS for one country."""
    result_dfs: list[pd.DataFrame] = []

    for year in SOURCE_YEARS:
        proc_cache = RAW_DIR / f"pop_{iso3.lower()}_{year}.parquet"
        if proc_cache.exists():
            print(f"    {iso3} {year}: using cache")
            result_dfs.append(pd.read_parquet(proc_cache))
        else:
            df = _compute_country_year(iso3, year, admin_gdf)
            df.to_parquet(proc_cache, index=False)
            result_dfs.append(df)
            print(f"    {iso3} {year}: {len(df)} rows computed")

    return pd.concat(result_dfs, ignore_index=True)


def run(dry_run: bool = False) -> None:
    if not BOUNDARIES_CACHE.exists():
        raise FileNotFoundError(
            f"Admin boundaries cache not found at {BOUNDARIES_CACHE}. "
            "Run `make ingest-boundaries` first."
        )

    RAW_DIR.mkdir(parents=True, exist_ok=True)

    df_bounds = pd.read_parquet(BOUNDARIES_CACHE)
    df_bounds["geometry"] = df_bounds["geometry_wkt"].apply(
        lambda w: shapely_wkt.loads(w) if w else None
    )
    admin_gdf = gpd.GeoDataFrame(df_bounds, geometry="geometry", crs="EPSG:4326")
    print(f"Loaded {len(admin_gdf)} admin boundaries")

    all_dfs: list[pd.DataFrame] = []
    for iso3, name in TARGET_COUNTRIES.items():
        print(f"  Processing {name} ({iso3}) ...")
        try:
            df = extract_country(iso3, admin_gdf)
            all_dfs.append(df)
            print(f"    {iso3}: {len(df)} rows total")
        except Exception as e:
            print(f"    ERROR {iso3}: {e}")

    if not all_dfs:
        raise RuntimeError("No population data retrieved for any country.")

    combined = pd.concat(all_dfs, ignore_index=True)
    out_path = RAW_DIR / "population_all.parquet"
    combined.to_parquet(out_path, index=False)
    print(f"Total: {len(combined)} rows → {out_path}")

    if not dry_run:
        from ingestion._snowflake import upsert_dataframe

        n_ins, n_upd = upsert_dataframe(
            combined,
            "POPULATION_DENSITY",
            merge_keys=["admin_gid", "year"],
        )
        print(f"Upserted → RAW.POPULATION_DENSITY: {n_ins} inserted, {n_upd} updated")
    else:
        print("Dry run — skipping Snowflake load")


if __name__ == "__main__":
    run()
