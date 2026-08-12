"""Tests for GeoJsonProcessor's caller-supplied weather handling
(geojson_processor.py::_weather_from_payload and the missing-weather
error path in _process_single_feature).
"""
import pandas as pd

from buem.integration.scripts.geojson_processor import GeoJsonProcessor

_ENVELOPE_ELEMENTS = [
    {"id": "Wall_1", "type": "wall", "area": 80.0, "azimuth": 0.0, "tilt": 90.0, "U": 0.35},
    {"id": "Roof_1", "type": "roof", "area": 100.0, "azimuth": 0.0, "tilt": 0.0, "U": 0.20},
    {"id": "Floor_1", "type": "floor", "area": 100.0, "azimuth": 0.0, "tilt": 180.0, "U": 0.25},
    {"id": "Window_1", "type": "window", "area": 15.0, "azimuth": 180.0, "tilt": 90.0, "U": 1.3},
    {"id": "Door_1", "type": "door", "area": 2.0, "azimuth": 180.0, "tilt": 90.0, "U": 1.8},
]


def _feature_collection(buem_extra: dict) -> dict:
    buem = {
        "building": {
            "building_type": "SFH",
            "country": "AT",
            "envelope": {"elements": _ENVELOPE_ELEMENTS},
        },
        **buem_extra,
    }
    return {
        "type": "FeatureCollection",
        "features": [{
            "type": "Feature",
            "id": "test-building",
            "geometry": {"type": "Point", "coordinates": [16.3738, 48.2082]},
            "properties": {
                "start_time": "2018-01-01T00:00:00Z",
                "end_time": "2018-01-01T01:00:00Z",
                "resolution": "60",
                "resolution_unit": "minutes",
                "buem": buem,
            },
        }],
    }


def test_process_fails_loudly_when_weather_is_missing():
    """A payload with no buem.weather must be reported as a per-feature
    processing error naming weather, never silently substituted with
    AttributeBuilder's generic default -- see geojson_processor.py's
    _process_single_feature for the reasoning.
    """
    payload = _feature_collection(buem_extra={})

    response = GeoJsonProcessor(payload=payload).process()

    assert response["metadata"]["successful_features"] == 0
    error = response["features"][0]["properties"]["buem"]["error"]
    assert "weather" in error["message"].lower()


def test_weather_from_payload_none_returns_none():
    assert GeoJsonProcessor._weather_from_payload(None) is None


def test_weather_from_payload_missing_index_returns_none():
    assert GeoJsonProcessor._weather_from_payload({"T": [1.0, 2.0]}) is None


def test_weather_from_payload_no_known_columns_returns_none():
    assert GeoJsonProcessor._weather_from_payload({"index": ["2018-01-01T00:00:00"]}) is None


def test_weather_from_payload_builds_dataframe_matching_load_feature_weather_shape():
    """Matches weather serve's actual GET .../point?format=json shape --
    variables nested under "variables", not top-level keys alongside
    "index" (weather enerplanet/weather#13)."""
    weather_json = {
        "index": ["2018-01-01T00:00:00", "2018-01-01T01:00:00"],
        "variables": {
            "T": [1.0, 2.0],
            "GHI": [0.0, 10.0],
            "DNI": [0.0, 5.0],
            "DHI": [0.0, 5.0],
        },
    }

    df = GeoJsonProcessor._weather_from_payload(weather_json)

    assert isinstance(df, pd.DataFrame)
    assert isinstance(df.index, pd.DatetimeIndex)
    assert list(df.columns) == ["T", "GHI", "DNI", "DHI"]
    assert list(df["T"]) == [1.0, 2.0]
    assert list(df["GHI"]) == [0.0, 10.0]


def test_weather_from_payload_handles_partial_columns():
    weather_json = {"index": ["2018-01-01T00:00:00"], "variables": {"T": [1.0]}}

    df = GeoJsonProcessor._weather_from_payload(weather_json)

    assert list(df.columns) == ["T"]


def test_weather_from_payload_rejects_stale_flat_shape():
    """weather_json's old flat shape (variables as top-level keys, not
    nested under "variables") must not be silently accepted as if it had
    no usable columns -- it should behave exactly like "no columns given",
    i.e. return None, not partially/incorrectly parse."""
    weather_json = {
        "index": ["2018-01-01T00:00:00"],
        "T": [1.0],  # old flat shape -- no longer recognized
    }

    assert GeoJsonProcessor._weather_from_payload(weather_json) is None
