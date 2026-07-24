"""Tests for AttributeBuilder's caller-supplied elecLoad handling and the
shared weather-reindex helper (attribute_builder.py).
"""
import pandas as pd
import pytest

from buem.integration.scripts.attribute_builder import AttributeBuilder, _reindex_to_weather


def _weather_df(n_hours: int = 8760) -> pd.DataFrame:
    index = pd.date_range("2018-01-01", periods=n_hours, freq="h")
    return pd.DataFrame({"temp_air": [10.0] * n_hours}, index=index)


def _builder_with_elecload(values, weather_df) -> AttributeBuilder:
    builder = AttributeBuilder(payload_attrs={})
    builder.merged_attrs = {"elecLoad": values, "weather": weather_df}
    return builder


def test_normalize_provided_elec_load_rejects_too_short_list():
    weather_df = _weather_df(8760)
    builder = _builder_with_elecload([1.0] * 24, weather_df)
    with pytest.raises(ValueError, match="elecLoad has 24 values but weather data has 8760 hours"):
        builder._normalize_provided_elec_load(weather_df)


def test_normalize_provided_elec_load_rejects_too_long_list():
    weather_df = _weather_df(24)
    builder = _builder_with_elecload([1.0] * 96, weather_df)
    with pytest.raises(ValueError, match="elecLoad has 96 values but weather data has 24 hours"):
        builder._normalize_provided_elec_load(weather_df)


def test_normalize_provided_elec_load_accepts_matching_length():
    weather_df = _weather_df(24)
    values = [float(i) for i in range(24)]
    builder = _builder_with_elecload(values, weather_df)

    builder._normalize_provided_elec_load(weather_df)

    result = builder.merged_attrs["elecLoad"]
    assert isinstance(result, pd.Series)
    assert result.index.equals(weather_df.index)
    assert list(result.values) == values


def test_normalize_provided_elec_load_no_weather_index():
    values = [1.0, 2.0, 3.0]
    builder = _builder_with_elecload(values, weather_df=None)

    builder._normalize_provided_elec_load(weather_df=None)

    result = builder.merged_attrs["elecLoad"]
    assert isinstance(result, pd.Series)
    assert isinstance(result.index, pd.RangeIndex)
    assert list(result.values) == values


def test_reindex_to_weather_is_noop_when_index_matches():
    weather_df = _weather_df(24)
    series = pd.Series(range(24), index=weather_df.index)

    result = _reindex_to_weather(series, weather_df)

    assert result is series


def test_reindex_to_weather_reindexes_mismatched_index():
    weather_df = _weather_df(24)
    other_index = pd.date_range("2019-01-01", periods=24, freq="h")
    series = pd.Series(range(24), index=other_index)

    result = _reindex_to_weather(series, weather_df)

    assert result.index.equals(weather_df.index)
    assert len(result) == 24
