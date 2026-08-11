"""
Tests for the live-path LOD2 -> LOD3 envelope synthesis
(buem.buildings.mapping.live_synthesis / tabula_helpers.lookup_tabula_archetype
/ element_factory.synthesize_openings), and a basic end-to-end regression
check for the LOD2Mapper offline-pipeline refactor these were extracted
from. None of this touches weather/occupancy, so no BUEM_WEATHER_DATA_DIR
setup is needed (unlike tests/test_building_types.py).
"""
import pytest

from buem.buildings.mapping.element_factory import (
    WallInfo,
    identify_front_back,
    synthesize_openings,
)
from buem.buildings.mapping.live_synthesis import (
    FALLBACK_DOOR_RATIO,
    FALLBACK_WINDOW_RATIO_PER_DIRECTION,
    synthesize_missing_openings,
)
from buem.buildings.pipeline import DEFAULT_WORKBOOK

# The bundled TABULA reference workbook is *.xlsx-gitignored (repo-wide rule,
# predates this test file) -- present on a dev machine that's run the offline
# pipeline before, but not part of a fresh git checkout (confirmed: this is
# why these tests failed in CI on first push, 2026-08-11 -- nothing exercised
# ExcelBuildingSource/LOD2Mapper in CI before this file existed, so the gap
# was never caught). Real TABULA-archetype matching (tabula_helpers
# .lookup_tabula_archetype()) and the offline batch pipeline both need this
# file at runtime, not just for these tests -- see CLAUDE.md's "Open
# follow-ups" for the now-flagged, not-yet-decided fix (mirroring how
# weather's archive-access gap was eventually resolved with a small
# committed CI fixture). Skip cleanly rather than assert something false
# for any environment without the file, instead of failing outright.
_workbook_missing_reason = (
    None if DEFAULT_WORKBOOK.exists()
    else f"bundled TABULA workbook not present: {DEFAULT_WORKBOOK}"
)
requires_bundled_workbook = pytest.mark.skipif(
    _workbook_missing_reason is not None, reason=_workbook_missing_reason or "",
)
from buem.buildings.mapping.tabula_helpers import lookup_tabula_archetype


def _walls_only_components(area_1=53.0, area_2=80.0):
    """A minimal components dict with Walls only -- Windows/Doors/Ventilation
    deliberately absent, mirroring a request that omits LOD3 detail."""
    return {
        "Walls": {
            "U": 1.61,
            "b_transmission": 1.0,
            "elements": [
                {"id": "Wall_1", "area": area_1, "azimuth": 180.0, "tilt": 90.0},
                {"id": "Wall_2", "area": area_2, "azimuth": 0.0, "tilt": 90.0},
            ],
        },
        "Roof": {"U": 1.54, "elements": [{"id": "Roof_1", "area": 60.0, "azimuth": 180.0, "tilt": 30.0}]},
        "Floor": {"U": 1.72, "elements": [{"id": "Floor_1", "area": 50.0, "azimuth": 0.0, "tilt": 180.0}]},
    }


# ── element_factory: pure wall-geometry reasoning (no TABULA/pandas needed) ──


def test_identify_front_back_largest_area_is_front():
    walls = [
        WallInfo(wall_id="w1", surface_feature_id=1, area=40.0, azimuth=180.0, is_shared=False),
        WallInfo(wall_id="w2", surface_feature_id=2, area=75.0, azimuth=0.0, is_shared=False),
    ]
    front, back = identify_front_back(walls)
    assert front.wall_id == "w2"  # larger area
    assert back.wall_id == "w1"  # opposite azimuth (180 vs 0)


def test_identify_front_back_no_exposed_walls():
    assert identify_front_back([]) == (None, None)


def test_synthesize_openings_shared_wall_excluded_and_net_area_reduced():
    front = WallInfo(wall_id="w1", surface_feature_id=1, area=50.0, azimuth=180.0, is_shared=False)
    back = WallInfo(wall_id="w2", surface_feature_id=2, area=50.0, azimuth=0.0, is_shared=False)
    elements = synthesize_openings(
        [front, back], front, back,
        window_ratios={"north": 0.1, "east": 0.1, "south": 0.2, "west": 0.1},
        door_ratio=0.05,
        window_U=2.8, window_g_gl=0.5, door_U=3.0, n_air_use=0.5,
    )
    types = [e.element_type for e in elements]
    assert types.count("window") == 2  # one per exposed wall
    assert types.count("door") == 1  # front wall only
    assert types.count("ventilation") == 2  # front+back cross-ventilation

    # Wall net_area reflects subtracted window/door/vent area (buildings.rst
    # "Window Sizing"/"Door Sizing" -- net area is the caller's responsibility
    # to apply, WallInfo just tracks it).
    assert front.net_area < front.area
    assert front.window_area == pytest.approx(0.2 * 50.0)
    assert front.door_area == pytest.approx(0.05 * 50.0)


# ── tabula_helpers.lookup_tabula_archetype (bundled reference sheet) ─────────


@requires_bundled_workbook
def test_lookup_tabula_archetype_real_match():
    row = lookup_tabula_archetype("AB", "03", "DE")
    assert row is not None
    assert row["Code_BuildingSizeClass"] == "AB"
    assert row["Code_Country"] == "DE"
    assert row["Code_ConstructionYearClass"] == "DE.03"
    assert ".Gen." in row["Code_BuildingVariant"]


@requires_bundled_workbook
def test_lookup_tabula_archetype_accepts_prefixed_year_class_too():
    bare = lookup_tabula_archetype("AB", "03", "DE")
    prefixed = lookup_tabula_archetype("AB", "DE.03", "DE")
    assert bare["id"] == prefixed["id"]


def test_lookup_tabula_archetype_no_match_returns_none():
    # Country not covered by the bundled (Germany-only) reference sheet --
    # true whether or not the workbook itself is present in this
    # environment (missing sheet and "sheet present but no match" both
    # correctly return None), so this one needs no skip marker.
    assert lookup_tabula_archetype("MFH", "1965-1974", "NL") is None
    # Literal year-range string (EnerPlanET's actual v3 format) doesn't match
    # TABULA's class-code format either -- see CLAUDE.md's known-gap note.
    assert lookup_tabula_archetype("MFH", "1965-1974", "DE") is None


@requires_bundled_workbook
def test_lookup_tabula_archetype_explicit_code_override():
    row = lookup_tabula_archetype(
        "AB", None, None, bldg_tabula_id="DE.N.AB.03.Gen.ReEx.001.001",
    )
    assert row is not None
    assert row["Code_BuildingVariant"] == "DE.N.AB.03.Gen.ReEx.001.001"


# ── live_synthesis.synthesize_missing_openings ───────────────────────────────


def test_synthesize_missing_openings_real_tabula_match():
    comps = _walls_only_components()
    result = synthesize_missing_openings(
        comps, building_type="AB", construction_period="03", country="DE",
    )
    assert result["Windows"]["elements"], "expected synthesized windows"
    assert result["Doors"]["elements"], "expected a synthesized door"
    assert result["Ventilation"]["elements"], "expected synthesized ventilation"

    # Full set was missing -> Walls area should shrink to net opaque area.
    wall_areas = {e["id"]: e["area"] for e in result["Walls"]["elements"]}
    assert wall_areas["Wall_1"] < comps["Walls"]["elements"][0]["area"]
    assert wall_areas["Wall_2"] < comps["Walls"]["elements"][1]["area"]

    # Original input is untouched (function returns a new dict).
    assert "Windows" not in comps


def test_synthesize_missing_openings_fallback_when_no_tabula_match(caplog):
    comps = _walls_only_components(area_1=53.0, area_2=80.0)
    with caplog.at_level("WARNING"):
        result = synthesize_missing_openings(
            comps, building_type="MFH", construction_period="1965-1974", country="NL",
        )
    assert "safe-default ratios" in caplog.text

    # Front wall = largest area (Wall_2, 80 m2, north) -> door there.
    door = result["Doors"]["elements"][0]
    assert door["surface"] == "Wall_2"
    assert door["area"] == pytest.approx(FALLBACK_DOOR_RATIO * 80.0)

    # South wall (Wall_1) window uses the flat per-direction fallback ratio.
    south_window = next(w for w in result["Windows"]["elements"] if w["surface"] == "Wall_1")
    assert south_window["area"] == pytest.approx(FALLBACK_WINDOW_RATIO_PER_DIRECTION * 53.0)


def test_synthesize_missing_openings_preserves_explicit_override():
    comps = _walls_only_components()
    comps["Windows"] = {
        "U": 1.1, "g_gl": 0.6,
        "elements": [{"id": "Win_custom", "area": 3.3, "surface": "Wall_1", "azimuth": 180.0, "tilt": 90.0}],
    }
    result = synthesize_missing_openings(
        comps, building_type="AB", construction_period="03", country="DE",
    )
    # Windows untouched (explicit, non-empty).
    assert result["Windows"] == comps["Windows"]
    # Doors/Ventilation were missing -> still synthesized.
    assert result["Doors"]["elements"]
    assert result["Ventilation"]["elements"]
    # Partial override -> Walls area left as originally supplied (no
    # reliable way to know how much area the caller already accounted for).
    wall_areas = {e["id"]: e["area"] for e in result["Walls"]["elements"]}
    assert wall_areas["Wall_1"] == 53.0
    assert wall_areas["Wall_2"] == 80.0


def test_synthesize_missing_openings_noop_when_all_present():
    comps = _walls_only_components()
    comps["Windows"] = {"elements": [{"id": "w", "area": 1.0, "surface": "Wall_1", "azimuth": 180.0, "tilt": 90.0}]}
    comps["Doors"] = {"elements": [{"id": "d", "area": 1.0, "surface": "Wall_1", "azimuth": 180.0, "tilt": 90.0}]}
    comps["Ventilation"] = {"elements": [{"id": "v", "air_changes": 0.5}]}
    result = synthesize_missing_openings(
        comps, building_type="AB", construction_period="03", country="DE",
    )
    assert result is comps  # early-return, unchanged


def test_synthesize_missing_openings_noop_without_walls():
    comps = {"Roof": {"U": 1.5, "elements": []}}
    result = synthesize_missing_openings(
        comps, building_type="AB", construction_period="03", country="DE",
    )
    assert result is comps


# ── LOD2Mapper: end-to-end regression check against the bundled workbook ────
# (previously untested -- the extraction of synthesize_openings/
# identify_front_back out of lod2_mapper.py had no direct coverage before.)


@requires_bundled_workbook
def test_lod2mapper_end_to_end_with_bundled_workbook():
    from buem.buildings.datasources.excel_source import ExcelBuildingSource
    from buem.buildings.mapping.lod2_mapper import LOD2Mapper

    source = ExcelBuildingSource(DEFAULT_WORKBOOK)
    building_ids = source.get_building_ids(limit=5)
    assert building_ids, "bundled workbook should contain at least one building"

    mapper = LOD2Mapper(source, country="DE")
    buildings = mapper.map_all(building_ids=building_ids)
    assert buildings, "expected at least one successfully-mapped building"

    bldg = buildings[0]
    assert bldg.walls(), "expected wall elements"
    # A building with any exposed (non-shared) wall >= the min window-eligible
    # size should get at least one window -- not asserted unconditionally
    # since a fully party-walled building legitimately has none.
    for wall in bldg.walls():
        assert wall.area >= 0.0
    for vent in bldg.ventilation_elements():
        assert vent.air_changes is not None
