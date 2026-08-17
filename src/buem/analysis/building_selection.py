"""
Building selection helpers over ``ExcelBuildingSource``/``PostgresBuildingSource``
+ ``LOD2Mapper`` -- picking and sanity-checking real, freshly-mapped buildings
for analysis, instead of hand-writing a filter loop each time (as the
previous ad hoc comparison session did).

"Freshly mapped" matters: party-wall (shared-wall) detection is computed
once per ``LOD2Mapper`` instance from the *entire* surface table
(``SharedWallDetector``, see ``buem.buildings.mapping.wall_classifier``),
so a building picked and mapped through this module gets a real,
cross-building-verified party-wall determination -- unlike reading an
already-exported GeoJSON fixture, which only reflects whatever was true
when that fixture was generated.
"""
from __future__ import annotations

import logging
import math
from collections.abc import Iterable
from dataclasses import dataclass

from buem.buildings.building import Building
from buem.buildings.mapping.lod2_mapper import BuildingSource, LOD2Mapper
from buem.config.building_registry import RESIDENTIAL_BUILDING_TYPES

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class WallExposureSummary:
    """Party-wall sanity-check result for one mapped building."""

    n_walls: int
    n_exposed: int
    n_shared: int

    @property
    def has_exposed_wall(self) -> bool:
        return self.n_exposed >= 1

    @property
    def is_fully_exposed(self) -> bool:
        return self.n_shared == 0


def wall_exposure(building: Building) -> WallExposureSummary:
    """Summarize a mapped building's exposed-vs-shared wall split.

    A building with **zero exposed walls** is physically impossible (a
    real building always has at least one surface facing the outdoors) --
    found during this module's own precursor investigation to be a real,
    if uncommon, characteristic of some city2tabula rows even under
    correct, freshly-computed cross-building party-wall detection (not
    just a stale-fixture artifact). ``select_household_buildings()``
    below excludes these by default; check ``has_exposed_wall`` directly
    if you need to see them.
    """
    walls = building.walls()
    n_shared = sum(1 for w in walls if w.b_transmission == 0)
    return WallExposureSummary(n_walls=len(walls), n_exposed=len(walls) - n_shared, n_shared=n_shared)


def select_household_buildings(
    source: BuildingSource,
    *,
    country: str = "DE",
    building_types: Iterable[str] = RESIDENTIAL_BUILDING_TYPES,
    min_area_m2: float = 40.0,
    max_area_m2: float = 300.0,
    require_exposed_wall: bool = True,
    limit: int | None = None,
    scan_limit: int | None = None,
) -> list[Building]:
    """Pick and map a list of plausible household buildings.

    Filters on the source's own building/TABULA tables first (type,
    country) before mapping anything, then maps each candidate via
    ``LOD2Mapper`` (one shared ``SharedWallDetector`` instance, computed
    once against the source's full surface table) and applies the
    remaining, mapping-dependent filters (floor area, exposed-wall sanity
    check).

    Parameters
    ----------
    source : ExcelBuildingSource | PostgresBuildingSource
        Any ``BuildingSource``-protocol data source.
    country : str
        ISO 3166-1 alpha-2 country code, passed to ``LOD2Mapper``.
    building_types : iterable of str
        TABULA size classes to keep (default: the four residential codes
        -- ``RESIDENTIAL_BUILDING_TYPES``).
    min_area_m2, max_area_m2 : float
        Reject a mapped building whose ``A_ref`` falls outside this range
        -- filters out both LOD2 digitization artifacts (near-zero area)
        and building/archetype geometry mismatches that inflate ``A_ref``
        implausibly.
    require_exposed_wall : bool
        Reject a mapped building with zero exposed walls (see
        ``wall_exposure``'s docstring) -- default ``True``.
    limit : int, optional
        Stop once this many buildings have passed every filter.
    scan_limit : int, optional
        Cap how many candidate ``building_feature_id``s are even
        considered (before mapping) -- useful to bound a quick smoke test
        against a source with thousands of rows. ``None`` scans all of
        them (bounded by ``limit`` once enough have passed).

    Returns
    -------
    list of Building
    """
    building_types = set(building_types)
    bldg_df = source.buildings
    tabula_df = source.tabula.set_index("id")

    candidate_ids: list[int] = []
    for _, row in bldg_df.iterrows():
        tabula_id = row.get("tabula_variant_code_id")
        if tabula_id is None or math.isnan(tabula_id):
            continue
        tabula_row = tabula_df.loc[int(tabula_id)] if int(tabula_id) in tabula_df.index else None
        if tabula_row is None or tabula_row.get("Code_BuildingSizeClass") not in building_types:
            continue
        candidate_ids.append(int(row["building_feature_id"]))
        if scan_limit is not None and len(candidate_ids) >= scan_limit:
            break

    mapper = LOD2Mapper(source, country=country)
    selected: list[Building] = []
    for building_feature_id in candidate_ids:
        building = mapper.map_building(building_feature_id)
        if building is None:
            continue
        if not (min_area_m2 <= building.A_ref <= max_area_m2):
            continue
        if require_exposed_wall and not wall_exposure(building).has_exposed_wall:
            logger.info(
                "building_feature_id=%d: 0 exposed walls (all %d shared) -- "
                "excluded (require_exposed_wall=True).",
                building_feature_id, len(building.walls()),
            )
            continue
        selected.append(building)
        if limit is not None and len(selected) >= limit:
            break

    return selected


__all__ = ["WallExposureSummary", "select_household_buildings", "wall_exposure"]
