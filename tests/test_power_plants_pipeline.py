"""Unit tests for the WRI Power Plants ingestion pipeline (no network calls)."""

import pandas as pd
import pytest

from ingestion.power_plants.pipeline import OUTPUT_COLS, TARGET_COUNTRIES, transform


def _mock_raw() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "gppd_idnr": ["KEN001", "NGA001", "USA001", "IND001"],
            "country": ["KEN", "NGA", "USA", "IND"],
            "country_long": ["Kenya", "Nigeria", "United States", "India"],
            "name": ["Plant A", "Plant B", "Plant C", "Plant D"],
            "capacity_mw": [100.0, 250.0, 1000.0, 500.0],
            "latitude": [-1.0, 6.5, 40.0, 28.6],
            "longitude": [36.8, 3.4, -74.0, 77.2],
            "primary_fuel": ["Solar", "Gas", "Coal", "Wind"],
        }
    )


def test_transform_filters_target_countries_only():
    result = transform(_mock_raw())
    assert set(result["country"].unique()).issubset(TARGET_COUNTRIES)
    assert "USA" not in result["country"].values


def test_transform_renames_gppd_idnr_to_plant_id():
    result = transform(_mock_raw())
    assert "plant_id" in result.columns
    assert "gppd_idnr" not in result.columns


def test_transform_returns_expected_columns():
    result = transform(_mock_raw())
    assert set(result.columns) == set(OUTPUT_COLS)


def test_transform_fills_missing_cols_with_empty_string():
    result = transform(_mock_raw())
    # commissioning_year was not in mock — should be empty string
    assert (result["commissioning_year"] == "").all()


def test_transform_no_nan_values():
    result = transform(_mock_raw())
    assert not result.isna().any().any()
