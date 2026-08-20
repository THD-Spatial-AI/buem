"""
CityJSON (3D BAG) -> lod2_building_feature.csv / lod2_child_feature_surface.csv
extractor -- a clean, single-pass replacement for city2tabula's LOD2 geometry
export.

Why this exists
----------------
The city2tabula-derived Netherlands/Loenen export
(``src/buem/data/buildings/netherlands/Loenen/``) was found to carry TWO
independent, compounding duplication bugs (see ``.claude/residential/
resolved.md`` and ``open.md``, 2026-08-15/16): exact-duplicate export rows
(fixed in ``csv_source.py``), and a second "near-identical batch" layer
where the whole per-building extraction appears to have run twice under
sequential ``surface_feature_id`` blocks (not fixed -- not safely
automatable from the export alone). Both were only found by cross-checking
against the real CityJSON (3D BAG) source. This module goes one step
further: extract geometry **directly** from that CityJSON source, so buem
no longer depends on city2tabula's pipeline for Netherlands geometry at
all -- "difficult to control a pipeline within city2tabula which is not
created by [the user]" (verbatim, 2026-08-16).

Scope -- geometry only, deliberately
-------------------------------------
This module produces real wall/roof/floor geometry (area/tilt/azimuth),
building-level aggregates, real party-wall detection, and a real
lat/lon-capable centroid. It does **not** attempt TABULA archetype
matching (``tabula_variant_code_id`` is left null on every row) -- that is
a separate, explicitly deferred discussion (2026-08-16: "Finish the
regeneration first and then discuss how and where to map to get
appropriate U values"). A building extracted here cannot be run through
``LOD2Mapper`` until that follow-up lands (``get_tabula_row`` will return
``None`` for every row).

Geometry conventions (validated against real 3D BAG data before writing
this module -- see the 2026-08-16 session, not asserted blind)
-------------------------------------------------------------------------
- CityJSON LOD2.2 ``Solid`` geometry gives each real physical surface as
  its own already-planar face -- unlike city2tabula's export, there is no
  fragmentation step here and therefore nothing to accidentally duplicate.
  One face = one output row, always ``is_valid=True``/``is_planar=True``.
- Face area/normal via Newell's method (already used elsewhere in this
  codebase for the same CityJSON cross-check, see
  ``.claude/residential/resolved.md``).
- ``azimuth = atan2(nx, ny) % 360`` (nx, ny = horizontal normal
  components) and ``tilt = degrees(acos(nz / |n|))`` (nz = vertical
  normal component) were checked against 3D BAG's own ``b3_azimut``/
  ``b3_hellingshoek`` roof attributes on real buildings and matched
  exactly (e.g. 307.89328 vs. computed 307.9, 8.22113 vs. 8.2) --
  confirms both the outward-normal orientation convention (exterior
  shells wind so Newell's method already points outward: a GroundSurface
  normal was confirmed pointing straight down, nz=-1, a RoofSurface
  mostly up) and the exact azimuth/tilt formula, before trusting it for
  walls (which 3D BAG does not publish an azimuth for directly).
- Matches ``lod2_mapper.py``'s existing convention for Ground/Wall/Roof:
  GroundSurface is always written as tilt=0/azimuth=0 (not the geometric
  downward-normal value) and WallSurface tilt is always 90 -- these are
  buem's own modeling simplification, not something to derive per-row.

Party-wall detection (2026-08-16, geometric coincidence)
----------------------------------------------------------
CityJSON gives each building its own self-contained solid -- there is no
shared ID between two adjacent buildings' touching wall faces the way
city2tabula's ``surface_feature_id`` matching relied on. A real
alternative signal was checked and rejected first: 3D BAG's own
``on_footprint_edge`` wall-semantic attribute does **not** correlate with
the shared boundary between two confirmed-touching buildings (checked
against a real adjacent pair, ``…0021335``/``…0021333`` -- the
``on_footprint_edge=False`` faces sit away from the shared edge, not on
it; it flags something else, most likely non-perimeter segments from a
non-convex footprint).

Real geometric coincidence detection instead: every wall face's vertices
project onto a single 2D line (it is a vertical planar polygon), so two
wall faces from *different* buildings are the same physical party wall
when their 2D line segments are (a) nearly collinear (perpendicular
distance from one segment's endpoints to the other's line < 0.3 m -- real
matches measured 0.0002-0.09 m against a known pair, spurious near-misses
0.03-0.1 m, so 0.3 m keeps a comfortable margin) and (b) substantially
overlapping (>= 50% of the shorter segment's length -- real matches
measured 93-100% overlap, spurious collinear-but-non-touching segments
measured 0-7%, again a wide margin). Matching is greedy (highest-overlap
pairs first, each face consumed at most once) and restricted to buildings
in the same/adjacent 20 m grid cell for performance. **Known
simplification**: if a single wall face genuinely touches two different
neighbouring segments (a footprint step along the shared boundary), only
its single best-overlap match is recorded -- the rarer partial-touch case
is treated as fully exposed rather than split. Verified against the same
known pair before running dataset-wide: found exactly the 4 wall pairs a
manual read of their footprints predicts, all >= 93% overlap, with every
false-candidate cleanly separated by the 50% threshold.

A matched pair is written with the **same** ``surface_feature_id`` under
each of the two buildings -- this reuses ``wall_classifier
.SharedWallDetector``'s existing "appears under >=2 building_feature_id"
rule unchanged; ``LOD2Mapper`` needs no changes to consume this output.

Storeys (2026-08-16, user-confirmed approach)
------------------------------------------------
3D BAG's ``b3_bouwlagen`` (storey count) is only populated for buildings
with an estimated <=5 floors (its own documented scope, see
https://docs.3dbag.nl/en/schema/attributes/) -- ~42% of Loenen buildings
in this export. Per the user (2026-08-16, citing a Loenen-community
confirmation that <1% of local buildings exceed 5 floors): use it
directly when present; for the rest, estimate
``round((b3_h_dak_50p - b3_h_maaiveld) / STOREY_HEIGHT_M)``, floored at 1
storey. This is a modeling estimate, not measured data, for the ~58%
missing.
"""

from __future__ import annotations

import json
import logging
import math
import struct
import uuid
from collections import defaultdict
from pathlib import Path
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)

# ── schema constants (match the existing city2tabula-shaped schema) ─────────
OBJECTCLASS_WALL = 709
OBJECTCLASS_GROUND = 710
OBJECTCLASS_ROOF = 712
_CLASSNAME_BY_OBJECTCLASS = {
    OBJECTCLASS_WALL: "WallSurface",
    OBJECTCLASS_GROUND: "GroundSurface",
    OBJECTCLASS_ROOF: "RoofSurface",
}
_OBJECTCLASS_BY_CITYJSON_TYPE = {
    "WallSurface": OBJECTCLASS_WALL,
    "GroundSurface": OBJECTCLASS_GROUND,
    "RoofSurface": OBJECTCLASS_ROOF,
}

_RD_NEW_SRID = 28992  # Amersfoort / RD New -- matches geometry_utils.py

# ── party-wall coincidence-matching tolerances (calibrated against a real
#    known-touching building pair, see module docstring) ────────────────────
PARTY_WALL_PERP_TOLERANCE_M = 0.3
PARTY_WALL_MIN_OVERLAP_FRACTION = 0.5
_ADJACENCY_GRID_CELL_M = 20.0

# ── storeys estimate (user-confirmed 2026-08-16) ─────────────────────────────
STOREY_HEIGHT_M = 2.8


# ── geometry primitives ──────────────────────────────────────────────────────


def _load_cityjson(path: str | Path) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


class _VertexResolver:
    """Applies a CityJSON ``transform`` (scale + translate) to vertex indices."""

    def __init__(self, cj: dict[str, Any]):
        self._verts = cj["vertices"]
        self._scale = cj["transform"]["scale"]
        self._translate = cj["transform"]["translate"]

    def __call__(self, idx: int) -> tuple[float, float, float]:
        vx, vy, vz = self._verts[idx]
        return (
            vx * self._scale[0] + self._translate[0],
            vy * self._scale[1] + self._translate[1],
            vz * self._scale[2] + self._translate[2],
        )


def _ring_newell_vector(ring: list[int], resolve) -> tuple[float, float, float]:
    """Newell's method for one ring: the *un-normalized* (nx, ny, nz),
    magnitude = twice the ring's own planar area, direction = its own
    winding-determined normal. Not yet a final area/normal on its own --
    see _face_area_and_normal for why this is summed across rings first.
    """
    pts = [resolve(i) for i in ring]
    n = len(pts)
    nx = ny = nz = 0.0
    for i in range(n):
        x1, y1, z1 = pts[i]
        x2, y2, z2 = pts[(i + 1) % n]
        nx += (y1 - y2) * (z1 + z2)
        ny += (z1 - z2) * (x1 + x2)
        nz += (x1 - x2) * (y1 + y2)
    return nx / 2, ny / 2, nz / 2


def _face_area_and_normal(face: list[list[int]], resolve) -> tuple[float, float, float, float]:
    """Newell's method over a full face (outer ring + any holes): returns
    (area, unit_nx, unit_ny, unit_nz).

    CityJSON's own convention (confirmed against real Loenen faces before
    trusting it, 2026-08-17 -- 128 buildings/144 faces in this dataset
    actually have holes, e.g. courtyards/light-wells, not a theoretical
    case): ``face[0]`` is the exterior ring, ``face[1:]`` are interior
    rings (holes), wound in the *opposite* direction. Summing each ring's
    raw (un-normalized) Newell vector before taking the magnitude lets a
    hole's oppositely-signed contribution subtract naturally -- verified
    on real multi-ring faces here: every hole ring's vector had a strongly
    negative dot product against the outer ring's (i.e. genuinely
    opposite-facing, not a same-direction second boundary), and the net
    area after summing dropped by 6% in aggregate across the affected
    faces (up to ~37% for one individual face) versus reading only
    ``face[0]`` -- the bug this replaced.
    """
    nx = ny = nz = 0.0
    for ring in face:
        rnx, rny, rnz = _ring_newell_vector(ring, resolve)
        nx += rnx
        ny += rny
        nz += rnz
    norm = math.sqrt(nx * nx + ny * ny + nz * nz)
    area = norm
    if norm < 1e-9:
        return 0.0, 0.0, 0.0, 1.0
    return area, nx / norm, ny / norm, nz / norm


def _wall_2d_segment(ring: list[int], resolve) -> tuple[tuple[float, float], tuple[float, float]]:
    """A vertical wall's vertices all project onto one 2D line -- return the
    two points of maximum 2D separation as that line's segment endpoints."""
    pts2d = [(p[0], p[1]) for p in (resolve(i) for i in ring)]
    best = (pts2d[0], pts2d[0], -1.0)
    for i in range(len(pts2d)):
        for j in range(i + 1, len(pts2d)):
            d = math.hypot(pts2d[i][0] - pts2d[j][0], pts2d[i][1] - pts2d[j][1])
            if d > best[2]:
                best = (pts2d[i], pts2d[j], d)
    return best[0], best[1]


def _z_extent(ring: list[int], resolve) -> float:
    zs = [resolve(i)[2] for i in ring]
    return max(zs) - min(zs)


# ── per-building face extraction ─────────────────────────────────────────────


class _RawFace:
    __slots__ = (
        "area",
        "azimuth",
        "classname",
        "height",
        "objectclass_id",
        "pand_id",
        "seg",
        "surface_feature_id",
        "tilt",
    )

    def __init__(self, pand_id, objectclass_id, classname, area, tilt, azimuth, height, seg):
        self.pand_id = pand_id
        self.objectclass_id = objectclass_id
        self.classname = classname
        self.area = area
        self.tilt = tilt
        self.azimuth = azimuth
        self.height = height
        self.seg = seg  # (p1, p2) 2D segment, only meaningful for walls
        self.surface_feature_id: int | None = None  # assigned later


def _best_geometry(child: dict[str, Any]) -> dict[str, Any] | None:
    geoms = {g["lod"]: g for g in child.get("geometry", [])}
    if "2.2" in geoms:
        return geoms["2.2"]
    if not geoms:
        return None
    # fall back to the highest numeric LOD available
    return geoms[max(geoms.keys(), key=float)]


def _extract_faces_for_building(
    pand_id: str, building_obj: dict[str, Any], cos: dict[str, Any], resolve,
) -> list[_RawFace]:
    faces: list[_RawFace] = []
    for child_id in building_obj.get("children", []):
        child = cos.get(child_id)
        if child is None or child.get("type") != "BuildingPart":
            continue
        g = _best_geometry(child)
        if g is None or g.get("type") != "Solid":
            continue
        sem = g.get("semantics")
        if not sem:
            continue
        surf_defs = sem["surfaces"]
        for shell_i, shell in enumerate(g["boundaries"]):
            val_shell = sem["values"][shell_i]
            for face_i, face in enumerate(shell):
                vidx = val_shell[face_i]
                if vidx is None:
                    continue
                cj_type = surf_defs[vidx].get("type")
                objectclass_id = _OBJECTCLASS_BY_CITYJSON_TYPE.get(cj_type)
                if objectclass_id is None:
                    continue  # e.g. OuterCeilingSurface/ClosureSurface -- not modeled
                ring = face[0]  # exterior ring -- sufficient for span/z-extent below
                area, nx, ny, nz = _face_area_and_normal(face, resolve)  # all rings -- see docstring
                if area < 0.01:
                    continue  # geometry artefact, matches LOD2Mapper's own 0.01 m2 floor
                height = _z_extent(ring, resolve)
                seg = None
                if objectclass_id == OBJECTCLASS_GROUND:
                    tilt, azimuth = 0.0, 0.0
                elif objectclass_id == OBJECTCLASS_WALL:
                    tilt, azimuth = 90.0, math.degrees(math.atan2(nx, ny)) % 360.0
                    seg = _wall_2d_segment(ring, resolve)
                else:  # roof
                    tilt = math.degrees(math.acos(max(-1.0, min(1.0, nz))))
                    azimuth = math.degrees(math.atan2(nx, ny)) % 360.0
                faces.append(_RawFace(
                    pand_id, objectclass_id, _CLASSNAME_BY_OBJECTCLASS[objectclass_id],
                    area, tilt, azimuth, height, seg,
                ))
    return faces


# ── party-wall coincidence detection ─────────────────────────────────────────


def _seg_perp_dist_and_overlap(p1a, p2a, p1b, p2b) -> tuple[float, float, float] | None:
    """Returns (avg_perp_dist, overlap_length, wall_len_a), or None if
    either segment is degenerate."""
    ax, ay = p2a[0] - p1a[0], p2a[1] - p1a[1]
    la = math.hypot(ax, ay)
    bx, by = p2b[0] - p1b[0], p2b[1] - p1b[1]
    lb = math.hypot(bx, by)
    if la < 1e-6 or lb < 1e-6:
        return None
    ux, uy = ax / la, ay / la

    def perp_dist(p):
        vx, vy = p[0] - p1a[0], p[1] - p1a[1]
        return abs(vx * uy - vy * ux)

    def proj(p):
        vx, vy = p[0] - p1a[0], p[1] - p1a[1]
        return vx * ux + vy * uy

    avg_dist = (perp_dist(p1b) + perp_dist(p2b)) / 2
    ta1, ta2 = proj(p1b), proj(p2b)
    lo, hi = min(ta1, ta2), max(ta1, ta2)
    overlap = max(0.0, min(hi, la) - max(lo, 0.0))
    return avg_dist, overlap, la


def detect_party_walls(faces_by_building: dict[str, list[_RawFace]]) -> None:
    """Greedy geometric coincidence matching between wall faces of nearby
    buildings. Mutates each matched pair's ``surface_feature_id`` in place
    to the same shared value; assigns a unique value to every other
    surface (wall, roof, or floor). See module docstring for the
    calibration this threshold pair is based on.
    """
    # bucket buildings by a coarse grid cell over all their wall segment endpoints
    grid: dict[tuple[int, int], list[str]] = defaultdict(list)
    bbox: dict[str, tuple[float, float, float, float]] = {}
    for pid, faces in faces_by_building.items():
        pts = [pt for f in faces if f.seg for pt in f.seg]
        if not pts:
            continue
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        bbox[pid] = (min(xs), min(ys), max(xs), max(ys))
        cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
        grid[(int(cx // _ADJACENCY_GRID_CELL_M), int(cy // _ADJACENCY_GRID_CELL_M))].append(pid)

    candidates: list[tuple[float, str, int, str, int]] = []  # (overlap, pid_a, idx_a, pid_b, idx_b)
    checked_pairs: set[frozenset[str]] = set()
    for (gx, gy), pids in grid.items():
        neighbours: list[str] = []
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                neighbours.extend(grid.get((gx + dx, gy + dy), []))
        for pid_a in pids:
            for pid_b in neighbours:
                if pid_a >= pid_b:
                    continue
                key = frozenset((pid_a, pid_b))
                if key in checked_pairs:
                    continue
                checked_pairs.add(key)
                a1, a2, a3, a4 = bbox[pid_a]
                b1, b2, b3, b4 = bbox[pid_b]
                if max(a1 - b3, b1 - a3, a2 - b4, b2 - a4) > 2.0:
                    continue  # too far apart to plausibly touch
                walls_a = [(i, f) for i, f in enumerate(faces_by_building[pid_a]) if f.seg]
                walls_b = [(i, f) for i, f in enumerate(faces_by_building[pid_b]) if f.seg]
                for ia, fa in walls_a:
                    for ib, fb in walls_b:
                        r = _seg_perp_dist_and_overlap(fa.seg[0], fa.seg[1], fb.seg[0], fb.seg[1])
                        if r is None:
                            continue
                        avg_dist, overlap, len_a = r
                        if avg_dist > PARTY_WALL_PERP_TOLERANCE_M:
                            continue
                        min_len = min(len_a, math.hypot(
                            fb.seg[1][0] - fb.seg[0][0], fb.seg[1][1] - fb.seg[0][1],
                        ))
                        if min_len < 1e-6 or overlap / min_len < PARTY_WALL_MIN_OVERLAP_FRACTION:
                            continue
                        candidates.append((overlap, pid_a, ia, pid_b, ib))

    candidates.sort(key=lambda c: -c[0])
    matched_faces: set[tuple[str, int]] = set()
    n_matched_pairs = 0
    counter = 1

    def next_sfid():
        nonlocal counter
        counter += 1
        return counter

    for overlap, pid_a, ia, pid_b, ib in candidates:
        if (pid_a, ia) in matched_faces or (pid_b, ib) in matched_faces:
            continue
        sfid = next_sfid()
        faces_by_building[pid_a][ia].surface_feature_id = sfid
        faces_by_building[pid_b][ib].surface_feature_id = sfid
        matched_faces.add((pid_a, ia))
        matched_faces.add((pid_b, ib))
        n_matched_pairs += 1

    # assign a unique surface_feature_id to every remaining (unmatched) face
    for pid, faces in faces_by_building.items():
        for i, f in enumerate(faces):
            if f.surface_feature_id is None:
                f.surface_feature_id = next_sfid()

    logger.info("detect_party_walls: %d party-wall pairs matched (%d candidate pairs considered)",
                n_matched_pairs, len(candidates))


# ── storeys + centroid ────────────────────────────────────────────────────────


def _estimate_storeys(attrs: dict[str, Any]) -> int:
    bouwlagen = attrs.get("b3_bouwlagen")
    if bouwlagen is not None:
        return max(1, round(bouwlagen))
    h_top, h_ground = attrs.get("b3_h_dak_50p"), attrs.get("b3_h_maaiveld")
    if h_top is not None and h_ground is not None:
        return max(1, round((h_top - h_ground) / STOREY_HEIGHT_M))
    return 1


def _encode_point_ewkb(x: float, y: float, srid: int = _RD_NEW_SRID) -> str:
    """Inverse of geometry_utils.wkb_point_to_lat_lon -- encodes a 2D point
    as little-endian hex EWKB with an explicit SRID, matching the exact
    byte layout that module decodes (type=1/POINT, SRID flag set)."""
    parts = [
        struct.pack("<B", 1),               # little-endian
        struct.pack("<I", 0x20000001),      # POINT (1) | SRID flag
        struct.pack("<I", srid),
        struct.pack("<dd", x, y),
    ]
    return b"".join(parts).hex()


# ── top-level extraction ─────────────────────────────────────────────────────


def extract(cityjson_path: str | Path, limit: int | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Extract (buildings_df, surfaces_df) directly from a CityJSON export.

    Column-compatible with the existing ``lod2_building_feature.csv``/
    ``lod2_child_feature_surface.csv`` shape (``CsvBuildingSource`` reads
    either unchanged) -- with ``tabula_variant_code_id`` left null on
    every row (TABULA matching is a deliberately separate follow-up, see
    module docstring).
    """
    cj = _load_cityjson(cityjson_path)
    cos = cj["CityObjects"]
    resolve = _VertexResolver(cj)

    pand_ids = sorted(oid for oid, o in cos.items() if o["type"] == "Building")
    if limit is not None:
        pand_ids = pand_ids[:limit]

    faces_by_building: dict[str, list[_RawFace]] = {}
    for pid in pand_ids:
        faces_by_building[pid] = _extract_faces_for_building(pid, cos[pid], cos, resolve)

    detect_party_walls(faces_by_building)

    # surface_feature_id -> set of building pand_ids it appears under --
    # built once (O(total faces)) rather than per-building, so checking
    # "does this wall's sfid appear under a different building" below is
    # an O(1) lookup instead of rebuilding a cross-building set 3,000+
    # times over.
    sfid_to_pids: dict[int | None, set[str]] = defaultdict(set)
    for pid_, faces_ in faces_by_building.items():
        for f_ in faces_:
            sfid_to_pids[f_.surface_feature_id].add(pid_)

    building_rows = []
    surface_rows = []
    for bldg_idx, pid in enumerate(pand_ids, start=1):
        faces = faces_by_building[pid]
        if not faces:
            continue
        attrs = cos[pid]["attributes"]

        wall_faces = [f for f in faces if f.objectclass_id == OBJECTCLASS_WALL]
        roof_faces = [f for f in faces if f.objectclass_id == OBJECTCLASS_ROOF]
        floor_faces = [f for f in faces if f.objectclass_id == OBJECTCLASS_GROUND]

        for f in faces:
            row_id = str(uuid.uuid4())
            surface_rows.append({
                "id": row_id,
                "building_feature_id": bldg_idx,
                "surface_feature_id": f.surface_feature_id,
                "objectclass_id": f.objectclass_id,
                "classname": f.classname,
                "height": round(f.height, 6),
                "height_unit": "m",
                "surface_area": round(f.area, 8),
                "surface_area_unit": "sqm",
                "tilt": round(f.tilt, 4),
                "tilt_unit": "degrees",
                "azimuth": round(f.azimuth, 4),
                "azimuth_unit": "degrees",
                "is_valid": True,
                "is_planar": True,
                "child_row_id": row_id,
                "attribute_calc_status": "cityjson_extractor_v1",
                "geom": "",
            })

        # footprint centroid from ground-face vertices (area-weighted 2D centroid)
        ground_pts: list[tuple[float, float]] = []
        for child_id in cos[pid].get("children", []):
            child = cos.get(child_id, {})
            g = _best_geometry(child) if child else None
            if not g:
                continue
            sem = g.get("semantics")
            if not sem:
                continue
            for shell_i, shell in enumerate(g["boundaries"]):
                val_shell = sem["values"][shell_i]
                for face_i, face in enumerate(shell):
                    vidx = val_shell[face_i]
                    if vidx is None or sem["surfaces"][vidx].get("type") != "GroundSurface":
                        continue
                    ground_pts.extend((resolve(i)[0], resolve(i)[1]) for i in face[0])
        cx: float | None
        cy: float | None
        if ground_pts:
            cx = sum(p[0] for p in ground_pts) / len(ground_pts)
            cy = sum(p[1] for p in ground_pts) / len(ground_pts)
        else:
            ext = cos[pid].get("geographicalExtent")
            cx, cy = ((ext[0] + ext[3]) / 2, (ext[1] + ext[4]) / 2) if ext else (None, None)

        n_storeys = _estimate_storeys(attrs)
        area_wall = sum(f.area for f in wall_faces)
        area_roof = sum(f.area for f in roof_faces)
        area_floor = sum(f.area for f in floor_faces)

        neighbour_pids = {
            opid
            for f in wall_faces
            for opid in sfid_to_pids[f.surface_feature_id]
            if opid != pid
        }

        building_rows.append({
            "id": str(uuid.uuid4()),
            "building_feature_id": bldg_idx,
            "bag_pand_id": pid,
            "tabula_variant_code_id": None,   # deliberately deferred -- see module docstring
            "tabula_variant_code": None,
            "construction_year": attrs.get("oorspronkelijkbouwjaar"),
            "comment": "cityjson_extractor_v1",
            "heating_demand": None,
            "heating_demand_unit": None,
            "footprint_area": round(area_floor, 6),
            "footprint_complexity": None,
            "roof_complexity": len(roof_faces),
            "has_attached_neighbour": len(neighbour_pids) > 0,
            "total_attached_neighbour": len(neighbour_pids),
            "attached_neighbour_id": ";".join(sorted(neighbour_pids)) or None,
            "attached_neighbour_class": None,
            "is_greenhouse_or_warehouse": bool(attrs.get("b3_kas_warenhuis")),
            "is_glass_roof": bool(attrs.get("b3_is_glas_dak")),
            "min_height": attrs.get("b3_h_dak_min"),
            "min_height_unit": "m",
            "max_height": attrs.get("b3_h_dak_max"),
            "max_height_unit": "m",
            "room_height": None,
            "room_height_unit": "m",
            "number_of_storeys": n_storeys,
            "min_volume": attrs.get("b3_volume_lod22"),
            "min_volume_unit": "cbm",
            "max_volume": attrs.get("b3_volume_lod22"),
            "max_volume_unit": "cbm",
            "area_total_roof": round(area_roof, 6),
            "area_total_roof_unit": "sqm",
            "area_total_wall": round(area_wall, 6),
            "area_total_wall_unit": "sqm",
            "area_total_floor": round(area_floor, 6),
            "area_total_floor_unit": "sqm",
            "surface_count_floor": len(floor_faces),
            "surface_count_roof": len(roof_faces),
            "surface_count_wall": len(wall_faces),
            "building_centroid_geom": _encode_point_ewkb(cx, cy) if cx is not None and cy is not None else None,
            "building_footprint_geom": None,
        })

    buildings_df = pd.DataFrame(building_rows)
    surfaces_df = pd.DataFrame(surface_rows)
    logger.info(
        "extract: %d buildings, %d surfaces (%d walls / %d roofs / %d floors)",
        len(buildings_df), len(surfaces_df),
        (surfaces_df["objectclass_id"] == OBJECTCLASS_WALL).sum(),
        (surfaces_df["objectclass_id"] == OBJECTCLASS_ROOF).sum(),
        (surfaces_df["objectclass_id"] == OBJECTCLASS_GROUND).sum(),
    )
    return buildings_df, surfaces_df


def write_csvs(buildings_df: pd.DataFrame, surfaces_df: pd.DataFrame, output_dir: str | Path) -> None:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    buildings_df.to_csv(output_dir / "lod2_building_feature.csv", index=False)
    surfaces_df.to_csv(output_dir / "lod2_child_feature_surface.csv", index=False)
    logger.info("write_csvs: wrote lod2_building_feature.csv / lod2_child_feature_surface.csv to %s", output_dir)


__all__ = ["detect_party_walls", "extract", "write_csvs"]


def main() -> None:
    """CLI entry point: ``python -m buem.buildings.datasources.cityjson_extractor``.

    Regenerates ``lod2_building_feature.csv``/``lod2_child_feature_surface
    .csv`` from a CityJSON source. Re-run this whenever the source
    CityJSON changes (a newer 3D BAG export, a different region) --
    it is deterministic (buildings sorted by BAG pand id) so the same
    input always reproduces the same ``building_feature_id`` assignment.
    """
    import argparse
    import time

    parser = argparse.ArgumentParser(
        description="Extract clean LOD2 building geometry directly from a CityJSON (3D BAG) source.",
    )
    parser.add_argument("cityjson_path", type=str, help="Path to the source .city.json file")
    parser.add_argument(
        "--output", type=str, required=True,
        help="Output directory for lod2_building_feature.csv / lod2_child_feature_surface.csv",
    )
    parser.add_argument("--limit", type=int, default=None, help="Limit to the first N buildings (for smoke-testing)")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
        datefmt="%H:%M:%S",
    )
    t0 = time.perf_counter()
    buildings_df, surfaces_df = extract(args.cityjson_path, limit=args.limit)
    write_csvs(buildings_df, surfaces_df, args.output)
    logger.info("Done in %.1fs", time.perf_counter() - t0)


if __name__ == "__main__":
    main()
