"""Tests for GeoJsonProcessor's caller-supplied weather handling
(geojson_processor.py::_weather_from_payload).
"""
import pandas as pd
import pytest

from buem.integration.scripts.geojson_processor import GeoJsonProcessor


def test_weather_from_payload_none_returns_none():
    assert GeoJsonProcessor._weather_from_payload(None) is None


def test_weather_from_payload_missing_index_returns_none():
    assert GeoJsonProcessor._weather_from_payload({"T": [1.0, 2.0]}) is None


def test_weather_from_payload_no_known_columns_returns_none():
    assert GeoJsonProcessor._weather_from_payload({"index": ["2018-01-01T00:00:00"]}) is None


def test_weather_from_payload_builds_dataframe_matching_load_feature_weather_shape():
    weather_json = {
        "index": ["2018-01-01T00:00:00", "2018-01-01T01:00:00"],
        "T": [1.0, 2.0],
        "GHI": [0.0, 10.0],
        "DNI": [0.0, 5.0],
        "DHI": [0.0, 5.0],
    }

    df = GeoJsonProcessor._weather_from_payload(weather_json)

    assert isinstance(df, pd.DataFrame)
    assert isinstance(df.index, pd.DatetimeIndex)
    assert list(df.columns) == ["T", "GHI", "DNI", "DHI"]
    assert list(df["T"]) == [1.0, 2.0]
    assert list(df["GHI"]) == [0.0, 10.0]


def test_weather_from_payload_handles_partial_columns():
    weather_json = {"index": ["2018-01-01T00:00:00"], "T": [1.0]}

    df = GeoJsonProcessor._weather_from_payload(weather_json)

    assert list(df.columns) == ["T"]
