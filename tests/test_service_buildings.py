"""Tests for the non-residential (service-building) mapping path.

TABULA is a residential typology, so a warehouse or school has no
archetype row and used to be skipped before ``AttributeBuilder`` -- and
therefore before occupancy's ``ServiceBuildingProfile`` -- was ever
reached. These cover the reference-table fallback that closes that gap,
without needing real region data.
"""
from __future__ import annotations

import pandas as pd
import pytest

from buem.buildings.mapping.archetype_spec import (
    spec_from_service_reference,
    spec_from_tabula,
)


def _service_row(**overrides) -> pd.Series:
    base = {
        "service_building_type": "warehouse",
        "construction_year_class": "NL.03",
        "U_Wall": 0.769, "U_Roof": 0.769, "U_Floor": 0.769,
        "U_Window": 5.2, "U_Door": 3.5, "g_gl_Window": 0.6,
        "door_to_wall_ratio": 0.03, "h_room": 6.0, "c_m": 110.0,
        "n_air_infiltration": 0.45, "n_air_use": 0.30,
        "F_red_htr": 0.80, "design_T_min": -12.0,
    }
    base.update(overrides)
    return pd.Series(base)


def test_service_spec_carries_reference_values():
    spec = spec_from_service_reference(_service_row())

    assert spec.wall_U == 0.769
    assert spec.h_room == 6.0
    assert spec.n_air_use == 0.30
    assert spec.building_type == "warehouse"
    assert spec.construction_period == "NL.03"


def test_service_spec_has_no_party_walls():
    """A warehouse carries no attached-neighbour typology, so its whole
    envelope is exposed rather than partly adiabatic."""
    assert spec_from_service_reference(_service_row()).neighbour_status == "B_Alone"


def test_service_spec_leaves_internal_gains_to_occupancy():
    """phi_int would be a static per-m2 archetype figure; service-building
    gains come from occupancy's own per-category model instead, so a value
    here would silently compete with it."""
    spec = spec_from_service_reference(_service_row())
    assert spec.phi_int is None
    assert spec.q_w_nd is None


def test_service_spec_falls_back_on_missing_columns():
    """A hand-edited table missing an optional column must still map,
    rather than failing the whole building."""
    spec = spec_from_service_reference(pd.Series({
        "service_building_type": "office", "construction_year_class": "NL.05",
        "U_Wall": 0.286,
    }))
    assert spec.wall_U == 0.286
    assert spec.h_room == 3.0  # documented default
    assert spec.door_U == 3.0


# ── refurbishment-measure overrides (issue #5) ──────────────────────────


def _tabula_row_with_window_measure(r_value: float) -> pd.Series:
    return pd.Series({
        "U_Wall_1": 0.30, "U_Roof_1": 0.30, "U_Floor_1": 0.30,
        "U_Window_1": 5.2, "U_Door_1": 3.0, "g_gl_n_Window_1": 0.6,
        "b_Transmission_Wall_1": 1.0, "b_Transmission_Roof_1": 1.0,
        "b_Transmission_Floor_1": 0.5,
        "A_Wall_1": 100.0, "A_Door_1": 2.0,
        "Code_Measure_Window_1": "NL.Window.Ins.01",
        "Code_MeasureType_Window_1": "Replace",
        "R_PredefinedMeasure_Window_1": r_value,
        "Code_BuildingSizeClass": "MFH",
        "Code_ConstructionYearClass": "NL.02",
        "Code_AttachedNeighbours": "B_N1",
    })


def test_window_measure_override_replaces_published_resistance():
    """TABULA's NL.Window.Ins.01 implies U = 1.8 (HR glazing); real stock
    refurbished to that tier has HR++ at 1.1-1.2."""
    row = _tabula_row_with_window_measure(0.555556)

    as_published = spec_from_tabula(row)
    assert as_published.window_U == pytest.approx(1.80, rel=0.01)

    overrides = pd.DataFrame([{"measure_code": "NL.Window.Ins.01", "R_value": 0.870}])
    corrected = spec_from_tabula(row, measure_overrides=overrides)
    assert corrected.window_U == pytest.approx(1.149, rel=0.01)


def test_measure_override_only_touches_the_named_measure():
    row = _tabula_row_with_window_measure(0.555556)
    overrides = pd.DataFrame([{"measure_code": "NL.Window.Ins.01", "R_value": 0.870}])

    baseline = spec_from_tabula(row)
    corrected = spec_from_tabula(row, measure_overrides=overrides)

    assert corrected.wall_U == baseline.wall_U
    assert corrected.roof_U == baseline.roof_U
    assert corrected.door_U == baseline.door_U


def test_unmatched_measure_override_is_a_no_op():
    row = _tabula_row_with_window_measure(0.555556)
    overrides = pd.DataFrame([{"measure_code": "NL.Window.Ins.99", "R_value": 0.870}])
    assert spec_from_tabula(row, measure_overrides=overrides).window_U == pytest.approx(1.80, rel=0.01)


def test_bundled_reference_tables_cover_every_occupancy_service_type():
    """A drift guard: occupancy owning the type registry means a new type
    there would otherwise silently become unmappable here."""
    import occupancy

    table = pd.read_csv("src/buem/data/buildings/netherlands/Loenen/service_building_reference.csv")
    missing = set(occupancy.SERVICE_BUILDING_TYPES) - set(table["service_building_type"])
    assert not missing, f"service_building_reference.csv is missing rows for {sorted(missing)}"
