"""Tests for ``buem.analysis.netherlands.construction_year_stratification``'s
pure-logic pieces (population counting, skew reporting, weighted-mean
math) -- real Loenen/Apeldoorn data, no simulation (``run_era_stratification()``
itself is a slow, real-simulation investigative tool, exercised manually --
see ``.claude/dhw_cooking_heat_handoff.md``'s "Construction-year
stratification" section for real run results, not here).

Gated the same way ``test_netherlands_data_source.py`` gates on the real
Loenen data: skip cleanly, don't fail, when it's absent (fresh checkout, CI).
"""
from __future__ import annotations

import pytest

from buem.analysis.netherlands.construction_year_stratification import (
    EraStratum,
    format_era_report,
    population_distribution,
    population_weighted_intensity,
    sample_skew_report,
)
from buem.buildings.datasources.csv_source import CsvBuildingSource

NL_DATA_DIR = "src/buem/data/buildings/netherlands/Loenen"

_nl_data_missing_reason = None
try:
    CsvBuildingSource(NL_DATA_DIR)
except FileNotFoundError as exc:
    _nl_data_missing_reason = str(exc)

requires_nl_data = pytest.mark.skipif(
    _nl_data_missing_reason is not None, reason=_nl_data_missing_reason or "",
)


@requires_nl_data
def test_population_distribution_shares_sum_to_one_per_type():
    dist = population_distribution(NL_DATA_DIR)
    totals = dist.groupby("building_type")["population_share"].sum()
    for btype, total in totals.items():
        assert total == pytest.approx(1.0), f"{btype}'s shares sum to {total}, not 1.0"


@requires_nl_data
def test_population_distribution_counts_are_positive():
    dist = population_distribution(NL_DATA_DIR)
    assert (dist["population_count"] > 0).all()


@requires_nl_data
def test_sample_skew_report_runs_and_names_every_building_type():
    report = sample_skew_report(NL_DATA_DIR, samples_per_group=5)
    for btype in ("SFH", "TH", "MFH", "AB"):
        assert btype in report


def test_population_weighted_intensity_matches_manual_calculation():
    """Pure math, no real data needed -- a hand-built two-stratum example."""
    results = [
        EraStratum(
            building_type="SFH", construction_class="NL.01", u_wall=2.0,
            population_count=80, population_share=0.8,
            sample_building_id="1", heating_kwh=200.0, a_ref_m2=1.0,
        ),
        EraStratum(
            building_type="SFH", construction_class="NL.06", u_wall=0.2,
            population_count=20, population_share=0.2,
            sample_building_id="2", heating_kwh=50.0, a_ref_m2=1.0,
        ),
    ]
    weighted = population_weighted_intensity(results)
    # intensity: 200.0 and 50.0 (A_ref=1.0 for both) -> weighted mean
    # = 200*0.8 + 50*0.2 = 170.0
    assert weighted["SFH"] == pytest.approx(170.0)


def test_population_weighted_intensity_skips_strata_with_no_simulation():
    results = [
        EraStratum(
            building_type="SFH", construction_class="NL.01", u_wall=2.0,
            population_count=80, population_share=0.8,
            sample_building_id="1", heating_kwh=200.0, a_ref_m2=1.0,
        ),
        EraStratum(
            # Simulation failed for this stratum -- heating_kwh/a_ref_m2 are None.
            building_type="SFH", construction_class="NL.06", u_wall=0.2,
            population_count=20, population_share=0.2,
            sample_building_id=None, heating_kwh=None, a_ref_m2=None,
        ),
    ]
    weighted = population_weighted_intensity(results)
    # Only NL.01 contributes -- its own intensity, not blended with a
    # missing value treated as zero.
    assert weighted["SFH"] == pytest.approx(200.0)


def test_era_stratum_intensity_none_when_a_ref_missing_or_zero():
    stratum = EraStratum(
        building_type="SFH", construction_class="NL.01", u_wall=2.0,
        population_count=1, population_share=1.0,
        sample_building_id="1", heating_kwh=100.0, a_ref_m2=0.0,
    )
    assert stratum.intensity_kwh_m2 is None


def test_format_era_report_handles_missing_simulation_gracefully():
    results = [
        EraStratum(
            building_type="SFH", construction_class="NL.01", u_wall=None,
            population_count=5, population_share=1.0,
            sample_building_id=None, heating_kwh=None, a_ref_m2=None,
        ),
    ]
    report = format_era_report(results)
    assert "SFH" in report
    assert "—" in report
