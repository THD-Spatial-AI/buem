"""
Tests for the v3->v4 live-contract promotion (2026-08-14): building_type
enum validation, buem.weather.provider/year forwarding, building.equipment
forwarding, file-based buem.inputs.electricity_load_profile /
buem.weather.profile loading, and explicit rejection of the still-unwired
weather.use_percentile / solver.compute_cooling fields.

See CLAUDE.md's "v2 vs v3/v4 request formats" and
src/buem/integration/json_schema/versions/v4/DRAFT.md for the contract
this exercises.
"""
import json
from pathlib import Path

import pandas as pd
import pytest

from buem.config.cfg_building import CfgBuilding
from buem.integration.scripts.attribute_builder import AttributeBuilder
from buem.integration.scripts.geojson_validator import validate_geojson_request
from buem.thermal.model_buem import ModelBUEM

project_root = Path(__file__).resolve().parent.parent
DUMMY_DIR = project_root / "src" / "buem" / "data" / "buildings" / "dummy"


def _load_v3_payload(fixture_name: str = "building_01_small_residential.json") -> dict:
    return json.loads((DUMMY_DIR / fixture_name).read_text(encoding="utf-8"))


def _building_attrs(payload: dict) -> dict:
    result = validate_geojson_request(payload)
    assert result.is_valid, [str(e) for e in result.get_errors()]
    return result.validated_data["features"][0]["properties"]["buem"]["building_attributes"]


# ── building_type validation ─────────────────────────────────────────────


def test_valid_residential_building_type_passes():
    payload = _load_v3_payload()
    assert payload["features"][0]["properties"]["buem"]["building"]["building_type"] == "SFH"
    attrs = _building_attrs(payload)
    assert attrs["building_type"] == "SFH"


def test_valid_service_building_type_passes():
    payload = _load_v3_payload("building_02_medium_office.json")
    assert payload["features"][0]["properties"]["buem"]["building"]["building_type"] == "office"
    attrs = _building_attrs(payload)
    assert attrs["building_type"] == "office"


def test_unknown_building_type_rejected():
    payload = _load_v3_payload()
    payload["features"][0]["properties"]["buem"]["building"]["building_type"] = "not_a_real_type"
    result = validate_geojson_request(payload)
    assert not result.is_valid
    assert any("Unknown building_type" in str(e.message) for e in result.get_errors())


def test_missing_building_type_still_passes():
    """building_type stays optional -- absence is not an error, matching
    v2's existing optional behavior; AttributeBuilder's own default applies."""
    payload = _load_v3_payload()
    del payload["features"][0]["properties"]["buem"]["building"]["building_type"]
    attrs = _building_attrs(payload)
    assert "building_type" not in attrs


# ── buem.weather.provider/year forwarding ────────────────────────────────


def test_weather_provider_forwarded():
    payload = _load_v3_payload()
    payload["features"][0]["properties"]["buem"]["weather"] = {"provider": "cosmo-rea6"}
    attrs = _building_attrs(payload)
    assert attrs["weather_provider"] == "cosmo-rea6"
    assert "year" not in attrs  # not supplied -> not forwarded


def test_weather_year_forwarded_only_when_explicit():
    payload = _load_v3_payload()
    payload["features"][0]["properties"]["buem"]["weather"] = {"year": 2018}
    attrs = _building_attrs(payload)
    assert attrs["year"] == 2018


def test_weather_block_absent_forwards_nothing():
    payload = _load_v3_payload()
    attrs = _building_attrs(payload)
    assert "weather_provider" not in attrs
    assert "year" not in attrs


# ── building.equipment forwarding ────────────────────────────────────────


def test_equipment_forwarded():
    payload = _load_v3_payload()
    payload["features"][0]["properties"]["buem"]["building"]["equipment"] = {
        "oven": True, "dish_washer": False,
    }
    attrs = _building_attrs(payload)
    assert attrs["equipment"] == {"oven": True, "dish_washer": False}


# ── deliberately-unwired fields are rejected, not silently ignored ──────


def test_use_percentile_rejected():
    payload = _load_v3_payload()
    payload["features"][0]["properties"]["buem"]["weather"] = {"use_percentile": True}
    result = validate_geojson_request(payload)
    assert not result.is_valid
    assert any("use_percentile" in str(e.message) for e in result.get_errors())


def test_compute_cooling_rejected():
    payload = _load_v3_payload()
    payload["features"][0]["properties"]["buem"]["solver"] = {"compute_cooling": True}
    result = validate_geojson_request(payload)
    assert not result.is_valid
    assert any("compute_cooling" in str(e.message) for e in result.get_errors())


def test_compute_cooling_false_is_not_rejected():
    """Explicit false matches today's always-on behavior -- nothing to reject."""
    payload = _load_v3_payload()
    payload["features"][0]["properties"]["buem"]["solver"] = {"compute_cooling": False}
    attrs = _building_attrs(payload)
    assert attrs["building_type"] == "SFH"  # got through conversion fine


# ── file-based buem.inputs.electricity_load_profile ──────────────────────


def test_electricity_load_profile_json_file_loaded(tmp_path):
    values = [float(i % 5) for i in range(8760)]
    profile_path = tmp_path / "elec.json"
    profile_path.write_text(json.dumps(values), encoding="utf-8")

    payload = _load_v3_payload()
    payload["features"][0]["properties"]["buem"]["inputs"] = {
        "electricity_load_profile": {"path": str(profile_path), "unit": "kWh"}
    }
    attrs = _building_attrs(payload)
    assert attrs["use_provided_elecLoad"] is True
    assert isinstance(attrs["elecLoad"], pd.Series)
    assert len(attrs["elecLoad"]) == 8760
    assert attrs["elecLoad"].iloc[3] == 3.0


def test_electricity_load_profile_wh_unit_converted(tmp_path):
    profile_path = tmp_path / "elec.json"
    profile_path.write_text(json.dumps([1000.0] * 8760), encoding="utf-8")

    payload = _load_v3_payload()
    payload["features"][0]["properties"]["buem"]["inputs"] = {
        "electricity_load_profile": {"path": str(profile_path), "unit": "Wh"}
    }
    attrs = _building_attrs(payload)
    assert attrs["elecLoad"].iloc[0] == pytest.approx(1.0)  # 1000 Wh -> 1 kWh


def test_electricity_load_profile_missing_file_reported_as_error(tmp_path):
    payload = _load_v3_payload()
    payload["features"][0]["properties"]["buem"]["inputs"] = {
        "electricity_load_profile": {"path": str(tmp_path / "does_not_exist.json")}
    }
    result = validate_geojson_request(payload)
    assert not result.is_valid
    assert any("Could not read" in str(e.message) for e in result.get_errors())


# ── file-based buem.weather.profile ──────────────────────────────────────


def test_weather_profile_csv_file_loaded(tmp_path):
    idx = pd.date_range("2018-01-01", periods=24, freq="h")
    df = pd.DataFrame({"T": 5.0, "GHI": 100.0, "DHI": 50.0, "DNI": 200.0}, index=idx)
    profile_path = tmp_path / "weather.csv"
    df.to_csv(profile_path)

    payload = _load_v3_payload()
    payload["features"][0]["properties"]["buem"]["weather"] = {
        "profile": {"path": str(profile_path), "format": "csv"}
    }
    attrs = _building_attrs(payload)
    assert attrs["use_provided_weather"] is True
    assert isinstance(attrs["weather"], pd.DataFrame)
    assert list(attrs["weather"]["T"]) == [5.0] * 24
    assert {"T", "GHI", "DHI", "DNI"} <= set(attrs["weather"].columns)


def test_weather_profile_missing_column_reported_as_error(tmp_path):
    idx = pd.date_range("2018-01-01", periods=24, freq="h")
    df = pd.DataFrame({"T": 5.0, "GHI": 100.0}, index=idx)  # missing DHI/DNI
    profile_path = tmp_path / "weather_bad.csv"
    df.to_csv(profile_path)

    payload = _load_v3_payload()
    payload["features"][0]["properties"]["buem"]["weather"] = {
        "profile": {"path": str(profile_path), "format": "csv"}
    }
    result = validate_geojson_request(payload)
    assert not result.is_valid
    assert any("missing required column" in str(e.message) for e in result.get_errors())


def test_weather_profile_json_file_loaded_default_format(tmp_path):
    """json is the default format (EnerPlanET's actual format,
    confirmed 2026-08-14) -- omitting `format` entirely must still work."""
    records = [
        {"time": f"2018-01-01T{h:02d}:00:00", "T": 5.0, "GHI": 100.0, "DHI": 50.0, "DNI": 200.0}
        for h in range(24)
    ]
    profile_path = tmp_path / "weather.json"
    profile_path.write_text(json.dumps(records), encoding="utf-8")

    payload = _load_v3_payload()
    payload["features"][0]["properties"]["buem"]["weather"] = {
        "profile": {"path": str(profile_path)}  # format omitted -> json default
    }
    attrs = _building_attrs(payload)
    assert attrs["use_provided_weather"] is True
    assert isinstance(attrs["weather"], pd.DataFrame)
    assert len(attrs["weather"]) == 24
    assert list(attrs["weather"]["GHI"]) == [100.0] * 24


def test_weather_profile_json_missing_time_key_reported_as_error(tmp_path):
    records = [{"T": 5.0, "GHI": 100.0, "DHI": 50.0, "DNI": 200.0}]  # no "time"
    profile_path = tmp_path / "weather_bad.json"
    profile_path.write_text(json.dumps(records), encoding="utf-8")

    payload = _load_v3_payload()
    payload["features"][0]["properties"]["buem"]["weather"] = {
        "profile": {"path": str(profile_path), "format": "json"}
    }
    result = validate_geojson_request(payload)
    assert not result.is_valid
    assert any("'time' key" in str(e.message) for e in result.get_errors())


# ── per-provider weather year-range validation ───────────────────────────


def test_cosmo_rea6_year_within_range_passes():
    payload = _load_v3_payload()
    payload["features"][0]["properties"]["buem"]["weather"] = {
        "provider": "cosmo-rea6", "year": 2010,
    }
    attrs = _building_attrs(payload)
    assert attrs["weather_provider"] == "cosmo-rea6"
    assert attrs["year"] == 2010


def test_cosmo_rea6_year_out_of_range_rejected():
    payload = _load_v3_payload()
    payload["features"][0]["properties"]["buem"]["weather"] = {
        "provider": "cosmo-rea6", "year": 2020,  # cosmo-rea6 only covers 1995-2018
    }
    result = validate_geojson_request(payload)
    assert not result.is_valid
    assert any("outside cosmo-rea6's available range" in str(e.message) for e in result.get_errors())


def test_era5_land_year_out_of_range_rejected():
    payload = _load_v3_payload()
    payload["features"][0]["properties"]["buem"]["weather"] = {
        "provider": "era5-land", "year": 1975,  # era5-land only covers 1980-2025
    }
    result = validate_geojson_request(payload)
    assert not result.is_valid
    assert any("outside era5-land's available range" in str(e.message) for e in result.get_errors())


def test_default_provider_year_range_applies_when_provider_omitted():
    """year alone (no provider) is validated against the default provider
    (merra-2, 1950-2025)."""
    payload = _load_v3_payload()
    payload["features"][0]["properties"]["buem"]["weather"] = {"year": 1900}
    result = validate_geojson_request(payload)
    assert not result.is_valid
    assert any("outside merra-2's available range" in str(e.message) for e in result.get_errors())


def test_merra2_full_range_accepted():
    payload = _load_v3_payload()
    payload["features"][0]["properties"]["buem"]["weather"] = {
        "provider": "merra-2", "year": 1960,
    }
    attrs = _building_attrs(payload)
    assert attrs["year"] == 1960


# ── full end-to-end: real v3 request -> AttributeBuilder -> ModelBUEM ────


def test_electricity_load_profile_end_to_end(tmp_path):
    """A real v3-format request with a file-based electricity_load_profile
    must run all the way through the model, not just survive conversion --
    exercises the index-alignment path between the file's raw (unindexed)
    array and buem's actual (half-hour-offset) weather index."""
    values = [2.5] * 8760
    profile_path = tmp_path / "elec.json"
    profile_path.write_text(json.dumps(values), encoding="utf-8")

    payload = _load_v3_payload()
    payload["features"][0]["properties"]["buem"]["inputs"] = {
        "electricity_load_profile": {"path": str(profile_path), "unit": "kWh"}
    }
    building_attrs = _building_attrs(payload)

    merged = AttributeBuilder(payload_attrs=building_attrs).build()
    assert merged["elecLoad"].nunique() == 1  # flat 2.5 supplied profile, uniformly applied
    assert merged["Q_ig"].nunique() > 1  # occupancy still ran for real

    cfg = CfgBuilding(merged).to_cfg_dict()
    model = ModelBUEM(cfg)
    model.sim_model(use_milp=False)
    assert model.heating_load is not None
    assert len(model.heating_load) == len(cfg["weather"])
