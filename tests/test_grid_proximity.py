"""Unit tests for processing.geospatial.grid_proximity (no file I/O)."""

import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import LineString, Polygon

from processing.geospatial.grid_proximity import (
    _proximity_category,
    compute_proximity,
)


def _make_admin_gdf() -> gpd.GeoDataFrame:
    """Three admin polygons at known positions."""
    return gpd.GeoDataFrame(
        {
            "admin_gid": ["A1", "A2", "A3"],
            "country_code": ["KEN", "KEN", "KEN"],
            "admin_name": ["Region 1", "Region 2", "Region 3"],
            "admin_level": ["2", "2", "2"],
            "geometry": [
                Polygon([(0, 0), (1, 0), (1, 1), (0, 1)]),   # centroid ~(0.5, 0.5)
                Polygon([(2, 2), (3, 2), (3, 3), (2, 3)]),   # centroid ~(2.5, 2.5)
                Polygon([(10, 10), (11, 10), (11, 11), (10, 11)]),  # far away
            ],
        },
        crs="EPSG:4326",
    )


def _make_grid_gdf() -> gpd.GeoDataFrame:
    """A single grid line near the first two polygons."""
    return gpd.GeoDataFrame(
        {"geometry": [LineString([(0, 0), (3, 0)])]},
        crs="EPSG:4326",
    )


def test_proximity_category_tiers():
    assert _proximity_category(5.0) == "on_grid"
    assert _proximity_category(9.9) == "on_grid"
    assert _proximity_category(10.0) == "near_grid"
    assert _proximity_category(49.9) == "near_grid"
    assert _proximity_category(50.0) == "off_grid"
    assert _proximity_category(200.0) == "off_grid"


def test_compute_proximity_returns_expected_columns():
    result = compute_proximity(_make_admin_gdf(), _make_grid_gdf())
    assert set(result.columns) == {
        "admin_gid", "country_code", "admin_name", "admin_level",
        "dist_to_grid_km", "grid_proximity_category",
    }


def test_compute_proximity_row_count():
    result = compute_proximity(_make_admin_gdf(), _make_grid_gdf())
    assert len(result) == 3


def test_compute_proximity_near_line_is_closer():
    result = compute_proximity(_make_admin_gdf(), _make_grid_gdf())
    dist_a1 = result.loc[result["admin_gid"] == "A1", "dist_to_grid_km"].iloc[0]
    dist_a3 = result.loc[result["admin_gid"] == "A3", "dist_to_grid_km"].iloc[0]
    assert dist_a1 < dist_a3


def test_compute_proximity_distances_non_negative():
    result = compute_proximity(_make_admin_gdf(), _make_grid_gdf())
    assert (result["dist_to_grid_km"] >= 0).all()


def test_compute_proximity_categories_valid():
    result = compute_proximity(_make_admin_gdf(), _make_grid_gdf())
    valid = {"on_grid", "near_grid", "off_grid", "unknown"}
    assert set(result["grid_proximity_category"].unique()).issubset(valid)
