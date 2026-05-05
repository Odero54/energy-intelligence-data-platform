"""Unit tests for the World Bank ingestion pipeline (no network calls)."""

import pandas as pd
import pytest

from ingestion.world_bank.pipeline import (
    INDICATOR,
    INDICATOR_NAME,
    OUTPUT_COLS,
    transform,
)


def _mock_raw() -> pd.DataFrame:
    return pd.DataFrame(
        {2020: [75.0, 55.0, None], 2021: [76.0, 56.0, 85.0]},
        index=pd.Index(["KEN", "NGA", "RWA"], name="economy"),
    )


def test_transform_returns_expected_columns():
    result = transform(_mock_raw())
    assert set(result.columns) == set(OUTPUT_COLS)


def test_transform_drops_nulls():
    result = transform(_mock_raw())
    assert not result["value"].isna().any()
    # RWA 2020 was None — only RWA 2021 should survive
    rwa = result[result["country_code"] == "RWA"]
    assert len(rwa) == 1
    assert rwa["year"].iloc[0] == "2021"


def test_transform_adds_indicator_metadata():
    result = transform(_mock_raw())
    assert (result["indicator_code"] == INDICATOR).all()
    assert (result["indicator_name"] == INDICATOR_NAME).all()


def test_transform_maps_country_names():
    result = transform(_mock_raw())
    assert result.loc[result["country_code"] == "KEN", "country_name"].iloc[0] == "Kenya"
    assert result.loc[result["country_code"] == "NGA", "country_name"].iloc[0] == "Nigeria"


def test_transform_types_are_strings():
    result = transform(_mock_raw())
    assert result["year"].dtype == object
    assert result["value"].dtype == object
