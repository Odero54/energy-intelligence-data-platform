"""Unit tests for processing.raster.zonal_stats (in-memory rasters, no file I/O)."""

import numpy as np
import pytest
from affine import Affine
from rasterio.io import MemoryFile
from shapely.geometry import box

from processing.raster.zonal_stats import zonal_stats

_TRANSFORM = Affine(1.0, 0.0, 0.0, 0.0, -1.0, 3.0)  # 3×3 grid, 1-degree pixels


def _open_mem(data: np.ndarray, nodata: float | None = None):
    """Return an open MemoryFile dataset (caller must close)."""
    mf = MemoryFile()
    kwargs = dict(
        driver="GTiff",
        height=data.shape[0],
        width=data.shape[1],
        count=1,
        dtype="float32",
        crs="EPSG:4326",
        transform=_TRANSFORM,
    )
    if nodata is not None:
        kwargs["nodata"] = nodata
    with mf.open(**kwargs) as dst:
        dst.write(data.astype("float32"), 1)
    return mf.open()  # open for reading; caller owns this


def test_basic_mean():
    data = np.arange(1, 10, dtype="float32").reshape(3, 3)
    with _open_mem(data) as src:
        # Polygon covers interior of the 3×3 raster
        geom = box(0.1, 0.1, 2.9, 2.9).__geo_interface__
        results = zonal_stats(src, [geom])

    assert len(results) == 1
    assert results[0]["mean"] == pytest.approx(5.0, abs=1.5)


def test_stats_keys():
    data = np.ones((3, 3), dtype="float32")
    with _open_mem(data) as src:
        geom = box(0.1, 0.1, 2.9, 2.9).__geo_interface__
        results = zonal_stats(src, [geom])

    assert set(results[0].keys()) == {"mean", "max", "min", "sum", "count", "valid_pct"}


def test_empty_geometry_skipped():
    data = np.ones((3, 3), dtype="float32")
    with _open_mem(data) as src:
        # Polygon entirely outside the raster extent
        geom = box(100, 100, 110, 110).__geo_interface__
        results = zonal_stats(src, [geom])

    assert results == []


def test_nodata_excluded():
    data = np.array(
        [[1.0, 2.0, -9999.0], [4.0, 5.0, -9999.0], [7.0, 8.0, 9.0]],
        dtype="float32",
    )
    with _open_mem(data, nodata=-9999.0) as src:
        geom = box(0.1, 0.1, 2.9, 2.9).__geo_interface__
        results = zonal_stats(src, [geom])

    assert len(results) == 1
    assert results[0]["max"] < 100  # -9999 must not appear as max


def test_uniform_raster_stats():
    data = np.full((3, 3), 7.0, dtype="float32")
    with _open_mem(data) as src:
        geom = box(0.1, 0.1, 2.9, 2.9).__geo_interface__
        results = zonal_stats(src, [geom])

    assert results[0]["mean"] == pytest.approx(7.0, abs=0.1)
    assert results[0]["max"] == pytest.approx(7.0, abs=0.1)
    assert results[0]["min"] == pytest.approx(7.0, abs=0.1)
