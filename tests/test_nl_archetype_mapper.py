"""
Tests for ``buem.buildings.datasources.nl_archetype_mapper`` -- pure unit
tests against synthetic data plus, where marked, the real bundled NL
TABULA sheet (no CityJSON/RIVM file needed -- ``tabula.csv`` is small and
already git-tracked).
"""
from __future__ import annotations

import pandas as pd
import pytest

from buem.buildings.datasources.nl_archetype_mapper import (
    label_to_construction_class,
    map_buildings,
    year_to_construction_class,
)

NL_DATA_DIR = "src/buem/data/buildings/netherlands"

_nl_tabula_missing_reason = None
try:
    _nl_tabula = pd.read_csv(f"{NL_DATA_DIR}/tabula.csv", na_values=["NULL"])
    _nl_tabula = _nl_tabula[_nl_tabula["Code_Country"] == "NL"]
except FileNotFoundError as exc:
    _nl_tabula = None
    _nl_tabula_missing_reason = str(exc)

requires_nl_tabula = pytest.mark.skipif(_nl_tabula is None, reason=_nl_tabula_missing_reason or "")


# ── year_to_construction_class ───────────────────────────────────────────


def test_year_to_construction_class_boundaries():
    assert year_to_construction_class(1900) == "NL.01"
    assert year_to_construction_class(1964) == "NL.01"
    assert year_to_construction_class(1965) == "NL.02"
    assert year_to_construction_class(1974) == "NL.02"
    assert year_to_construction_class(1975) == "NL.03"
    assert year_to_construction_class(1991) == "NL.03"
    assert year_to_construction_class(1992) == "NL.04"
    assert year_to_construction_class(2005) == "NL.04"
    assert year_to_construction_class(2006) == "NL.05"
    assert year_to_construction_class(2014) == "NL.05"
    assert year_to_construction_class(2015) == "NL.06"
    assert year_to_construction_class(2026) == "NL.06"


def test_year_to_construction_class_missing_year_returns_none():
    assert year_to_construction_class(None) is None
    assert year_to_construction_class(float("nan")) is None


# ── label_to_construction_class ──────────────────────────────────────────


def test_label_to_construction_class_known_labels():
    assert label_to_construction_class("G") == "NL.01"
    assert label_to_construction_class("C") == "NL.03"
    assert label_to_construction_class("A+++++") == "NL.06"


def test_label_to_construction_class_missing_or_unknown():
    assert label_to_construction_class(None) is None
    assert label_to_construction_class(float("nan")) is None
    assert label_to_construction_class("not-a-real-label") is None


# ── map_buildings: end-to-end on synthetic data + real TABULA NL sheet ──


def _synthetic_buildings():
    return pd.DataFrame([
        {  # detached, real construction year, no label -> year-driven match
            "bag_pand_id": "A", "construction_year": 1980, "attached_neighbour_id": None,
            "is_greenhouse_or_warehouse": False, "is_glass_roof": False,
        },
        {  # detached, has a real label -> label overrides year
            "bag_pand_id": "B", "construction_year": 1980, "attached_neighbour_id": None,
            "is_greenhouse_or_warehouse": False, "is_glass_roof": False,
        },
        {  # non-residential, large -> excluded from TABULA but linked to a service type
            "bag_pand_id": "C", "construction_year": 2000, "attached_neighbour_id": None,
            "is_greenhouse_or_warehouse": True, "is_glass_roof": False, "footprint_area": 2000.0,
        },
    ])


@requires_nl_tabula
def test_map_buildings_year_driven_match():
    rivm = pd.DataFrame(columns=["bag_pand_id", "aant_verblijfsobj", "dominant_label"])
    result = map_buildings(_synthetic_buildings(), _nl_tabula, rivm)
    row_a = result.set_index("bag_pand_id").loc["A"]
    assert row_a["is_residential"]
    assert row_a["building_type"] == "SFH"
    assert row_a["construction_year_class"] == "NL.03"  # 1980 -> 1975-1991
    assert not row_a["matched_via_label"]
    assert pd.notna(row_a["tabula_variant_code_id"])
    assert row_a["tabula_variant_code"].startswith("NL.N.SFH.03.")
    assert row_a["residential_units"] == 1.0  # no RIVM match -> single-dwelling default


@requires_nl_tabula
def test_map_buildings_residential_units_carries_real_rivm_count():
    """Regression test for the 2026-08-18 fix: a multi-unit building's
    real dwelling count must survive as its own output column, not just
    be consumed internally by classify_all() -- found necessary when a
    validation script needed to normalize a whole-*building* simulation
    result back to a per-*dwelling* figure for a fair CBS comparison
    (real Loenen AB buildings are whole apartment blocks with 257-756 m2
    footprints, not single units)."""
    rivm = pd.DataFrame([{"bag_pand_id": "B", "aant_verblijfsobj": 12.0, "dominant_label": None}])
    result = map_buildings(_synthetic_buildings(), _nl_tabula, rivm)
    row_b = result.set_index("bag_pand_id").loc["B"]
    assert row_b["residential_units"] == 12.0


@requires_nl_tabula
def test_map_buildings_label_overrides_year():
    # building B: real construction_year says 1980 (NL.03), but a real
    # label "A+++" says NL.06 -- the label should win.
    rivm = pd.DataFrame([{"bag_pand_id": "B", "aant_verblijfsobj": 1.0, "dominant_label": "A+++"}])
    result = map_buildings(_synthetic_buildings(), _nl_tabula, rivm)
    row_b = result.set_index("bag_pand_id").loc["B"]
    assert row_b["construction_year_class"] == "NL.06"
    assert row_b["matched_via_label"]
    assert row_b["tabula_variant_code"].startswith("NL.N.SFH.06.")


@requires_nl_tabula
def test_map_buildings_excludes_non_residential():
    rivm = pd.DataFrame(columns=["bag_pand_id", "aant_verblijfsobj", "dominant_label"])
    result = map_buildings(_synthetic_buildings(), _nl_tabula, rivm)
    row_c = result.set_index("bag_pand_id").loc["C"]
    assert not row_c["is_residential"]
    assert pd.isna(row_c["tabula_variant_code_id"])
    # excluded from TABULA, but still linked to occupancy's service-building
    # path -- classify_all()'s own service_building_type column survives
    # map_buildings() unchanged (see nl_building_classifier)
    assert row_c["service_building_type"] == "warehouse"
