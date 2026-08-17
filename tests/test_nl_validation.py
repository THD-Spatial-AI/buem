"""
Tests for ``buem.analysis.netherlands.validation``'s pure-logic pieces
(``TypeGroupResult``, ``format_report``) -- no real building data, no
simulation, no network. ``run_validation()`` itself needs a real
``CsvBuildingSource`` directory + real weather + a live CBS query, so
it's exercised manually (see ``docs/source/modules/netherlands.rst``'s
"Validation" section for real run results), not here.
"""
from __future__ import annotations

from buem.analysis.netherlands.gas_conversion import gas_m3_to_useful_heat_kwh
from buem.analysis.netherlands.validation import TypeGroupResult, format_report


def _result(**overrides) -> TypeGroupResult:
    defaults = {
        "building_type": "SFH",
        "neighbour_status": "B_Alone",
        "cbs_key": "detached",
        "n_simulated": 2,
        "mean_simulated_heating_kwh": 6780.0,
        "cbs_gas_m3_per_year": 1380.0,
        "cbs_conversion": gas_m3_to_useful_heat_kwh(1380.0),
    }
    defaults.update(overrides)
    return TypeGroupResult(**defaults)


def test_ratio_simulated_to_cbs_computes_expected_value():
    result = _result()
    expected = result.mean_simulated_heating_kwh / result.cbs_conversion.useful_heat_kwh
    assert result.ratio_simulated_to_cbs == expected


def test_ratio_simulated_to_cbs_none_when_no_simulated_value():
    result = _result(mean_simulated_heating_kwh=None)
    assert result.ratio_simulated_to_cbs is None


def test_ratio_simulated_to_cbs_none_when_no_cbs_data():
    result = _result(cbs_conversion=None, cbs_gas_m3_per_year=None)
    assert result.ratio_simulated_to_cbs is None


def test_ratio_simulated_to_cbs_none_when_cbs_useful_heat_is_zero():
    """Guards the division -- a real (if degenerate) CBS figure of 0 m3
    must not raise ZeroDivisionError."""
    result = _result(cbs_conversion=gas_m3_to_useful_heat_kwh(0.0), cbs_gas_m3_per_year=0.0)
    assert result.ratio_simulated_to_cbs is None


def test_format_report_renders_missing_data_as_em_dash_not_crash():
    """A group with no simulated buildings and no CBS match (both None)
    must still render, not raise."""
    result = _result(
        mean_simulated_heating_kwh=None, cbs_gas_m3_per_year=None,
        cbs_conversion=None, cbs_key=None, n_simulated=0,
    )
    report = format_report([result])
    assert "—" in report
    assert "SFH" in report


def test_format_report_includes_every_group():
    results = [_result(building_type="SFH"), _result(building_type="TH", neighbour_status="B_N1")]
    report = format_report(results)
    assert "SFH" in report
    assert "TH" in report
