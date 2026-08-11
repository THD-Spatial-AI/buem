"""
Live-path LOD2 → LOD3 envelope synthesis.

Bridges the documented, TABULA-ratio-based window/door/ventilation sizing
logic in :mod:`element_factory`/:mod:`tabula_helpers` (originally written
for :class:`~buem.buildings.mapping.lod2_mapper.LOD2Mapper`'s offline
Excel/PostgreSQL batch pipeline) to the live request-handling path
(:class:`buem.config.cfg_building.CfgBuilding`), which receives wall
geometry from an EnerPlanET API request, buem's own module-level config
default, or a caller-supplied ``components`` dict directly -- with no
attached LOD2 surface table to detect party walls or a numeric FK to
resolve a TABULA row.

EnerPlanET's own UI deliberately doesn't ask general users to fill in
window/door/ventilation detail (see ``CLAUDE.md``): a request may supply
these explicitly, but when it doesn't, buem must compute them internally
from whatever wall geometry it does have, using the same rules documented
in ``docs/source/modules/buildings.rst`` -- not silently leave them empty.
This module is that internal computation for the live path:

- "Shared wall" detection falls back to each wall's own ``b_transmission``
  (``0`` → party wall) instead of cross-building ``surface_feature_id``
  matching, which needs a full LOD2 surface table this path doesn't have
  (see buildings.rst "Party (Shared) Walls").
- The TABULA archetype is resolved from ``building_type`` +
  ``construction_period`` + ``country`` (already forwarded end-to-end from
  a real v3 API request, see ``CLAUDE.md`` "v2 vs v3/v4 request formats")
  or an explicit ``bldg_tabula_id``, via
  :func:`tabula_helpers.lookup_tabula_archetype`, falling back to
  documented safe-default ratios when no archetype matches -- see
  buildings.rst "Missing TABULA values use safe defaults".
- Never overrides an explicitly-supplied, non-empty ``Windows``/``Doors``/
  ``Ventilation`` component -- EnerPlanET "can provide [it]... but does not
  have to".
"""

from __future__ import annotations

import logging
from typing import Any

from buem.buildings.mapping.element_factory import WallInfo, identify_front_back, synthesize_openings
from buem.buildings.mapping.tabula_helpers import (
    compute_window_ratios,
    lookup_tabula_archetype,
    safe_series_float,
)

logger = logging.getLogger(__name__)

# ── documented safe-default fallback ratios ──────────────────────────────────
#
# Used only when no TABULA archetype can be resolved for the caller's
# building_type/construction_period/country (e.g. a country the bundled
# reference sheet doesn't cover, or a construction_period given as a literal
# year-range like "1965-1974" instead of TABULA's class-code format). NOT
# derived from TABULA data -- a first-pass heuristic, not a substitute for a
# real archetype match, same treatment as buildings.rst's existing "Missing
# TABULA values use safe defaults" table (n_air_infiltration/c_m/etc.), which
# this extends. Windows measurably affect heat loss/gain even at a modest
# share of envelope area, so the fallback always synthesizes something
# physically plausible rather than leaving these components empty.
#
# ~15% glazing-to-wall ratio per cardinal direction sits mid-range for
# existing European residential stock (TABULA archetypes bundled here run
# roughly 8-25% depending on era/type); a single flat door area fraction
# gives a ~2 m2 door on a typical ~40 m2 front wall.
FALLBACK_WINDOW_RATIO_PER_DIRECTION = 0.15
FALLBACK_DOOR_RATIO = 0.05
FALLBACK_WINDOW_U = 2.8
FALLBACK_WINDOW_G_GL = 0.5
FALLBACK_DOOR_U = 3.0
FALLBACK_N_AIR_USE = 0.5

_OPENING_TYPES = ("window", "door", "ventilation")
_COMPONENT_KEY_BY_TYPE = {"window": "Windows", "door": "Doors", "ventilation": "Ventilation"}


def _is_empty_component(components: dict[str, Any], key: str) -> bool:
    comp = components.get(key)
    if not isinstance(comp, dict):
        return True
    return not comp.get("elements")


def _flatten_element(el) -> dict[str, Any]:
    """Convert a synthesized ``EnvelopeElement`` to the flat dict shape used
    by ``components.<Group>.elements[]`` -- the same shape
    ``geojson_validator.py::_convert_v3_to_v2`` and ``cfg_attribute.py``'s
    demo default already use (plain floats, not v3's ``{value, unit}``
    wrapping -- ``EnvelopeElement.to_element_dict()`` is not reused here
    because it targets that different, v3-wrapped shape).
    """
    if el.element_type == "ventilation":
        d: dict[str, Any] = {"id": el.id}
        if el.air_changes is not None:
            d["air_changes"] = round(el.air_changes, 4)
        return d
    d = {
        "id": el.id,
        "area": round(el.area, 4),
        "azimuth": round(el.azimuth, 2),
        "tilt": round(el.tilt, 2),
    }
    if el.surface is not None:
        d["surface"] = el.surface
    return d


def synthesize_missing_openings(
    components: dict[str, Any],
    *,
    building_type: str | None,
    construction_period: str | None,
    country: str | None,
    bldg_tabula_id: str | None = None,
) -> dict[str, Any]:
    """Fill in missing Windows/Doors/Ventilation from Walls geometry.

    Only synthesizes component groups the caller left empty/absent; any
    explicitly-supplied non-empty group is returned unchanged. Returns a
    new dict -- does not mutate ``components`` in place.

    When *all three* of Windows/Doors/Ventilation are missing (the expected
    case: a caller that supplied wall/roof/floor geometry only), the
    synthesized openings are also subtracted from each wall's own area, so
    the envelope doesn't double-count opaque wall area and window/door area
    over the same physical surface (matching
    ``LOD2Mapper``'s own wall-building step, which always uses each wall's
    net opaque area). When only *some* of the three are missing, ``Walls``
    is left untouched -- there is no reliable way to tell how much wall
    area a partially-supplied request already accounted for.
    """
    walls_comp = components.get("Walls")
    if not isinstance(walls_comp, dict):
        # Nothing to synthesize from -- leave components untouched.
        return components
    wall_elements = walls_comp.get("elements")
    if not wall_elements:
        return components

    missing = [
        _COMPONENT_KEY_BY_TYPE[t] for t in _OPENING_TYPES
        if _is_empty_component(components, _COMPONENT_KEY_BY_TYPE[t])
    ]
    if not missing:
        return components

    wall_default_b = float(walls_comp.get("b_transmission", 1.0))
    walls: list[WallInfo] = []
    for idx, elem in enumerate(wall_elements, start=1):
        b_transmission = float(elem.get("b_transmission", wall_default_b))
        walls.append(WallInfo(
            wall_id=str(elem.get("id", f"wall_{idx}")),
            surface_feature_id=-1,  # not applicable outside the LOD2 batch pipeline
            area=float(elem.get("area", 0.0)),
            azimuth=float(elem.get("azimuth", 0.0)) % 360.0,
            is_shared=(b_transmission == 0.0),
        ))

    exposed = [w for w in walls if not w.is_shared]
    front_wall, back_wall = identify_front_back(exposed)

    tabula_row = None
    if building_type:
        tabula_row = lookup_tabula_archetype(
            building_type, construction_period, country, bldg_tabula_id=bldg_tabula_id,
        )

    if tabula_row is not None:
        a_wall_1 = safe_series_float(tabula_row, "A_Wall_1", 0.0)
        window_ratios = compute_window_ratios(tabula_row, a_wall_1)
        door_ratio = (
            safe_series_float(tabula_row, "A_Door_1", 0.0) / a_wall_1 if a_wall_1 > 0 else 0.0
        )
        window_U = safe_series_float(tabula_row, "U_Window_1", FALLBACK_WINDOW_U)
        window_g_gl = safe_series_float(tabula_row, "g_gl_n_Window_1", FALLBACK_WINDOW_G_GL)
        door_U = safe_series_float(tabula_row, "U_Door_1", FALLBACK_DOOR_U)
        n_air_use = safe_series_float(tabula_row, "n_air_use", FALLBACK_N_AIR_USE)
        horizontal = safe_series_float(tabula_row, "A_Window_Horizontal", 0.0)
        logger.info(
            "Synthesizing missing envelope component(s) %s from TABULA archetype %s "
            "(building_type=%r construction_period=%r country=%r)",
            missing, tabula_row.get("Code_BuildingVariant"),
            building_type, construction_period, country,
        )
    else:
        window_ratios = {d: FALLBACK_WINDOW_RATIO_PER_DIRECTION for d in ("north", "east", "south", "west")}
        door_ratio = FALLBACK_DOOR_RATIO
        window_U, window_g_gl = FALLBACK_WINDOW_U, FALLBACK_WINDOW_G_GL
        door_U, n_air_use, horizontal = FALLBACK_DOOR_U, FALLBACK_N_AIR_USE, 0.0
        logger.warning(
            "No TABULA archetype resolved for building_type=%r construction_period=%r "
            "country=%r -- synthesizing missing envelope component(s) %s from buem's "
            "documented safe-default ratios, not real TABULA data (see buildings.rst "
            "'Missing TABULA values use safe defaults').",
            building_type, construction_period, country, missing,
        )

    opening_elements = synthesize_openings(
        exposed, front_wall, back_wall,
        window_ratios=window_ratios,
        door_ratio=door_ratio,
        window_U=window_U,
        window_g_gl=window_g_gl,
        door_U=door_U,
        n_air_use=n_air_use,
        horizontal_window_area=horizontal,
    )

    result = dict(components)

    grouped: dict[str, list[dict[str, Any]]] = {"Windows": [], "Doors": [], "Ventilation": []}
    for el in opening_elements:
        grouped[_COMPONENT_KEY_BY_TYPE[el.element_type]].append(_flatten_element(el))

    for comp_key, comp_U, comp_g_gl in (
        ("Windows", window_U, window_g_gl),
        ("Doors", door_U, None),
        ("Ventilation", None, None),
    ):
        if comp_key not in missing:
            continue
        comp: dict[str, Any] = {"elements": grouped[comp_key]}
        if comp_U is not None:
            comp["U"] = comp_U
        if comp_g_gl is not None:
            comp["g_gl"] = comp_g_gl
        result[comp_key] = comp

    # Shrink wall areas to opaque net area -- only when the full opening set
    # was synthesized (see docstring: partial overrides leave Walls alone).
    # ``walls`` was built from ``wall_elements`` via enumerate() above, so
    # the two lists share order/length -- zip rather than re-match by id,
    # which would break for walls without an explicit "id".
    if set(missing) == {"Windows", "Doors", "Ventilation"}:
        new_wall_elements = [
            {**elem, "area": round(w.net_area, 4)}
            for elem, w in zip(wall_elements, walls)
        ]
        result["Walls"] = {**walls_comp, "elements": new_wall_elements}

    return result
