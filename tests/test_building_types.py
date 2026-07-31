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
import json
import os
from pathlib import Path

import pytest

project_root = Path(__file__).resolve().parent.parent
os.environ.setdefault("BUEM_WEATHER_DIR", str(project_root / "src" / "buem" / "data"))

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
