"""
Tests for ``buem.analysis.netherlands.validation``'s pure-logic pieces
(``TypeGroupResult``, ``format_report``, ``aggregate_parquet``) -- no real
building data, no simulation, no network. ``run_validation()`` itself
needs a real ``CsvBuildingSource`` directory + real weather + a live CBS
query, so it's exercised manually (see
``docs/source/modules/netherlands.rst``'s "Validation" section for real
run results), not here.
"""
from __future__ import annotations

import pandas as pd
import pytest

from buem.analysis.netherlands import validation as validation_module
from buem.analysis.netherlands.cbs_reference import CbsConsumptionFigure
from buem.analysis.netherlands.gas_conversion import gas_m3_to_useful_heat_kwh
from buem.analysis.netherlands.validation import (
    TypeGroupResult,
    aggregate_parquet,
    format_report,
)


def _result(**overrides) -> TypeGroupResult:
    defaults = {
        "building_type": "SFH",
        "neighbour_status": "B_Alone",
        "cbs_key": "detached",
        "n_simulated": 2,
        "mean_simulated_heating_kwh": 6780.0,
        "mean_simulated_dhw_kwh": 1200.0,
        "mean_simulated_cooking_kwh": 130.0,
        "cbs_gas_m3_per_year": 1380.0,
        "cbs_conversion": gas_m3_to_useful_heat_kwh(1380.0),
        "cbs_conversion_full": gas_m3_to_useful_heat_kwh(1380.0, space_heating_share=1.0),
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


def test_mean_simulated_total_kwh_sums_heating_dhw_cooking():
    result = _result()
    assert result.mean_simulated_total_kwh == (6780.0 + 1200.0 + 130.0)


def test_mean_simulated_total_kwh_treats_missing_dhw_cooking_as_zero():
    """A building with no DHW/cooking data (e.g. occupancy generated no
    cooking_active signal) should still report a total -- heating alone,
    not None."""
    result = _result(mean_simulated_dhw_kwh=None, mean_simulated_cooking_kwh=None)
    assert result.mean_simulated_total_kwh == 6780.0


def test_mean_simulated_total_kwh_none_when_no_heating():
    result = _result(mean_simulated_heating_kwh=None)
    assert result.mean_simulated_total_kwh is None


def test_ratio_total_to_cbs_full_computes_expected_value():
    result = _result()
    expected = result.mean_simulated_total_kwh / result.cbs_conversion_full.useful_heat_kwh
    assert result.ratio_total_to_cbs_full == expected


def test_ratio_total_to_cbs_full_none_when_no_cbs_full_data():
    result = _result(cbs_conversion_full=None)
    assert result.ratio_total_to_cbs_full is None


def test_ratio_total_to_cbs_full_none_when_cbs_full_useful_heat_is_zero():
    result = _result(cbs_conversion_full=gas_m3_to_useful_heat_kwh(0.0, space_heating_share=1.0))
    assert result.ratio_total_to_cbs_full is None


# ── aggregate_parquet ────────────────────────────────────────────────────────
# The population-complete path: it reads a finished batch run and never
# simulates, so CBS is the only external dependency and is stubbed here.


@pytest.fixture
def _stub_cbs(monkeypatch):
    """Return a fixed CBS figure for any requested housing-type key."""
    def _fake_fetch(region_code, period, keys=None):
        return {
            key: CbsConsumptionFigure(
                region_code=region_code, period=period, housing_type_key=key,
                gas_m3_per_year=1000.0, electricity_kwh_per_year=3000.0,
            )
            for key in (keys or [])
        }
    monkeypatch.setattr(validation_module, "fetch_consumption", _fake_fetch)


def _batch_frame(rows: list[dict]) -> pd.DataFrame:
    defaults = {
        "status": "ok", "building_type": "SFH", "neighbour_status": "B_Alone",
        "heating_kWh": 10000.0, "dhw_kWh": 2000.0, "cooking_gas_kWh": 200.0,
        "residential_units": 1.0, "matched_via_label": "True",
        "A_ref": 120.0,  # a plausible Dutch dwelling; see IMPLAUSIBLE_M2_PER_DWELLING
    }
    return pd.DataFrame([{**defaults, **row} for row in rows])


def _write_parquet(tmp_path, rows: list[dict]):
    path = tmp_path / "batch.parquet"
    _batch_frame(rows).to_parquet(path)
    return path


def test_aggregate_parquet_means_each_type_group(tmp_path, _stub_cbs):
    path = _write_parquet(tmp_path, [
        {"building_feature_id": 1, "heating_kWh": 10000.0},
        {"building_feature_id": 2, "heating_kWh": 20000.0},
        {"building_feature_id": 3, "building_type": "TH", "neighbour_status": "B_N2", "heating_kWh": 5000.0},
    ])
    results = aggregate_parquet(path, region_code="GM0200", period="2018JJ00")

    by_type = {r.building_type: r for r in results}
    assert by_type["SFH"].n_simulated == 2
    assert by_type["SFH"].mean_simulated_heating_kwh == 15000.0
    assert by_type["TH"].n_simulated == 1
    assert by_type["TH"].mean_simulated_heating_kwh == 5000.0


def test_aggregate_parquet_divides_by_residential_units(tmp_path, _stub_cbs):
    """A multi-dwelling block is simulated whole; CBS publishes per
    dwelling, so the comparison must divide by the real unit count."""
    path = _write_parquet(tmp_path, [
        {"building_feature_id": 1, "building_type": "AB", "neighbour_status": "B_Alone",
         "heating_kWh": 120000.0, "dhw_kWh": 24000.0, "cooking_gas_kWh": 1200.0,
         "residential_units": 12.0},
    ])
    result = aggregate_parquet(path, region_code="GM0200", period="2018JJ00")[0]

    assert result.mean_simulated_heating_kwh == 10000.0
    assert result.mean_simulated_dhw_kwh == 2000.0
    assert result.mean_simulated_cooking_kwh == 100.0


def test_aggregate_parquet_ignores_failed_rows(tmp_path, _stub_cbs):
    path = _write_parquet(tmp_path, [
        {"building_feature_id": 1, "heating_kWh": 10000.0},
        {"building_feature_id": 2, "status": "error", "heating_kWh": None},
        {"building_feature_id": 3, "status": "skipped", "heating_kWh": None},
    ])
    result = aggregate_parquet(path, region_code="GM0200", period="2018JJ00")[0]
    assert result.n_simulated == 1


def test_aggregate_parquet_labeled_only_filters(tmp_path, _stub_cbs):
    path = _write_parquet(tmp_path, [
        {"building_feature_id": 1, "heating_kWh": 10000.0, "matched_via_label": "True"},
        {"building_feature_id": 2, "heating_kWh": 90000.0, "matched_via_label": "False"},
    ])
    unfiltered = aggregate_parquet(path, region_code="GM0200", period="2018JJ00")[0]
    labeled = aggregate_parquet(path, region_code="GM0200", period="2018JJ00", labeled_only=True)[0]

    assert unfiltered.n_simulated == 2
    assert labeled.n_simulated == 1
    assert labeled.mean_simulated_heating_kwh == 10000.0


def test_aggregate_parquet_reports_implausible_dwelling_counts(tmp_path, _stub_cbs, caplog):
    """A wrong dwelling count makes the per-dwelling figure meaningless, so
    it must be surfaced rather than passed off as a modelling result."""
    path = _write_parquet(tmp_path, [
        {"building_feature_id": 1, "A_ref": 19240.0, "residential_units": 2.0},
        {"building_feature_id": 2, "A_ref": 120.0, "residential_units": 1.0},
    ])
    with caplog.at_level("WARNING"):
        aggregate_parquet(path, region_code="GM0200", period="2018JJ00")
    assert "1 of 2 building(s) imply more than" in caplog.text


def test_aggregate_parquet_max_m2_per_dwelling_excludes_rows(tmp_path, _stub_cbs):
    path = _write_parquet(tmp_path, [
        {"building_feature_id": 1, "A_ref": 19240.0, "residential_units": 2.0, "heating_kWh": 900000.0},
        {"building_feature_id": 2, "A_ref": 120.0, "residential_units": 1.0, "heating_kWh": 10000.0},
    ])
    unfiltered = aggregate_parquet(path, region_code="GM0200", period="2018JJ00")[0]
    filtered = aggregate_parquet(
        path, region_code="GM0200", period="2018JJ00", max_m2_per_dwelling=500.0,
    )[0]

    assert unfiltered.n_simulated == 2
    assert filtered.n_simulated == 1
    assert filtered.mean_simulated_heating_kwh == 10000.0


def test_aggregate_parquet_max_m2_per_dwelling_raises_if_it_excludes_everything(tmp_path, _stub_cbs):
    path = _write_parquet(tmp_path, [
        {"building_feature_id": 1, "A_ref": 19240.0, "residential_units": 2.0},
    ])
    with pytest.raises(ValueError, match="excluded every row"):
        aggregate_parquet(path, region_code="GM0200", period="2018JJ00", max_m2_per_dwelling=500.0)


def test_dwelling_area_check_treats_missing_or_zero_units_as_one():
    """A missing count must not divide by zero or NaN -- it falls back to a
    single dwelling, which is also what makes it show up as implausible."""
    from buem.analysis.netherlands.validation import dwelling_area_check

    df = pd.DataFrame({
        "A_ref": [1000.0, 1000.0, 1000.0],
        "residential_units": [None, 0.0, 4.0],
    })
    assert list(dwelling_area_check(df)) == [1000.0, 1000.0, 250.0]


def test_aggregate_parquet_raises_when_nothing_simulated(tmp_path, _stub_cbs):
    """An all-failed run must say so rather than reporting empty groups as
    if the comparison had succeeded."""
    path = _write_parquet(tmp_path, [{"building_feature_id": 1, "status": "error", "heating_kWh": None}])
    with pytest.raises(ValueError, match="no successfully-simulated rows"):
        aggregate_parquet(path, region_code="GM0200", period="2018JJ00")
