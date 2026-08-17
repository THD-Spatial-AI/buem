"""Tests for ``buem.analysis.netherlands.gas_conversion`` -- pure math,
no I/O."""
from __future__ import annotations

import pytest

from buem.analysis.netherlands.gas_conversion import (
    BOILER_EFFICIENCY_UPPER_VALUE,
    GAS_CALORIFIC_VALUE_KWH_PER_M3,
    SPACE_HEATING_SHARE_OF_GAS,
    gas_m3_to_useful_heat_kwh,
)


def test_gas_m3_to_useful_heat_kwh_default_constants():
    result = gas_m3_to_useful_heat_kwh(860.0)  # real Apeldoorn "all dwellings" 2024 figure
    assert result.gas_m3_per_year == 860.0
    assert result.gross_gas_energy_kwh == pytest.approx(860.0 * GAS_CALORIFIC_VALUE_KWH_PER_M3)
    assert result.space_heating_gas_energy_kwh == pytest.approx(result.gross_gas_energy_kwh * SPACE_HEATING_SHARE_OF_GAS)
    assert result.useful_heat_kwh == pytest.approx(result.space_heating_gas_energy_kwh * BOILER_EFFICIENCY_UPPER_VALUE)


def test_gas_m3_to_useful_heat_kwh_stages_are_monotonically_decreasing():
    """Each stage should only ever reduce the energy figure (all three
    factors are <= 1 or a straightforward multiplier >= 1 for the first
    stage) -- gross >= space-heating share >= useful heat delivered."""
    result = gas_m3_to_useful_heat_kwh(1000.0)
    assert result.gross_gas_energy_kwh > result.space_heating_gas_energy_kwh > result.useful_heat_kwh > 0


def test_gas_m3_to_useful_heat_kwh_zero_gas_is_zero_heat():
    result = gas_m3_to_useful_heat_kwh(0.0)
    assert result.useful_heat_kwh == 0.0


def test_gas_m3_to_useful_heat_kwh_accepts_overrides():
    default_result = gas_m3_to_useful_heat_kwh(500.0)
    overridden = gas_m3_to_useful_heat_kwh(500.0, boiler_efficiency=1.0)
    assert overridden.useful_heat_kwh > default_result.useful_heat_kwh
    assert overridden.useful_heat_kwh == pytest.approx(overridden.space_heating_gas_energy_kwh)


def test_calorific_value_matches_official_dutch_standard():
    """Regression guard against silently drifting off the real, sourced
    value (35.17 MJ/m3 = 9.769 kWh/m3, the Gasunie/CBS billing standard)
    -- not the loose "~10 kWh/m3" figure sometimes used casually."""
    assert GAS_CALORIFIC_VALUE_KWH_PER_M3 == pytest.approx(9.769, abs=0.001)
