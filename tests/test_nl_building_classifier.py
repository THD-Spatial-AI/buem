"""
Tests for ``buem.buildings.mapping.nl_building_classifier`` -- pure-Python
unit tests against synthetic adjacency data, no CityJSON/RIVM file needed.
"""
from __future__ import annotations

import pandas as pd

from buem.buildings.mapping.nl_building_classifier import (
    MIN_SERVICE_BUILDING_FOOTPRINT_M2,
    build_adjacency,
    classify_all,
    classify_building_type,
    connected_component_sizes,
)


def _bldg(pid, neighbours=None, units=None, kas=False, glas=False, footprint=0.0):
    return {
        "bag_pand_id": pid,
        "attached_neighbour_id": ";".join(neighbours) if neighbours else None,
        "is_greenhouse_or_warehouse": kas,
        "is_glass_roof": glas,
        "footprint_area": footprint,
    }


# ── classify_building_type: the CBS rules directly ──────────────────────


def test_classify_detached():
    assert classify_building_type(degree=0, component_size=1, n_residential_units=1) == ("SFH", "B_Alone")


def test_classify_semi_detached_pair():
    # degree 1, component of exactly 2 -> twee-onder-een-kap -> SFH/B_N1
    assert classify_building_type(degree=1, component_size=2, n_residential_units=1) == ("SFH", "B_N1")


def test_classify_corner_house():
    # degree 1, but part of a row of 3+ -> hoekwoning -> TH/B_N1
    assert classify_building_type(degree=1, component_size=4, n_residential_units=1) == ("TH", "B_N1")


def test_classify_mid_terrace():
    assert classify_building_type(degree=2, component_size=5, n_residential_units=1) == ("TH", "B_N2")


def test_classify_multi_family_small():
    building_type, status = classify_building_type(degree=0, component_size=1, n_residential_units=3)
    assert building_type == "MFH"
    assert status == "B_Alone"


def test_classify_multi_family_large_is_apartment_block():
    building_type, _ = classify_building_type(degree=0, component_size=1, n_residential_units=20)
    assert building_type == "AB"


def test_classify_missing_units_defaults_to_single_family_path():
    # None/0 units -> treated as 1 (the common case), not "unknown multi-unit"
    assert classify_building_type(degree=0, component_size=1, n_residential_units=None) == ("SFH", "B_Alone")
    assert classify_building_type(degree=0, component_size=1, n_residential_units=0) == ("SFH", "B_Alone")


# ── adjacency graph + connected components ───────────────────────────────


def test_build_adjacency_is_symmetric():
    df = pd.DataFrame([_bldg("A", ["B"]), _bldg("B", None)])  # only A lists B
    graph = build_adjacency(df)
    assert graph["A"] == {"B"}
    assert graph["B"] == {"A"}  # symmetric even though only recorded on A's row


def test_connected_component_sizes_row_of_three():
    # A - B - C, a row of 3 (B is mid-terrace, A/C are corner units)
    df = pd.DataFrame([_bldg("A", ["B"]), _bldg("B", ["A", "C"]), _bldg("C", ["B"])])
    graph = build_adjacency(df)
    sizes = connected_component_sizes(graph)
    assert sizes == {"A": 3, "B": 3, "C": 3}


def test_connected_component_sizes_isolated_building():
    df = pd.DataFrame([_bldg("A", None)])
    sizes = connected_component_sizes(build_adjacency(df))
    assert sizes["A"] == 1


# ── classify_all: end-to-end on a small synthetic dataset ───────────────


def test_classify_all_end_to_end_row_of_three_plus_detached_plus_apartment():
    df = pd.DataFrame([
        _bldg("detached", None),
        _bldg("corner1", ["mid"]),
        _bldg("mid", ["corner1", "corner2"]),
        _bldg("corner2", ["mid"]),
        _bldg("apartments", None, units=12),
        _bldg("big_warehouse", None, kas=True, footprint=2000.0),
        _bldg("garden_shed", None, glas=True, footprint=16.0),
    ])
    units = {"apartments": 12.0}
    result = classify_all(df, units)

    by_id = result.set_index("bag_pand_id")
    assert tuple(by_id.loc["detached", ["building_type", "neighbour_status"]]) == ("SFH", "B_Alone")
    assert tuple(by_id.loc["corner1", ["building_type", "neighbour_status"]]) == ("TH", "B_N1")
    assert tuple(by_id.loc["mid", ["building_type", "neighbour_status"]]) == ("TH", "B_N2")
    assert tuple(by_id.loc["corner2", ["building_type", "neighbour_status"]]) == ("TH", "B_N1")
    assert by_id.loc["apartments", "building_type"] == "AB"

    # large flagged building -> real service_building_type, still not residential
    assert by_id.loc["big_warehouse", "is_residential"] == False  # noqa: E712
    assert pd.isna(by_id.loc["big_warehouse", "building_type"])
    assert by_id.loc["big_warehouse", "service_building_type"] == "warehouse"

    # tiny flagged building -> excluded from both residential AND service modeling
    assert by_id.loc["garden_shed", "is_residential"] == False  # noqa: E712
    assert pd.isna(by_id.loc["garden_shed", "building_type"])
    assert pd.isna(by_id.loc["garden_shed", "service_building_type"])

    # ordinary residential buildings never get a service_building_type
    assert pd.isna(by_id.loc["detached", "service_building_type"])


def test_classify_all_excludes_buildings_with_no_registered_residential_unit():
    """A Pand matched in RIVM's data (present in units_by_pand_id) but
    with zero or null residential units registered under it is a real
    non-dwelling (a shed/garage/outbuilding), not an ambiguous case --
    excluded from residential classification the same as a flagged
    greenhouse/warehouse, distinct from no RIVM match at all."""
    df = pd.DataFrame([
        _bldg("shed_zero", None, footprint=15.0),
        _bldg("shed_null", None, footprint=20.0),
        _bldg("real_house_no_match", None, footprint=90.0),
        _bldg("real_house_matched", None, footprint=110.0),
    ])
    units = {"shed_zero": 0.0, "shed_null": float("nan"), "real_house_matched": 1.0}
    result = classify_all(df, units)
    by_id = result.set_index("bag_pand_id")

    assert by_id.loc["shed_zero", "is_residential"] == False  # noqa: E712
    assert pd.isna(by_id.loc["shed_zero", "building_type"])
    assert by_id.loc["shed_null", "is_residential"] == False  # noqa: E712
    assert pd.isna(by_id.loc["shed_null", "building_type"])

    # No RIVM match at all stays ambiguous, not excluded -- unlike a
    # matched-but-zero/null record, "unknown" isn't treated as evidence
    # of non-residential.
    assert by_id.loc["real_house_no_match", "is_residential"] == True  # noqa: E712
    assert by_id.loc["real_house_no_match", "building_type"] == "SFH"

    assert by_id.loc["real_house_matched", "is_residential"] == True  # noqa: E712
    assert by_id.loc["real_house_matched", "building_type"] == "SFH"


def test_classify_all_glass_roof_large_enough_also_links_to_service_type():
    """A real large glass-roofed structure (e.g. a genuine greenhouse
    complex) should link to a service type too, not just b3_kas_warenhuis
    ones -- Loenen's own is_glas_dak buildings happen to both be tiny, but
    the rule itself isn't flag-specific, only size-specific."""
    df = pd.DataFrame([_bldg("real_greenhouse", None, glas=True, footprint=500.0)])
    result = classify_all(df, {})
    assert result.iloc[0]["service_building_type"] == "warehouse"


def test_min_service_building_footprint_constant_is_between_real_loenen_cases():
    """Sanity check on the threshold itself against the real evidence it
    was set from (2,125/1,718 m² real commercial structures vs.
    16/5 m² garden structures) -- not a finely-tuned cutoff, just needs
    to sit clearly between the two real clusters."""
    assert 16.0 < MIN_SERVICE_BUILDING_FOOTPRINT_M2 < 1718.0
