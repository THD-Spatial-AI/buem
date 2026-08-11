"""
Integration smoke-test: run a residential and a service-building dummy
fixture end-to-end (GeoJSON -> AttributeBuilder -> ModelBUEM).

Deliberately calls ModelBUEM.sim_model() directly instead of
buem.main.run_model() -- the latter (and anything importing
buem.integration.scripts.geojson_processor) currently fails to import due
to a pre-existing, unrelated gap (buem.main imports the non-existent
buem.results.standard_plots, see CLAUDE.md "Open follow-ups"). Avoiding
that chain keeps this test collectible under pytest, unlike
test_energy.py/test_geojson_integration.py/test_scaling.py/
test_worker_debug.py.
"""
import copy
import json
import os
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

project_root = Path(__file__).resolve().parent.parent
os.environ.setdefault("BUEM_WEATHER_DIR", str(project_root / "src" / "buem" / "data" / "weather"))

from buem.config.cfg_attribute import RESIDENTIAL_BUILDING_TYPES
from buem.config.cfg_attribute import cfg as DEFAULT_CFG
from buem.config.cfg_building import CfgBuilding
from buem.integration.scripts.attribute_builder import AttributeBuilder
from buem.integration.scripts.geojson_validator import validate_geojson_request
from buem.thermal.model_buem import ModelBUEM

DUMMY_DIR = project_root / "src" / "buem" / "data" / "buildings" / "dummy"


def _load_building_attributes(fixture_name: str) -> dict:
    """Validate+convert a dummy v3 GeoJSON fixture to a flat v2 building_attributes dict."""
    payload = json.loads((DUMMY_DIR / fixture_name).read_text(encoding="utf-8"))
    result = validate_geojson_request(payload)
    assert result.is_valid, [str(e) for e in result.get_errors()]
    feature = result.validated_data["features"][0]
    return feature["properties"]["buem"]["building_attributes"]


@pytest.mark.parametrize(
    "fixture_name,expected_building_type",
    [
        ("building_01_small_residential.json", "SFH"),
        ("building_02_medium_office.json", "office"),
    ],
)
def test_dummy_fixture_runs_end_to_end(fixture_name, expected_building_type):
    """A residential (household) and a services (ServiceBuildingProfile) fixture
    both run through the full AttributeBuilder -> ModelBUEM pipeline without error."""
    building_attrs = _load_building_attributes(fixture_name)
    assert building_attrs["building_type"] == expected_building_type

    # Real per-location weather fetch (weather is a compulsory dependency;
    # requires BUEM_WEATHER_DATA_DIR / WEATHER_DATA_DIR to point at
    # processed provider archives -- see .env.example).
    merged = AttributeBuilder(payload_attrs=building_attrs).build()
    cfg = CfgBuilding(merged).to_cfg_dict()

    model = ModelBUEM(cfg)
    model.sim_model(use_milp=False)

    assert model.heating_load is not None
    assert model.cooling_load is not None
    assert len(model.heating_load) == len(cfg["weather"])
    # Sanity: no runaway negative "heating" or positive "cooling" (sign convention).
    assert (model.heating_load >= 0).all()
    assert (model.cooling_load <= 0).all()


def test_time_varying_comfort_bounds_change_heating_shape():
    """A comfortT_lb schedule with a deep night setback should shift heating
    demand away from those hours, unlike a flat scalar bound -- exercising the
    Tier-3 scalar-or-pd.Series support in ModelBUEM._init5R1C."""
    weather_index = DEFAULT_CFG["weather"].index
    hours = weather_index.hour.to_numpy()
    night_mask = (hours >= 0) & (hours < 6)

    scalar_cfg = copy.deepcopy(DEFAULT_CFG)
    model_scalar = ModelBUEM(scalar_cfg)
    model_scalar.sim_model(use_milp=False)

    # Night setback (0-6h): lower bound relaxed to 15 degC vs. the default 21 degC.
    lb_series = pd.Series(np.where(night_mask, 15.0, 21.0), index=weather_index)
    series_cfg = copy.deepcopy(DEFAULT_CFG)
    series_cfg["comfortT_lb"] = lb_series
    model_series = ModelBUEM(series_cfg)
    model_series.sim_model(use_milp=False)

    assert not np.allclose(model_series.heating_load, model_scalar.heating_load)
    assert model_series.heating_load[night_mask].sum() <= model_scalar.heating_load[night_mask].sum()


def test_v4_building_type_enum_matches_occupancy():
    """Drift guard for occupancy_gains_handoff.md's Gap 3 (registry
    duplication risk): versions/v4/request_schema.json's building_type
    enum hand-copies occupancy's service-building type ids (JSON Schema is
    static, so it can't import them at load time). occupancy.
    SERVICE_BUILDING_TYPES is the real, top-level, live source of truth
    (promoted there 2026-08-07 specifically for this); this test fails
    loudly the moment the two fall out of sync, instead of the enum
    silently going stale."""
    import occupancy

    schema_path = (
        project_root
        / "src"
        / "buem"
        / "integration"
        / "json_schema"
        / "versions"
        / "v4"
        / "request_schema.json"
    )
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    enum_values = set(
        schema["$defs"]["building"]["properties"]["building_type"]["enum"]
    )
    service_type_values = enum_values - RESIDENTIAL_BUILDING_TYPES
    assert service_type_values == set(occupancy.SERVICE_BUILDING_TYPES), (
        "versions/v4/request_schema.json's building_type enum has drifted "
        "from occupancy.SERVICE_BUILDING_TYPES -- update the enum (and its "
        "description) in request_schema.json to match, and note the change "
        "in DRAFT.md."
    )
