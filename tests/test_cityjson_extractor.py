"""
Tests for ``buem.buildings.datasources.cityjson_extractor``'s own geometry
primitives and party-wall detection -- pure-Python unit tests against
synthetic geometry, no CityJSON file or NL data drop needed (unlike
``test_netherlands_data_source.py``, which tests the *data* this module
produces).
"""
from __future__ import annotations

import struct

from buem.buildings.datasources.cityjson_extractor import (
    _encode_point_ewkb,
    _estimate_storeys,
    _face_area_and_normal,
    _RawFace,
    detect_party_walls,
)
from buem.buildings.mapping.geometry_utils import wkb_point_to_lat_lon


def _make_resolver(points: dict[int, tuple[float, float, float]]):
    """A trivial vertex resolver over a plain {index: (x, y, z)} dict --
    stands in for cityjson_extractor's real _VertexResolver, which applies
    a CityJSON transform this test doesn't need."""
    return lambda idx: points[idx]


# ── _face_area_and_normal: holes (2026-08-17 regression) ────────────────


def test_face_area_and_normal_simple_square_no_holes():
    """A flat 10x10 square in the XY plane, wound counter-clockwise as
    seen from +Z -- area 100, normal straight up."""
    points = {0: (0, 0, 0), 1: (10, 0, 0), 2: (10, 10, 0), 3: (0, 10, 0)}
    resolve = _make_resolver(points)
    area, nx, ny, nz = _face_area_and_normal([[0, 1, 2, 3]], resolve)
    assert area == 100.0
    assert (nx, ny, nz) == (0.0, 0.0, 1.0)


def test_face_area_and_normal_subtracts_a_hole():
    """Regression test for the 2026-08-17 fix: a face with an interior
    ring (hole) must have that ring's area subtracted, not silently
    ignored. Confirmed against 128 real Loenen buildings/144 faces this
    way (see cityjson_extractor's module docstring) -- this is the
    minimal synthetic version of that real-data finding. Outer: 10x10
    square (area 100). Hole: 2x2 square (area 4) wound *opposite* to the
    outer ring, matching CityJSON's/OGC's own interior-ring convention
    (confirmed on real data: every real hole's Newell vector pointed
    opposite the outer ring's, not the same direction)."""
    points = {
        0: (0, 0, 0), 1: (10, 0, 0), 2: (10, 10, 0), 3: (0, 10, 0),  # outer, CCW from +Z
        4: (4, 4, 0), 5: (4, 6, 0), 6: (6, 6, 0), 7: (6, 4, 0),      # hole, CW from +Z (opposite)
    }
    resolve = _make_resolver(points)
    face = [[0, 1, 2, 3], [4, 5, 6, 7]]
    area, nx, ny, nz = _face_area_and_normal(face, resolve)
    assert area == 96.0  # 100 - 4, not 100
    assert (nx, ny, nz) == (0.0, 0.0, 1.0)  # normal direction unaffected by the hole


def test_face_area_and_normal_ignoring_holes_would_overcount():
    """Sanity check on the test fixture itself: outer-ring-only (the old,
    buggy behavior) really would have reported 100, not 96 -- confirms
    the hole fixture above actually exercises the fix, not a no-op."""
    points = {0: (0, 0, 0), 1: (10, 0, 0), 2: (10, 10, 0), 3: (0, 10, 0)}
    resolve = _make_resolver(points)
    outer_only_area, _, _, _ = _face_area_and_normal([[0, 1, 2, 3]], resolve)
    assert outer_only_area == 100.0


# ── _estimate_storeys ─────────────────────────────────────────────────────


def test_estimate_storeys_prefers_b3_bouwlagen_when_present():
    assert _estimate_storeys({"b3_bouwlagen": 3}) == 3
    assert _estimate_storeys({"b3_bouwlagen": 0}) == 1  # floored at 1, never 0


def test_estimate_storeys_falls_back_to_height_when_bouwlagen_missing():
    # 8.4m above ground / 2.8m per storey = 3 storeys
    attrs = {"b3_bouwlagen": None, "b3_h_dak_50p": 88.4, "b3_h_maaiveld": 80.0}
    assert _estimate_storeys(attrs) == 3


def test_estimate_storeys_defaults_to_one_with_no_signal_at_all():
    assert _estimate_storeys({}) == 1


# ── _encode_point_ewkb: round-trips with geometry_utils' own decoder ────


def test_encode_point_ewkb_round_trips_through_geometry_utils_decoder():
    x, y = 197985.2464459839, 458590.46497011126  # a real Loenen RD-New coordinate
    hexgeom = _encode_point_ewkb(x, y)
    lat, lon = wkb_point_to_lat_lon(hexgeom)
    # Loenen, Gelderland -- same sanity bounds test_netherlands_data_source.py uses
    assert 51.5 < lat < 53.0
    assert 5.0 < lon < 7.0


def test_encode_point_ewkb_byte_layout():
    hexgeom = _encode_point_ewkb(1.5, 2.5, srid=28992)
    raw = bytes.fromhex(hexgeom)
    assert raw[0] == 1  # little-endian
    type_and_flags = struct.unpack("<I", raw[1:5])[0]
    assert type_and_flags & 0xFFFF == 1  # POINT
    assert type_and_flags & 0x20000000  # SRID flag set
    srid = struct.unpack("<I", raw[5:9])[0]
    assert srid == 28992
    x, y = struct.unpack("<dd", raw[9:25])
    assert (x, y) == (1.5, 2.5)


# ── detect_party_walls: coincidence matching on synthetic geometry ──────


def _wall_face(pand_id: str, p1: tuple[float, float], p2: tuple[float, float]) -> _RawFace:
    f = _RawFace(pand_id, 709, "WallSurface", area=1.0, tilt=90.0, azimuth=0.0, height=3.0, seg=(p1, p2))
    return f


def test_detect_party_walls_matches_touching_segments_across_buildings():
    """Two buildings share a wall along x=10, y in [0, 5] -- must be
    matched (same surface_feature_id on both sides)."""
    shared_a = _wall_face("A", (10.0, 0.0), (10.0, 5.0))
    shared_b = _wall_face("B", (10.0, 0.0), (10.0, 5.0))
    exposed_a = _wall_face("A", (0.0, 0.0), (0.0, 5.0))
    faces = {"A": [shared_a, exposed_a], "B": [shared_b]}

    detect_party_walls(faces)

    assert shared_a.surface_feature_id == shared_b.surface_feature_id
    assert exposed_a.surface_feature_id != shared_a.surface_feature_id
    # every face gets an id, none left unassigned
    assert all(f.surface_feature_id is not None for bldg in faces.values() for f in bldg)


def test_detect_party_walls_does_not_match_collinear_but_non_overlapping_segments():
    """Two buildings' walls sit on the same infinite line (x=10) but at
    disjoint y-ranges -- collinear is not enough, they must not match
    (this is exactly the real false-candidate pattern found calibrating
    against a real touching pair, see module docstring: 0-7% overlap)."""
    a = _wall_face("A", (10.0, 0.0), (10.0, 5.0))
    b = _wall_face("B", (10.0, 20.0), (10.0, 25.0))
    faces = {"A": [a], "B": [b]}

    detect_party_walls(faces)

    assert a.surface_feature_id != b.surface_feature_id


def test_detect_party_walls_does_not_match_walls_too_far_apart():
    a = _wall_face("A", (0.0, 0.0), (0.0, 5.0))
    b = _wall_face("B", (100.0, 0.0), (100.0, 5.0))
    faces = {"A": [a], "B": [b]}

    detect_party_walls(faces)

    assert a.surface_feature_id != b.surface_feature_id
