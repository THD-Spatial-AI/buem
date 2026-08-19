"""Tests for ``buem.config.reference_values`` -- the CSV-backed loader
for `src/buem/data/reference/dhw_cooking_constants.csv`."""
from __future__ import annotations

import pytest

from buem.config.reference_values import load_dhw_cooking_constants

_EXPECTED_NAMES = {
    "WATER_DENSITY_KG_PER_L",
    "WATER_SPECIFIC_HEAT_KJ_PER_KGK",
    "DHW_DELTA_T_K",
    "DHW_DELTA_T_K_REFERENCE",
    "DHW_LITERS_PER_PERSON_DAY_EN12831_3",
    "DHW_ANNUAL_KWH_PER_PERSON_NTA8800",
    "SPACE_HEATING_SHARE_OF_GAS",
    "DHW_SHARE_OF_GAS",
    "COOKING_SHARE_OF_GAS",
    "GAS_CALORIFIC_VALUE_KWH_PER_M3",
    "BOILER_EFFICIENCY_UPPER_VALUE",
}


def test_load_dhw_cooking_constants_has_every_expected_name():
    values = load_dhw_cooking_constants()
    assert _EXPECTED_NAMES <= set(values)


def test_load_dhw_cooking_constants_values_are_floats():
    values = load_dhw_cooking_constants()
    for name, value in values.items():
        assert isinstance(value, float), f"{name} loaded as {type(value).__name__}, not float"


def test_load_dhw_cooking_constants_known_values():
    """Regression guard against a silent CSV edit drifting these away from
    the real, sourced EN 12831-3 / CBS values documented in
    `.claude/dhw_cooking_heat_handoff.md`."""
    values = load_dhw_cooking_constants()
    assert values["DHW_DELTA_T_K"] == pytest.approx(30.8)
    assert values["DHW_DELTA_T_K_REFERENCE"] == pytest.approx(46.5)
    assert values["DHW_LITERS_PER_PERSON_DAY_EN12831_3"] == pytest.approx(55.0)
    assert values["SPACE_HEATING_SHARE_OF_GAS"] == pytest.approx(0.78)
    assert values["DHW_SHARE_OF_GAS"] == pytest.approx(0.20)
    assert values["COOKING_SHARE_OF_GAS"] == pytest.approx(0.02)
    assert values["GAS_CALORIFIC_VALUE_KWH_PER_M3"] == pytest.approx(9.769)
    assert values["BOILER_EFFICIENCY_UPPER_VALUE"] == pytest.approx(0.90)


def test_load_dhw_cooking_constants_is_cached():
    """lru_cache-backed -- two calls return the same dict object, not two
    independent file reads."""
    assert load_dhw_cooking_constants() is load_dhw_cooking_constants()


def test_dhw_cooking_module_constants_match_the_csv():
    """`buem.thermal.dhw_cooking`'s module-level constants must actually
    come from the CSV, not silently reintroduce a hardcoded duplicate."""
    from buem.thermal import dhw_cooking

    values = load_dhw_cooking_constants()
    assert dhw_cooking.DHW_DELTA_T_K == values["DHW_DELTA_T_K"]
    assert dhw_cooking.DHW_DELTA_T_K_REFERENCE == values["DHW_DELTA_T_K_REFERENCE"]
    assert dhw_cooking.SPACE_HEATING_SHARE_OF_GAS == values["SPACE_HEATING_SHARE_OF_GAS"]


def test_gas_conversion_module_constants_match_the_csv():
    from buem.analysis.netherlands import gas_conversion

    values = load_dhw_cooking_constants()
    assert gas_conversion.GAS_CALORIFIC_VALUE_KWH_PER_M3 == values["GAS_CALORIFIC_VALUE_KWH_PER_M3"]
    assert gas_conversion.BOILER_EFFICIENCY_UPPER_VALUE == values["BOILER_EFFICIENCY_UPPER_VALUE"]
