"""Tests for ``buem.thermal.dhw_cooking`` -- pure math, no I/O, no
5R1C/LP solve involved."""
from __future__ import annotations

import pandas as pd
import pytest

from buem.analysis.netherlands.gas_conversion import (
    COOKING_SHARE_OF_GAS,
    DHW_SHARE_OF_GAS,
    SPACE_HEATING_SHARE_OF_GAS,
)
from buem.thermal.dhw_cooking import (
    DHW_ANNUAL_KWH_PER_PERSON_EN12831_3,
    DHW_ANNUAL_KWH_PER_PERSON_NTA8800,
    DHW_DELTA_T_K,
    cooking_gas_energy_kwh,
    dhw_energy_kwh,
    dhw_energy_kwh_annual_fallback,
)


def _hourly_index(n=24):
    return pd.date_range("2018-01-01", periods=n, freq="h")


def test_dhw_energy_kwh_known_value():
    """100 L at the default (EN 12831-3 operating-conditions) ΔT should be
    ~3.58 kWh -- E = V*rho*c*ΔT = 100 * 1 * 4.186 * 30.8 kJ = 12892.9 kJ =
    3.5814 kWh."""
    liters = pd.Series([100.0], index=_hourly_index(1))
    result = dhw_energy_kwh(liters)
    assert result.iloc[0] == pytest.approx(3.5814, abs=0.001)
    assert result.name == "dhw_kWh"


def test_dhw_energy_kwh_known_value_at_explicit_delta_t():
    """Decoupled from whatever DHW_DELTA_T_K's default currently is --
    100 L at ΔT 50 K should be ~5.81 kWh regardless."""
    liters = pd.Series([100.0], index=_hourly_index(1))
    result = dhw_energy_kwh(liters, delta_t_k=50.0)
    assert result.iloc[0] == pytest.approx(5.8139, abs=0.001)


def test_dhw_energy_kwh_zero_liters_is_zero_energy():
    liters = pd.Series([0.0, 0.0], index=_hourly_index(2))
    result = dhw_energy_kwh(liters)
    assert (result == 0.0).all()


def test_dhw_energy_kwh_scales_linearly_with_delta_t():
    liters = pd.Series([50.0], index=_hourly_index(1))
    at_default = dhw_energy_kwh(liters, delta_t_k=DHW_DELTA_T_K)
    at_double = dhw_energy_kwh(liters, delta_t_k=DHW_DELTA_T_K * 2)
    assert at_double.iloc[0] == pytest.approx(at_default.iloc[0] * 2)


def test_dhw_energy_kwh_preserves_index():
    idx = _hourly_index(5)
    liters = pd.Series([10.0, 20.0, 0.0, 5.0, 15.0], index=idx)
    result = dhw_energy_kwh(liters)
    assert list(result.index) == list(idx)


def test_dhw_energy_kwh_annual_fallback_scales_with_persons():
    one_person = dhw_energy_kwh_annual_fallback(1)
    four_persons = dhw_energy_kwh_annual_fallback(4)
    assert one_person == pytest.approx(DHW_ANNUAL_KWH_PER_PERSON_EN12831_3)
    assert four_persons == pytest.approx(one_person * 4)


def test_dhw_energy_kwh_annual_fallback_accepts_nta8800_override():
    """The old NTA 8800 default is still available, explicitly, for
    backward compatibility/comparison -- just not the implicit default
    anymore (see the 2026-08-18 EN 12831-3 internal-consistency finding)."""
    result = dhw_energy_kwh_annual_fallback(
        1, annual_kwh_per_person=DHW_ANNUAL_KWH_PER_PERSON_NTA8800
    )
    assert result == pytest.approx(DHW_ANNUAL_KWH_PER_PERSON_NTA8800)


def test_dhw_energy_kwh_annual_fallback_rejects_nonpositive_persons():
    with pytest.raises(ValueError):
        dhw_energy_kwh_annual_fallback(0)
    with pytest.raises(ValueError):
        dhw_energy_kwh_annual_fallback(-1)


def test_cooking_gas_energy_kwh_distributes_only_to_active_hours():
    idx = _hourly_index(4)
    cooking_active = pd.Series([1, 0, 1, 0], index=idx)
    result = cooking_gas_energy_kwh(cooking_active, annual_total_kwh=100.0)
    assert result.iloc[0] == pytest.approx(50.0)
    assert result.iloc[1] == 0.0
    assert result.iloc[2] == pytest.approx(50.0)
    assert result.iloc[3] == 0.0
    assert result.sum() == pytest.approx(100.0)
    assert result.name == "cooking_gas_kWh"


def test_cooking_gas_energy_kwh_falls_back_to_flat_when_never_active():
    idx = _hourly_index(4)
    cooking_active = pd.Series([0, 0, 0, 0], index=idx)
    result = cooking_gas_energy_kwh(cooking_active, annual_total_kwh=40.0)
    assert (result == 10.0).all()
    assert result.sum() == pytest.approx(40.0)


def test_cooking_gas_energy_kwh_rejects_negative_total():
    idx = _hourly_index(2)
    cooking_active = pd.Series([1, 0], index=idx)
    with pytest.raises(ValueError):
        cooking_gas_energy_kwh(cooking_active, annual_total_kwh=-1.0)


def test_cbs_shares_sum_to_one():
    """Regression guard: the three CBS 2016 shares
    (`gas_conversion.py`) this module's cooking-total calibration is meant
    to be anchored against should still sum to ~1.0 -- if they ever drift
    apart, `dhw_cooking`'s docstring guidance (derive a cooking total from
    a building's own heating_kWh via the CBS ratio) silently stops making
    sense."""
    assert (
        SPACE_HEATING_SHARE_OF_GAS + DHW_SHARE_OF_GAS + COOKING_SHARE_OF_GAS
        == pytest.approx(1.0)
    )
