"""
Netherlands building-type classification -- a from-scratch replacement for
city2tabula's (mistrusted, per the user 2026-08-17: "I do not fully trust
the TABULA and 3D BAG/LOD2 building mapping done by city2tabula") linking
between a real building and a TABULA archetype's ``Code_BuildingSizeClass``
(SFH/TH/MFH/AB) and ``Code_AttachedNeighbours`` (B_Alone/B_N1/B_N2).

Method: replicates CBS's own published ``woningtype`` derivation
methodology (Statistics Netherlands, the national statistics office --
see ``.claude/residential/resolved.md`` for the full research trail,
2026-08-17), rather than inventing a new one or training a classifier:

    "de[rivation] ... is based on a modeling approach where the number of
    connected BAG buildings and the number of BAG residential objects
    with their use function determines the assignment of housing type"
    -- CBS, https://www.cbs.nl/nl-nl/onze-diensten/methoden/
    onderzoeksomschrijvingen/korte-onderzoeksomschrijvingen/woningtype

Both signals CBS describes are already available here without needing
CBS's own (access-gated) microdata product:

- "number of connected BAG buildings" == this session's own geometric
  party-wall coincidence detection (``cityjson_extractor
  .detect_party_walls``), already recorded per building as
  ``attached_neighbour_id`` (semicolon-joined list of neighbouring
  ``bag_pand_id`` values).
- "number of BAG residential objects" == ``aant_verblijfsobj`` from the
  RIVM energy-labels GeoPackage (``energielabels_2025.gpkg`` --
  ``identificatie`` joins exactly to ``bag_pand_id`` once the
  ``NL.IMBAG.Pand.`` prefix is stripped; 99.4% match rate for Loenen,
  confirmed 2026-08-16/17).

CBS's exact category rules (Dutch, quoted from the page above) and their
mapping onto TABULA's coarser SFH/TH/MFH/AB + B_Alone/B_N1/B_N2 scheme
(buem's own judgment call, not from CBS -- CBS's 5 categories don't
correspond 1:1 to TABULA's 4):

======================  ======================================  ==========================
CBS category            CBS rule                                 TABULA mapping
======================  ======================================  ==========================
vrijstaand              0 connections                            SFH, B_Alone
twee-onder-een-kap      1 connection, pair (component size 2)     SFH, B_N1
hoekwoning              1 connection, in a row of 3+               TH, B_N1
tussenwoning            2+ connections (row middle)                TH, B_N2
meergezinswoning        2+ residential units in one Pand           MFH or AB (see below)
======================  ======================================  ==========================

The SFH/TH split for "1 connection" buildings follows TABULA's own
distinction between a semi-detached *pair* (still a single-family
dwelling *form*, structurally close to detached) and a genuine terraced
*row* (an architecturally different typology) -- a corner/end unit of a
3+ row is architecturally a row house even though it only touches one
neighbour, hence TH not SFH.

MFH vs. AB has no CBS or TABULA-published threshold -- buem's own
first-pass heuristic (``MFH_MAX_UNITS``), same framing as
``cfg_attribute.DEFAULT_ARCHETYPE_BY_BUILDING_TYPE``'s own "first-pass
heuristic, not a derivation" disclaimer: revisit with real data if/when
available.

Non-residential handling (2026-08-17, refined 2026-08-18): 3D BAG's own
``b3_kas_warenhuis`` (greenhouse/warehouse) and ``b3_is_glas_dak``
(glasshouse roof) flags (2 + 2 = 4 of Loenen's 3,105 buildings) mark a
building as not a dwelling -- excluded from TABULA *residential*
matching. Checking the flagged buildings' own footprint areas (per the
user, 2026-08-18: "the 4 buildings excluded ... should not be fully
excluded as they can be considered as service buildings and linked to
the occupancy module") before routing them uniformly surfaced a real
split, not assumed: the two ``b3_kas_warenhuis`` buildings are genuinely
large (2,125 m² / 1,718 m²) -- real commercial-scale structures, linked
here to occupancy's ``warehouse`` service-building type (the closest of
its 8 registered types; ``b3_kas_warenhuis`` conflates greenhouse *and*
department store under one flag, both closer to a large low-occupant-
density warehouse than to any other registered type). The two
``b3_is_glas_dak`` buildings are tiny (16 m² / 5 m²) -- too small to be
a real occupied structure at all (most likely a garden greenhouse/
conservatory/shed) -- these remain excluded from *both* residential and
service-building modeling, not force-fit into a type that wouldn't make
physical sense; ``MIN_SERVICE_BUILDING_FOOTPRINT_M2`` is the threshold
that separates the two cases.
"""

from __future__ import annotations

import logging
from collections import defaultdict

import pandas as pd

logger = logging.getLogger(__name__)

MFH_MAX_UNITS = 4
"""First-pass heuristic split between MFH and AB when a Pand has 2+
residential units -- neither CBS nor TABULA publish a threshold for
this; revisit with real data if/when available (see module docstring)."""

MIN_SERVICE_BUILDING_FOOTPRINT_M2 = 50.0
"""Below this footprint, a building flagged non-residential is treated
as too small to be a real occupied structure (garden shed/greenhouse/
conservatory) rather than linked to a service-building type -- see
module docstring. Real Loenen buildings sit well clear of this threshold
on both sides (2,125/1,718 m² real commercial structures vs. 16/5 m²
garden structures), so this is not a finely-tuned cutoff."""

# 3D BAG flag -> occupancy.services_buildings.SERVICE_BUILDING_TYPES id,
# for a large-enough (>= MIN_SERVICE_BUILDING_FOOTPRINT_M2) flagged
# building. Only b3_kas_warenhuis has a real large-building case in
# Loenen today; b3_is_glas_dak's real cases are both tiny (see above),
# but the mapping is defined for either flag in case a future region has
# a large glass-roofed structure (e.g. a real glasshouse/greenhouse
# complex) that should also route to a service type.
_SERVICE_TYPE_BY_FLAG = {
    "is_greenhouse_or_warehouse": "warehouse",
    "is_glass_roof": "warehouse",
}


def build_adjacency(buildings_df: pd.DataFrame) -> dict[str, set[str]]:
    """bag_pand_id -> set of directly-adjacent bag_pand_id, from the
    ``attached_neighbour_id`` column (semicolon-joined, as written by
    ``cityjson_extractor``)."""
    graph: dict[str, set[str]] = defaultdict(set)
    for _, row in buildings_df.iterrows():
        pid = row["bag_pand_id"]
        graph.setdefault(pid, set())
        raw = row.get("attached_neighbour_id")
        if pd.isna(raw) or not raw:
            continue
        for neighbour in str(raw).split(";"):
            neighbour = neighbour.strip()
            if not neighbour:
                continue
            graph[pid].add(neighbour)
            graph[neighbour].add(pid)  # adjacency is symmetric even if only recorded one-sided
    return graph


def connected_component_sizes(graph: dict[str, set[str]]) -> dict[str, int]:
    """bag_pand_id -> size of the connected component (row/pair/etc.) it
    belongs to, via a plain BFS over the adjacency graph. An isolated
    building (no neighbours) has component size 1."""
    sizes: dict[str, int] = {}
    seen: set[str] = set()
    for start in graph:
        if start in seen:
            continue
        component: list[str] = []
        queue = [start]
        seen.add(start)
        while queue:
            node = queue.pop()
            component.append(node)
            for neighbour in graph.get(node, ()):
                if neighbour not in seen:
                    seen.add(neighbour)
                    queue.append(neighbour)
        for node in component:
            sizes[node] = len(component)
    return sizes


def classify_building_type(
    degree: int, component_size: int, n_residential_units: float | None,
) -> tuple[str, str]:
    """Classify one building into (Code_BuildingSizeClass, Code_AttachedNeighbours).

    Parameters
    ----------
    degree : int
        Number of directly-attached neighbouring buildings (0, 1, 2+).
    component_size : int
        Size of the connected group this building belongs to (including
        itself) -- distinguishes a semi-detached *pair* (size 2) from a
        row's corner unit (size 3+, degree 1 either way).
    n_residential_units : float or None
        RIVM's ``aant_verblijfsobj`` for this Pand, or ``None`` if no
        match was found (treated as 1 -- the common case, not "unknown
        multi-unit").

    Returns
    -------
    (building_type, neighbour_status)
        e.g. ``("TH", "B_N1")``.
    """
    units = n_residential_units if n_residential_units and n_residential_units > 0 else 1.0

    if units >= 2:
        building_type = "MFH" if units <= MFH_MAX_UNITS else "AB"
        neighbour_status = "B_Alone" if degree == 0 else ("B_N1" if degree == 1 else "B_N2")
        return building_type, neighbour_status

    if degree == 0:
        return "SFH", "B_Alone"
    if degree == 1:
        return ("SFH", "B_N1") if component_size <= 2 else ("TH", "B_N1")
    return "TH", "B_N2"


def _service_building_type(row: pd.Series) -> str | None:
    """Which occupancy service-building type (if any) a non-residential
    building links to -- ``None`` when it's flagged but too small to be a
    real occupied structure (see module docstring)."""
    footprint = row.get("footprint_area") or 0.0
    if footprint < MIN_SERVICE_BUILDING_FOOTPRINT_M2:
        return None
    for flag_col, service_type in _SERVICE_TYPE_BY_FLAG.items():
        if bool(row.get(flag_col)):
            return service_type
    return None


def classify_all(
    buildings_df: pd.DataFrame, units_by_pand_id: dict[str, float],
) -> pd.DataFrame:
    """Add ``building_type``/``neighbour_status``/``is_residential``/
    ``service_building_type`` columns to a copy of ``buildings_df``.

    A building flagged non-residential (greenhouse/warehouse/glasshouse)
    gets ``is_residential=False`` and null TABULA type/neighbour_status
    either way -- never forced into a residential archetype. Large enough
    ones (``>= MIN_SERVICE_BUILDING_FOOTPRINT_M2``) additionally get a
    real ``service_building_type`` (one of occupancy's registered
    service-building ids); buildings too small to be a real occupied
    structure get neither -- excluded from both residential and service
    modeling. See module docstring for the real Loenen evidence behind
    this split.
    """
    graph = build_adjacency(buildings_df)
    sizes = connected_component_sizes(graph)

    building_types: list[str | None] = []
    neighbour_statuses: list[str | None] = []
    is_residential: list[bool] = []
    service_building_types: list[str | None] = []
    for _, row in buildings_df.iterrows():
        pid = row["bag_pand_id"]
        non_residential = bool(row.get("is_greenhouse_or_warehouse")) or bool(row.get("is_glass_roof"))
        if non_residential:
            building_types.append(None)
            neighbour_statuses.append(None)
            is_residential.append(False)
            service_building_types.append(_service_building_type(row))
            continue
        service_building_types.append(None)
        degree = len(graph.get(pid, ()))
        component_size = sizes.get(pid, 1)
        units = units_by_pand_id.get(pid)
        btype, nstatus = classify_building_type(degree, component_size, units)
        building_types.append(btype)
        neighbour_statuses.append(nstatus)
        is_residential.append(True)

    result = buildings_df.copy()
    result["building_type"] = building_types
    result["neighbour_status"] = neighbour_statuses
    result["is_residential"] = is_residential
    result["service_building_type"] = service_building_types

    n_non_residential = (~result["is_residential"]).sum()
    n_service = result["service_building_type"].notna().sum()
    n_unmodeled = n_non_residential - n_service
    if n_non_residential:
        logger.info(
            "classify_all: %d/%d buildings flagged non-residential -- %d linked to a "
            "service_building_type, %d too small to be a real occupied structure (excluded entirely)",
            n_non_residential, len(result), n_service, n_unmodeled,
        )
    logger.info("classify_all: building_type distribution: %s",
                result.loc[result["is_residential"], "building_type"].value_counts().to_dict())
    return result


__all__ = ["MFH_MAX_UNITS", "build_adjacency", "classify_all", "classify_building_type", "connected_component_sizes"]
