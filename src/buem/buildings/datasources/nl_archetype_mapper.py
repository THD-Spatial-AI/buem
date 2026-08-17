"""
Netherlands TABULA archetype linking -- the "which real TABULA row does
this building match" step city2tabula used to own, redone from scratch
(2026-08-17) per the user: "I do not fully trust the TABULA and 3D BAG/
LOD2 building mapping done by city2tabula. So, if you are deriving the
U-values based on that mapping, it might be wrong."

This module does **not** distrust TABULA's own published Dutch archetype
*data* (``tabula.csv``, Code_Country == "NL", 135 real research-project
rows) -- only city2tabula's *linking* of a specific building to one of
those rows. The two are independently cross-validated here before being
trusted: TABULA NL's own ``U_Wall_1`` values, converted to Rc = 1/U, match
the independently-researched Dutch Bouwbesluit/NTA 8800 historical
Rc-value requirements almost exactly at every checkable point (e.g.
1975-1991: TABULA gives 1.30 m2K/W, Bouwbesluit's own published minimum
for that period is 1.30 m2K/W -- see ``.claude/residential/resolved.md``
for the full cross-validation, 2026-08-17). The *fresh* link built here
uses only signals independent of city2tabula: real ``construction_year``
(from 3D BAG's own ``oorspronkelijkbouwjaar``, not a fuzzy range) and a
building_type/neighbour_status derived by
:mod:`buem.buildings.mapping.nl_building_classifier` (real geometry +
RIVM energy-label metadata, replicating CBS's own published methodology
-- see that module's docstring).

Two routes into the same TABULA year-class, per the user (2026-08-17,
"I agree that we use the real label as an override where present"):

1. **Real energy label present** (24% of Loenen buildings, see
   ``rivm_energy_labels``): NTA 8800/ISSO 82.1 treats a construction-year
   class and a "typical baseline label" as two views of the same
   historical insulation-standard tier ("building year heavily dictates
   the final energy label... this mapping forms the proxy backbone for
   energy-to-insulation mapping" -- user-supplied reference, 2026-08-17).
   ``LABEL_TO_YEAR_CLASS`` is that correspondence read in reverse: a real
   label maps straight to the year-class whose typical performance it
   matches, overriding whatever the raw construction year would have
   picked -- because the label reflects the building's *actual current*
   envelope (post-renovation, if any), which a year-class average cannot.
2. **No real label** (76%): the year-class is read directly from the
   real ``construction_year``.

Either way, the resulting year-class + the classifier's building_type
are looked up against the *real* bundled Dutch TABULA sheet via
:func:`tabula_helpers.lookup_tabula_archetype` (parameterized onto the NL
sheet 2026-08-17 specifically for this) -- the exact same selection logic
(prefer a ``.Gen.`` variant, lowest id) ``LOD2Mapper``/``live_synthesis``
already use for Germany, not a reimplementation. A matched building's
``tabula_variant_code_id``/``tabula_variant_code`` are set to that real
row's own ``id``/``Code_BuildingVariant`` -- so ``LOD2Mapper.map_building()``
needs no code changes at all to start working for Netherlands buildings
once this has run; only the *editable* U-value override
(``u_value_reference.csv``) needed a small, optional hook -- see
``LOD2Mapper.__init__``'s ``u_value_overrides`` parameter.
"""

from __future__ import annotations

import logging

import pandas as pd

from buem.buildings.mapping.nl_building_classifier import classify_all
from buem.buildings.mapping.tabula_helpers import lookup_tabula_archetype

logger = logging.getLogger(__name__)

# TABULA NL's own construction-year class boundaries (confirmed directly
# from the bundled tabula.csv, 2026-08-17 -- not assumed): NL.01 <=1964,
# NL.02 1965-1974, NL.03 1975-1991, NL.04 1992-2005, NL.05 2006-2014,
# NL.06 2015+. These already align closely with the real Dutch Bouwbesluit
# code-change history (1965/1975/1992/2015), which is presumably *why*
# TABULA chose them, not a coincidence.
_YEAR_CLASS_BOUNDARIES: list[tuple[int, str]] = [
    (1965, "01"), (1975, "02"), (1992, "03"), (2006, "04"), (2015, "05"),
]
_LATEST_YEAR_CLASS = "06"

# Real RIVM dominant_label -> the TABULA year-class whose typical envelope
# performance NTA 8800/ISSO 82.1 associates with that label (see module
# docstring). B and A both fall in the user-supplied table's single
# "1992-2014" bucket; split across TABULA's own finer NL.04/NL.05 boundary
# here (B -> the earlier, A -> the later sub-period) as the natural way to
# use the extra resolution TABULA offers beyond the label table's own,
# coarser bucketing -- not itself independently sourced, flagged as such.
LABEL_TO_YEAR_CLASS: dict[str, str] = {
    "G": "NL.01", "F": "NL.01",
    "E": "NL.02", "D": "NL.02",
    "C": "NL.03",
    "B": "NL.04",
    "A": "NL.05",
    "A+": "NL.06", "A++": "NL.06", "A+++": "NL.06", "A++++": "NL.06", "A+++++": "NL.06",
}


def year_to_construction_class(year: float | None) -> str | None:
    """Real construction year -> TABULA ``NL.0X`` class code, or ``None``
    if no year is available -- picking *any* class without a year would
    be a silent guess in either direction (oldest and newest are both
    unjustified); callers should skip TABULA matching for that building
    instead, the same way a missing building_type is already handled.
    Not currently reachable for the bundled Loenen data specifically
    (``construction_year`` is 100% populated from real BAG
    ``oorspronkelijkbouwjaar``), but a real possibility for other regions.
    """
    if year is None or pd.isna(year):
        return None
    year = int(year)
    for boundary, code in _YEAR_CLASS_BOUNDARIES:
        if year < boundary:
            return f"NL.{code}"
    return f"NL.{_LATEST_YEAR_CLASS}"


def label_to_construction_class(label: str | None) -> str | None:
    """Real RIVM ``dominant_label`` -> equivalent TABULA year-class, or
    ``None`` if the label is missing/unrecognized (caller falls back to
    the year-derived class)."""
    if label is None or pd.isna(label):
        return None
    return LABEL_TO_YEAR_CLASS.get(str(label).strip())


def map_buildings(
    buildings_df: pd.DataFrame,
    nl_tabula_df: pd.DataFrame,
    rivm_labels_df: pd.DataFrame,
) -> pd.DataFrame:
    """Full Netherlands archetype-linking pipeline.

    Parameters
    ----------
    buildings_df : pd.DataFrame
        ``cityjson_extractor``'s regenerated ``lod2_building_feature``
        table (must have ``bag_pand_id``, ``construction_year``,
        ``attached_neighbour_id``, ``is_greenhouse_or_warehouse``,
        ``is_glass_roof``).
    nl_tabula_df : pd.DataFrame
        The real bundled Dutch TABULA sheet (``Code_Country == "NL"``).
    rivm_labels_df : pd.DataFrame
        Output of ``rivm_energy_labels.load_labels_for_buildings`` --
        ``bag_pand_id``/``aant_verblijfsobj``/``dominant_label``.

    Returns
    -------
    pd.DataFrame
        A copy of ``buildings_df`` with ``building_type``,
        ``neighbour_status``, ``is_residential``,
        ``construction_year_class`` (the class actually used --
        label-derived when available), ``matched_via_label`` (bool, for
        transparency), ``tabula_variant_code_id``, and
        ``tabula_variant_code`` populated. Non-residential and
        no-archetype-match buildings keep ``tabula_variant_code_id`` null
        (unchanged from ``cityjson_extractor``'s own output) -- exactly
        as ``LOD2Mapper.map_building()`` already expects (it returns
        ``None`` cleanly for a building with no TABULA match, logging a
        warning, rather than raising).
    """
    units_by_pand_id = dict(zip(rivm_labels_df["bag_pand_id"], rivm_labels_df["aant_verblijfsobj"], strict=False))
    labels_by_pand_id = dict(zip(rivm_labels_df["bag_pand_id"], rivm_labels_df["dominant_label"], strict=False))

    classified = classify_all(buildings_df, units_by_pand_id)

    # Real dwelling-unit count, carried through as its own column (not
    # just consumed internally by classify_all) -- found necessary
    # 2026-08-18 while building the CBS validation script: an MFH/AB
    # building_feature_id is a whole multi-unit *building*, but every
    # downstream per-dwelling comparison (CBS's own gas/electricity
    # figures are per dwelling, not per building) needs this to
    # normalize a whole-building simulation result back to a per-unit
    # figure. Defaults to 1.0 (no RIVM match), matching classify_all's
    # own "no data -> treat as single-unit" convention exactly.
    def _real_or_default_units(pid: str) -> float:
        units = units_by_pand_id.get(pid)
        return float(units) if units is not None and units > 0 else 1.0

    classified["residential_units"] = [_real_or_default_units(pid) for pid in classified["bag_pand_id"]]

    year_classes: list[str | None] = []
    matched_via_label: list[bool] = []
    tabula_ids: list[float | None] = []
    tabula_codes: list[str | None] = []

    n_matched = 0
    for _, row in classified.iterrows():
        if not row["is_residential"]:
            year_classes.append(None)
            matched_via_label.append(False)
            tabula_ids.append(None)
            tabula_codes.append(None)
            continue

        label = labels_by_pand_id.get(row["bag_pand_id"])
        label_class = label_to_construction_class(label)
        if label_class is not None:
            year_class: str | None = label_class
            via_label = True
        else:
            year_class = year_to_construction_class(row.get("construction_year"))
            via_label = False

        tabula_row = (
            lookup_tabula_archetype(row["building_type"], year_class.split(".")[1], "NL", sheet=nl_tabula_df)
            if year_class is not None else None
        )
        year_classes.append(year_class)
        matched_via_label.append(via_label)
        if tabula_row is not None:
            tabula_ids.append(float(tabula_row["id"]))
            tabula_codes.append(str(tabula_row["Code_BuildingVariant"]))
            n_matched += 1
        else:
            logger.warning(
                "No TABULA archetype match for %s (building_type=%r year_class=%r)",
                row["bag_pand_id"], row["building_type"], year_class,
            )
            tabula_ids.append(None)
            tabula_codes.append(None)

    result = classified.copy()
    result["construction_year_class"] = year_classes
    result["matched_via_label"] = matched_via_label
    result["tabula_variant_code_id"] = tabula_ids
    result["tabula_variant_code"] = tabula_codes

    n_residential = int(result["is_residential"].sum())
    logger.info(
        "map_buildings: %d/%d residential buildings matched a TABULA archetype "
        "(%d via a real energy label, %d via construction year)",
        n_matched, n_residential, sum(matched_via_label), n_matched - sum(matched_via_label),
    )
    return result


__all__ = [
    "LABEL_TO_YEAR_CLASS",
    "label_to_construction_class",
    "map_buildings",
    "year_to_construction_class",
]
