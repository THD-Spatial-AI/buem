"""
Tests for the new optional "equipment" (household inclusion/exclusion) and
the fixed "use_provided_elecLoad" (elecLoad override that still preserves
occupancy-generated Q_ig/occ_nothome/occ_sleeping) attributes -- see
CHANGELOG.md [Unreleased] and .claude/occupancy_module_activities.md.
"""
import json
import logging
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from occupancy import ElectricityConsumptionProfile, HouseholdProfile  # type: ignore[import]

from buem.config.cfg_attribute import HOUSEHOLD_EQUIPMENT_TYPES
from buem.integration.scripts.attribute_builder import AttributeBuilder, _resolve_equipment_table
from buem.integration.scripts.geojson_validator import validate_geojson_request

project_root = Path(__file__).resolve().parent.parent
DUMMY_DIR = project_root / "src" / "buem" / "data" / "buildings" / "dummy"


def _load_building_attributes(fixture_name: str) -> dict:
    payload = json.loads((DUMMY_DIR / fixture_name).read_text(encoding="utf-8"))
    result = validate_geojson_request(payload)
    assert result.is_valid, [str(e) for e in result.get_errors()]
    feature = result.validated_data["features"][0]
    return feature["properties"]["buem"]["building_attributes"]


# ── _resolve_equipment_table: unit-level, deterministic (no RNG dependence) ──


def _household(archetype="generic", seed=42):
    return HouseholdProfile(num_persons=4, year=2018, seed=seed, archetype=archetype)


def _specs_equal(a, b) -> bool:
    """Value equality for EquipmentSpec, sidestepping two pitfalls: its
    numpy-array fields (weekday/weekend) break plain dataclass `==`
    ("truth value of an array is ambiguous"), and archetypes with real
    equipment_overrides make _apply_overrides() rebuild a fresh object via
    dataclasses.replace() on every ElectricityConsumptionProfile
    construction, so `is` identity doesn't hold even when the values do."""
    if a is b:
        return True
    return (
        a.name == b.name and a.category == b.category
        and a.rated_power_kw == b.rated_power_kw and a.standby_power_kw == b.standby_power_kw
        and a.ownership_probability == b.ownership_probability
        and a.strategy == b.strategy and a.strategy_params == b.strategy_params
        and a.enabled == b.enabled
        and np.array_equal(a.weekday, b.weekday) and np.array_equal(a.weekend, b.weekend)
    )


def test_resolve_equipment_table_none_when_no_selector():
    household = _household()
    assert _resolve_equipment_table(household, 42, None) is None
    assert _resolve_equipment_table(household, 42, {}) is None


def test_resolve_equipment_table_true_forces_full_ownership_probability():
    household = _household()
    table = _resolve_equipment_table(household, 42, {"oven": True})
    assert table["oven"].ownership_probability == 1.0
    # Untouched items are the household's own archetype-adjusted defaults,
    # unmodified -- same key set, same specs.
    base_table = ElectricityConsumptionProfile(household, seed=42).get_equipment_table()
    for key in HOUSEHOLD_EQUIPMENT_TYPES - {"oven"}:
        assert _specs_equal(table[key], base_table[key])


def test_resolve_equipment_table_false_omits_item_entirely():
    household = _household()
    table = _resolve_equipment_table(household, 42, {"oven": False})
    assert "oven" not in table
    # Every other item is still present, untouched.
    base_table = ElectricityConsumptionProfile(household, seed=42).get_equipment_table()
    for key in HOUSEHOLD_EQUIPMENT_TYPES - {"oven"}:
        assert _specs_equal(table[key], base_table[key])


def test_resolve_equipment_table_preserves_archetype_overrides():
    """Reads the archetype-adjusted base table (get_equipment_table()), not
    the raw default_equipment_table() -- unmentioned items must match
    exactly what a plain ElectricityConsumptionProfile(household) would
    have used for this household's archetype."""
    household = _household(archetype="student_shared")
    table = _resolve_equipment_table(household, 42, {"oven": True})
    base_table = ElectricityConsumptionProfile(household, seed=42).get_equipment_table()
    for key in HOUSEHOLD_EQUIPMENT_TYPES - {"oven"}:
        assert _specs_equal(table[key], base_table[key])


def test_resolve_equipment_table_unknown_id_raises():
    household = _household()
    with pytest.raises(ValueError, match="unrecognized id"):
        _resolve_equipment_table(household, 42, {"not_a_real_appliance": True})


def test_resolve_equipment_table_non_bool_value_raises():
    household = _household()
    with pytest.raises(ValueError, match="must be true/false"):
        _resolve_equipment_table(household, 42, {"oven": "yes"})


def test_resolve_equipment_table_non_dict_raises():
    household = _household()
    with pytest.raises(ValueError, match="must be a dict"):
        _resolve_equipment_table(household, 42, ["oven"])


# ── full AttributeBuilder pipeline: wiring + error surfacing ─────────────


def test_equipment_wired_through_attribute_builder():
    building_attrs = _load_building_attributes("building_01_small_residential.json")
    attrs = dict(building_attrs)
    attrs["equipment"] = {"oven": True, "dish_washer": False}
    merged = AttributeBuilder(payload_attrs=attrs).build()
    assert "elecLoad" in merged
    assert not merged["elecLoad"].isna().any()


def test_equipment_unknown_id_raises_clear_error_through_builder():
    building_attrs = _load_building_attributes("building_01_small_residential.json")
    bad_attrs = dict(building_attrs)
    bad_attrs["equipment"] = {"not_a_real_appliance": True}
    with pytest.raises(RuntimeError, match="unrecognized id"):
        AttributeBuilder(payload_attrs=bad_attrs).build()


def test_equipment_selection_ignored_for_service_building(caplog):
    """occupancy.ServiceBuildingProfile has no per-item equipment selection
    yet -- a supplied equipment selector must be ignored with a warning, not
    raise, for a service building_type."""
    building_attrs = _load_building_attributes("building_02_medium_office.json")
    assert building_attrs["building_type"] == "office"
    attrs = dict(building_attrs)
    attrs["equipment"] = {"lighting": False}

    with caplog.at_level(logging.WARNING):
        merged = AttributeBuilder(payload_attrs=attrs).build()

    assert "elecLoad" in merged
    assert any(
        "no per-item equipment selection" in record.getMessage() for record in caplog.records
    )


def test_equipment_registry_matches_occupancy():
    """Drift guard: HOUSEHOLD_EQUIPMENT_TYPES and the v4 schema's
    building.equipment property list are both hand-copied from occupancy's
    households/data/equipment.json -- occupancy has no top-level export for
    this registry yet (see .claude/occupancy_module_activities.md item 1).
    Fails loudly the moment any of the three fall out of sync, mirroring
    test_building_types.py::test_v4_building_type_enum_matches_occupancy."""
    from occupancy.households.electricity import default_equipment_table

    real_ids = set(default_equipment_table().keys())
    assert HOUSEHOLD_EQUIPMENT_TYPES == real_ids, (
        "buem.config.cfg_attribute.HOUSEHOLD_EQUIPMENT_TYPES has drifted "
        "from occupancy's real equipment registry -- update it to match."
    )

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
    schema_ids = set(schema["$defs"]["building"]["properties"]["equipment"]["properties"])
    assert schema_ids == real_ids, (
        "versions/v4/request_schema.json's building.equipment property list "
        "has drifted from occupancy's real equipment registry -- update it "
        "(and note the change in DRAFT.md)."
    )


# ── use_provided_elecLoad (elecLoad override, occupancy patterns preserved) ──


def test_use_provided_elec_load_requires_series():
    building_attrs = _load_building_attributes("building_01_small_residential.json")
    bad_attrs = dict(building_attrs)
    bad_attrs["use_provided_elecLoad"] = True
    bad_attrs["elecLoad"] = [1.0, 2.0, 3.0]  # not a pandas Series
    with pytest.raises(ValueError, match="requires elecLoad to be a"):
        AttributeBuilder(payload_attrs=bad_attrs).build()


def test_use_provided_elec_load_preserves_occupancy_patterns():
    """Overriding elecLoad must still run a real occupancy generation for
    Q_ig/occ_nothome/occ_sleeping (via occupancy.to_buem_profiles(elec_load=
    ...)) instead of the old behavior of skipping occupancy entirely."""
    building_attrs = _load_building_attributes("building_01_small_residential.json")

    baseline = AttributeBuilder(payload_attrs=dict(building_attrs)).build()
    weather_index = baseline["weather"].index

    flat_supplied_load = pd.Series(5.0, index=weather_index, name="elecLoad")
    override_attrs = dict(building_attrs)
    override_attrs["use_provided_elecLoad"] = True
    override_attrs["elecLoad"] = flat_supplied_load

    overridden = AttributeBuilder(payload_attrs=override_attrs).build()

    # elecLoad matches the caller-supplied series...
    assert np.allclose(overridden["elecLoad"].to_numpy(), 5.0)
    # ...but Q_ig/occ_nothome/occ_sleeping are still real, occupancy-shaped
    # output (varying over the day), not flat/absent -- i.e. occupancy was
    # actually called, unlike the pre-fix total-bypass behavior.
    assert overridden["Q_ig"].nunique() > 1
    assert overridden["occ_nothome"].nunique() > 1
    assert not overridden["Q_ig"].isna().any()
