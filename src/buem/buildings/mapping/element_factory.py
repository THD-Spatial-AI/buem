"""
Envelope element factory — creates windows, doors, and ventilation elements.

Extracted from ``lod2_mapper.py`` to keep the mapper focused on orchestration.
Each factory function receives pre-classified wall information and TABULA
parameters, and returns ready-to-use ``EnvelopeElement`` instances.

Ventilation opening sizes
-------------------------
.. data:: VENT_AREA_FRONT
   Front (entrance) wall opening: 1.0 m² (capped at 10 % of wall area).

.. data:: VENT_AREA_BACK
   Back wall opening: 0.5 m² (capped at 10 % of wall area).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from buem.buildings.components.base import EnvelopeElement

if TYPE_CHECKING:
    from buem.buildings.mapping.lod2_mapper import _WallInfo

# ── ventilation opening constants ────────────────────────────────────────────

VENT_AREA_FRONT = 1.0   # m² — larger opening on the front (entrance) wall
VENT_AREA_BACK = 0.5    # m² — smaller opening on the back wall
_VENT_CAP_RATIO = 0.10  # max fraction of wall area for ventilation opening

MIN_WALL_AREA_FOR_WINDOWS = 5.0  # m² — walls smaller than this do not receive windows


def assign_vent_areas(
    front_wall: _WallInfo | None,
    back_wall: _WallInfo | None,
) -> None:
    """Assign ventilation opening areas to front and back walls in-place.

    Areas are capped at 10 % of wall area to avoid disproportionate openings
    on small walls.
    """
    if front_wall is not None:
        front_wall.vent_area = min(VENT_AREA_FRONT, front_wall.area * _VENT_CAP_RATIO)
    if (back_wall is not None
            and front_wall is not None
            and back_wall.wall_id != front_wall.wall_id):
        back_wall.vent_area = min(VENT_AREA_BACK, back_wall.area * _VENT_CAP_RATIO)


def create_windows(
    exposed_walls: list[_WallInfo],
    window_U: float,
    window_g_gl: float,
) -> list[EnvelopeElement]:
    """Create window elements from pre-computed proportional areas.

    Each exposed wall already has ``window_area`` set via the ratio
    ``A_Window_<Direction> / A_Wall_1 × LOD2_wall_area``.
    One window element is created per wall that has ``window_area > 0``.

    Walls smaller than ``MIN_WALL_AREA_FOR_WINDOWS`` (5 m²) are assumed to
    have no windows — small wall segments (gable fragments, narrow returns)
    rarely contain glazing in practice.

    Zero-area windows are also skipped — this catches floating-point
    artefacts from near-zero TABULA directional ratios (< 0.01 m²).

    Returns
    -------
    list of EnvelopeElement
        One window per exposed wall with meaningful window area.
    """
    windows: list[EnvelopeElement] = []
    for w in exposed_walls:
        if w.area < MIN_WALL_AREA_FOR_WINDOWS:
            continue
        if w.window_area < 0.01:
            continue
        windows.append(EnvelopeElement(
            id=f"win_{w.wall_id}",
            element_type="window",
            area=w.window_area,
            azimuth=w.azimuth,
            tilt=90.0,
            U=window_U,
            g_gl=window_g_gl,
            surface=w.wall_id,
        ))
    return windows


def create_door(
    front_wall: _WallInfo | None,
    door_U: float,
) -> EnvelopeElement | None:
    """Create a door element on the front wall.

    Returns ``None`` if there is no front wall or the door area is zero.
    """
    if front_wall is None or front_wall.door_area <= 0:
        return None
    return EnvelopeElement(
        id="door_1",
        element_type="door",
        area=front_wall.door_area,
        azimuth=front_wall.azimuth,
        tilt=90.0,
        U=door_U,
        b_transmission=1.0,
        surface=front_wall.wall_id,
    )


def create_ventilation(
    front_wall: _WallInfo | None,
    back_wall: _WallInfo | None,
    n_air_use: float,
) -> list[EnvelopeElement]:
    """Create ventilation elements on the front and back walls.

    Each element carries a physical opening area (already assigned to the
    wall via ``vent_area`` and subtracted from the wall's opaque
    ``net_area``), inherits the host wall's azimuth and tilt, and
    references the wall via ``surface`` (parent_id).

    - Two exposed walls → split air changes equally between front/back.
    - One exposed wall  → full air changes on the front wall.
    - No exposed walls  → infiltration-only placeholder (all party
      walls; purposeful ventilation requires mechanical systems).
    """
    if front_wall is None:
        # Fully enclosed by party walls — no natural ventilation openings.
        return [EnvelopeElement(
            id="vent_infiltration",
            element_type="ventilation",
            area=0.0,
            azimuth=0.0,
            tilt=0.0,
            air_changes=n_air_use,
        )]

    elements: list[EnvelopeElement] = []

    if back_wall is not None and back_wall.wall_id != front_wall.wall_id:
        # Cross-ventilation: split air changes equally
        half = n_air_use / 2.0
        elements.append(EnvelopeElement(
            id="vent_front",
            element_type="ventilation",
            area=front_wall.vent_area,
            azimuth=front_wall.azimuth,
            tilt=90.0,
            air_changes=half,
            surface=front_wall.wall_id,
        ))
        elements.append(EnvelopeElement(
            id="vent_back",
            element_type="ventilation",
            area=back_wall.vent_area,
            azimuth=back_wall.azimuth,
            tilt=90.0,
            air_changes=half,
            surface=back_wall.wall_id,
        ))
    else:
        # Single-sided ventilation: full air changes on front wall
        elements.append(EnvelopeElement(
            id="vent_front",
            element_type="ventilation",
            area=front_wall.vent_area,
            azimuth=front_wall.azimuth,
            tilt=90.0,
            air_changes=n_air_use,
            surface=front_wall.wall_id,
        ))

    return elements
