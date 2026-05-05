"""Rasterio-based zonal statistics for polygon features over a raster.

Used as a local fallback when GeoTIFFs are available (e.g., exported from
GEE to Google Drive and downloaded locally).
"""

from pathlib import Path
from typing import Any

import numpy as np
import rasterio
from rasterio.mask import mask as rio_mask


def _stats_from_open_src(
    src: rasterio.io.DatasetReader,
    geometries: list[dict[str, Any]],
    band: int,
    nodata: float | None,
    all_touched: bool,
) -> list[dict[str, float | int]]:
    results: list[dict[str, float | int]] = []
    raster_nodata = nodata if nodata is not None else src.nodata

    for geom_dict in geometries:
        try:
            data, _ = rio_mask(
                src,
                [geom_dict],
                crop=True,
                nodata=np.nan,
                all_touched=all_touched,
                filled=True,
            )
            band_data = data[band - 1].astype(np.float64)

            if raster_nodata is not None and not np.isnan(raster_nodata):
                band_data[band_data == raster_nodata] = np.nan

            valid = band_data[~np.isnan(band_data)]
            total = band_data.size

            if valid.size == 0:
                continue

            results.append(
                {
                    "mean": float(np.mean(valid)),
                    "max": float(np.max(valid)),
                    "min": float(np.min(valid)),
                    "sum": float(np.sum(valid)),
                    "count": int(valid.size),
                    "valid_pct": round(valid.size / total * 100, 2),
                }
            )
        except Exception:
            continue

    return results


def zonal_stats(
    raster_src: "str | Path | rasterio.io.DatasetReader",
    geometries: list[dict[str, Any]],
    band: int = 1,
    nodata: float | None = None,
    all_touched: bool = False,
) -> list[dict[str, float | int]]:
    """Compute per-polygon statistics over a raster band.

    Args:
        raster_src: Path to a GeoTIFF, a MemoryFile, or an already-open DatasetReader.
        geometries: List of GeoJSON geometry dicts ({"type": ..., "coordinates": ...}).
        band: 1-indexed band number to read.
        nodata: Value to treat as no-data. Falls back to the raster's nodata.
        all_touched: If True, include pixels touching polygon edges.

    Returns:
        List of dicts with keys: mean, max, min, sum, count, valid_pct.
        Entries where the polygon has zero valid pixels are omitted.
    """
    if hasattr(raster_src, "read"):
        # Already an open dataset — use directly
        return _stats_from_open_src(raster_src, geometries, band, nodata, all_touched)

    with rasterio.open(raster_src) as src:
        return _stats_from_open_src(src, geometries, band, nodata, all_touched)


def zonal_stats_gdf(
    raster_path: str | Path,
    gdf: Any,  # geopandas.GeoDataFrame
    band: int = 1,
    nodata: float | None = None,
    all_touched: bool = False,
) -> list[dict[str, float | int]]:
    """Convenience wrapper that accepts a GeoDataFrame instead of raw geometry dicts."""

    gdf_proj = gdf.to_crs("EPSG:4326") if gdf.crs else gdf
    geom_dicts = [
        row.geometry.__geo_interface__
        for _, row in gdf_proj.iterrows()
        if row.geometry is not None and not row.geometry.is_empty
    ]
    return zonal_stats(raster_path, geom_dicts, band=band, nodata=nodata, all_touched=all_touched)
