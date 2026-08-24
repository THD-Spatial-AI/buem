"""
Envelope element factory — creates windows, doors, and ventilation elements.

Extracted from ``lod2_mapper.py`` to keep the mapper focused on orchestration.
Each factory function receives pre-classified wall information and TABULA
parameters, and returns ready-to-use ``EnvelopeElement`` instances.

``WallInfo``, ``identify_front_back``, and ``synthesize_openings`` here are
source-agnostic: they operate on plain wall geometry (area/azimuth/
is_shared), not on a pandas DataFrame or a specific TABULA row. This is what
lets :func:`synthesize_openings` serve both :class:`~buem.buildings.mapping.
lod2_mapper.LOD2Mapper` (real per-building LOD2 + TABULA data, the offline
Excel/PostgreSQL batch pipeline) and the live request-handling path
(:mod:`buem.buildings.mapping.live_synthesis`, wall geometry from an
EnerPlanET API request or buem's own config, no attached LOD2 surface
table) — see ``docs/source/modules/buildings.rst`` for the documented
sizing rules both paths implement identically.

Ventilation opening sizes
-------------------------
.. data:: VENT_AREA_FRONT
   Front (entrance) wall opening: 1.0 m² (capped at 10 % of wall area).

.. data:: VENT_AREA_BACK
   Back wall opening: 0.5 m² (capped at 10 % of wall area).
"""

from __future__ import annotations

from dataclasses import dataclass

from buem.buildings.components.base import EnvelopeElement
from buem.buildings.mapping.tabula_helpers import azimuth_diff, azimuth_to_direction
from buem.config.building_registry import DEFAULT_WINDOW_TO_WALL_RATIO

# ── shared wall-geometry record ──────────────────────────────────────────────

# Maximum acceptable angular deviation (°) between a candidate back wall and
# the ideal opposite azimuth.  Beyond this threshold no true back wall exists
# (all exposed surfaces face roughly the same way → no cross-ventilation).
_BACK_WALL_ANGLE_LIMIT = 90.0


@dataclass
class WallInfo:
    """Source-agnostic record for a single exterior/shared wall.

    Built by :class:`~buem.buildings.mapping.lod2_mapper.LOD2Mapper` from
    per-building LOD2 surfaces (party-wall status via cross-building
    ``surface_feature_id`` matching), and by
    :mod:`buem.buildings.mapping.live_synthesis` from a caller-supplied
    ``components.Walls.elements`` list (party-wall status inferred from each
    wall's own ``b_transmission == 0`` — see buildings.rst "Party (Shared)
    Walls").
    """

    wall_id: str
    surface_feature_id: int
    area: float
    azimuth: float
    is_shared: bool
    direction: str = ""       # cardinal direction (north/east/south/west)
    window_area: float = 0.0  # proportional window area placed on this wall
    door_area: float = 0.0    # proportional door area placed on this wall
    vent_area: float = 0.0    # ventilation opening area on this wall
    azimuth_known: bool = True
    """Whether ``azimuth`` reflects real data, vs. a fallback value (e.g.
    LOD2Mapper normalises a source database's negative/NaN "unknown
    orientation" sentinel to 0.0/north — see ``lod2_mapper._normalise_
    azimuth``). ``synthesize_openings()`` skips window/door placement on
    a wall with ``azimuth_known=False`` — a fabricated orientation
    shouldn't drive where solar-gain-relevant openings go, even though
    the wall still counts fully toward opaque envelope area/conductance.
    Ventilation openings are unaffected (not orientation-sensitive)."""

    @property
    def net_area(self) -> float:
        """Opaque wall area after subtracting windows, doors, and vent openings."""
        return max(0.0, self.area - self.window_area - self.door_area - self.vent_area)


def identify_front_back(
    exposed_walls: list[WallInfo],
) -> tuple[WallInfo | None, WallInfo | None]:
    """Identify the front wall (largest exposed) and the back wall (opposite).

    The front wall is the exposed wall with the largest area.
    The back wall is the exposed wall whose azimuth is closest to 180°
    from the front wall's azimuth (i.e. facing the opposite direction).
    If only one exposed wall exists, it serves as both front and back.

    Returns
    -------
    (front_wall, back_wall) — either may be ``None`` if no exposed walls.
    """
    if not exposed_walls:
        return None, None

    # Front wall = largest area among exposed walls
    front = max(exposed_walls, key=lambda w: w.area)

    if len(exposed_walls) == 1:
        return front, front

    # Back wall = closest to 180° opposite front azimuth, within threshold
    opposite_az = (front.azimuth + 180.0) % 360.0
    best_back: WallInfo | None = None
    best_delta = float("inf")
    for w in exposed_walls:
        if w.wall_id == front.wall_id:
            continue
        delta = abs(azimuth_diff(w.azimuth, opposite_az))
        if delta < best_delta:
            best_delta = delta
            best_back = w

    # Only accept the candidate if it is within the angular limit;
    # otherwise there is no true opposite wall for cross-ventilation.
    if best_delta > _BACK_WALL_ANGLE_LIMIT:
        best_back = None

    return front, best_back


# ── ventilation opening constants ────────────────────────────────────────────

VENT_AREA_FRONT = 1.0   # m² — larger opening on the front (entrance) wall
VENT_AREA_BACK = 0.5    # m² — smaller opening on the back wall
_VENT_CAP_RATIO = 0.10  # max fraction of wall area for ventilation opening

MIN_WALL_AREA_FOR_WINDOWS = 5.0  # m² — walls smaller than this do not receive windows


def uniform_window_ratios(ratio: float | None = None) -> dict[str, float]:
    """Window-to-wall ratios for :func:`synthesize_openings`, applying the
    same fraction to every compass direction.

    Each exposed wall receives ``ratio × its own area`` as glazing,
    inheriting that wall's real azimuth and tilt, so orientation follows
    the building's actual geometry. The only directionality in the
    envelope is therefore each surface's own azimuth and tilt -- there is
    no separate per-direction glazing rule to keep consistent with it.

    ``ratio`` of ``None`` resolves to
    ``building_registry.DEFAULT_WINDOW_TO_WALL_RATIO``. This is the single
    place that default is applied, so a caller-supplied value and the
    default cannot diverge. An out-of-range value raises rather than
    falling back to the default: silently substituting a different ratio
    than the caller asked for would model a building they did not
    describe.
    """
    resolved = DEFAULT_WINDOW_TO_WALL_RATIO if ratio is None else float(ratio)
    if not 0.0 <= resolved < 1.0:
        raise ValueError(
            f"window_to_wall_ratio must be in [0, 1), got {resolved}"
        )
    return {"north": resolved, "east": resolved, "south": resolved, "west": resolved}


def assign_vent_areas(
    front_wall: WallInfo | None,
    back_wall: WallInfo | None,
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
    exposed_walls: list[WallInfo],
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
    front_wall: WallInfo | None,
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
    front_wall: WallInfo | None,
    back_wall: WallInfo | None,
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


def synthesize_openings(
    exposed_walls: list[WallInfo],
    front_wall: WallInfo | None,
    back_wall: WallInfo | None,
    *,
    window_ratios: dict[str, float],
    door_ratio: float,
    window_U: float,
    window_g_gl: float,
    door_U: float,
    n_air_use: float,
    horizontal_window_area: float = 0.0,
) -> list[EnvelopeElement]:
    """Compute proportional window/door/ventilation areas and build elements.

    Single entry point for the documented Window/Door/Ventilation sizing
    rules (``docs/source/modules/buildings.rst``): applies the per-direction
    window ratio and door ratio to each wall, assigns ventilation opening
    areas, then builds the window/door/ventilation ``EnvelopeElement``
    list — identically for :class:`~buem.buildings.mapping.lod2_mapper.
    LOD2Mapper` (extracted from here, previously inline in
    ``LOD2Mapper.map_building``) and for
    :mod:`buem.buildings.mapping.live_synthesis`.

    Mutates each wall's ``direction``/``window_area``/``door_area``/
    ``vent_area`` in place (callers that also need the resulting opaque
    ``net_area`` — e.g. to shrink a wall element's area by its openings —
    read it off the same ``WallInfo`` objects afterwards).

    Parameters
    ----------
    window_ratios : dict
        ``{"north": ratio, "east": ratio, "south": ratio, "west": ratio}``,
        each ``A_Window_<Direction> / A_Wall_1`` (real TABULA) or a
        documented safe-default ratio.
    door_ratio : float
        ``A_Door_1 / A_Wall_1`` (real TABULA) or a documented safe default.
    horizontal_window_area : float
        Skylight/horizontal window area, independent of wall geometry
        (TABULA ``A_Window_Horizontal``). ``0`` when not available.
    """
    for w in exposed_walls:
        if not w.azimuth_known:
            # Don't let a fabricated orientation drive window placement --
            # the wall still counts fully as opaque envelope area/
            # conductance (unaffected by this), just gets no window.
            w.direction = "unknown"
            w.window_area = 0.0
            continue
        w.direction = azimuth_to_direction(w.azimuth)
        if w.area < MIN_WALL_AREA_FOR_WINDOWS:
            # Mirrors create_windows()'s own cutoff -- a wall too small to
            # receive a window element must not have window_area subtracted
            # from its net_area either (WallInfo.net_area below), or that
            # area vanishes from the envelope entirely: not opaque wall
            # (net_area shrank), not a window (create_windows() never
            # built one for it). Previously only create_windows() honored
            # this cutoff, so window_area survived into net_area regardless
            # -- fixed here so the two stay consistent.
            w.window_area = 0.0
        else:
            w.window_area = window_ratios.get(w.direction, 0.0) * w.area
    if front_wall is not None and front_wall.azimuth_known:
        front_wall.door_area = door_ratio * front_wall.area

    assign_vent_areas(front_wall, back_wall)

    elements: list[EnvelopeElement] = list(create_windows(exposed_walls, window_U, window_g_gl))

    if horizontal_window_area > 0:
        elements.append(EnvelopeElement(
            id="win_horizontal",
            element_type="window",
            area=horizontal_window_area,
            azimuth=0.0,
            tilt=0.0,
            U=window_U,
            g_gl=window_g_gl,
        ))

    door_elem = create_door(front_wall, door_U)
    if door_elem is not None:
        elements.append(door_elem)

    elements.extend(create_ventilation(front_wall, back_wall, n_air_use))

    return elements
