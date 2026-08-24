"""
RIVM Dutch energy-labels GeoPackage reader -- ``energielabels_2025.gpkg``,
a nationwide (~11.35M row, ~3.2GB) export of real registered Dutch
building energy labels.

**Never loaded in full.** A GeoPackage is plain SQLite under the hood
(the ``gpkg_*`` metadata tables are just regular SQLite tables), so this
module queries it with the stdlib ``sqlite3`` module directly -- a
targeted ``WHERE identificatie IN (...)`` against a specific set of BAG
Pand ids, never a full-table read, matching this session's same
"don't read the whole huge file" discipline already applied to the
17MB CityJSON source (script-based, never the Read tool; here, SQL
`WHERE`, never a pandas/geopandas full-table load).

Schema (confirmed 2026-08-17 via a schema-only query, not assumed)::

    identificatie      TEXT     -- BAG Pand id, RAW 16-digit form,
                                    e.g. "0200100000938969" -- no
                                    "NL.IMBAG.Pand." prefix (unlike the
                                    CityJSON/cityjson_extractor id shape)
    aant_verblijfsobj  REAL     -- number of residential units ("verblijfs-
                                    objecten") registered under this Pand
    dominant_label     TEXT     -- most common label among this Pand's
                                    units, e.g. "C", "A++++"; NULL if no
                                    label is on record for this building
    hoogste_label      TEXT     -- best label present
    laagste_label      TEXT     -- worst label present

Coverage, confirmed for the real Loenen dataset (2026-08-17): 3,087/3,105
buildings (99.4%) have a matching Pand row at all, but only 742 (23.9%)
have a real, non-null ``dominant_label`` -- most buildings have never had
an energy label registered (matches the ~30% national average). This is
why the label is used as an *override* where present, not the sole
source -- see ``nl_archetype_mapper``.
"""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

_BAG_PREFIX = "NL.IMBAG.Pand."


def strip_bag_prefix(bag_pand_id: str) -> str:
    """``"NL.IMBAG.Pand.0200100000938969"`` -> ``"0200100000938969"`` --
    the raw form RIVM's ``identificatie`` column uses."""
    return bag_pand_id.removeprefix(_BAG_PREFIX)


def load_labels_for_buildings(gpkg_path: str | Path, bag_pand_ids: list[str]) -> pd.DataFrame:
    """Query only the given buildings' rows from the RIVM GeoPackage.

    Parameters
    ----------
    gpkg_path : str or Path
        Path to ``energielabels_2025.gpkg`` (or an equivalent RIVM export).
    bag_pand_ids : list of str
        Full ``NL.IMBAG.Pand.<digits>`` ids (``cityjson_extractor``'s own
        ``bag_pand_id`` column shape) -- prefix-stripped internally before
        querying.

    Returns
    -------
    pd.DataFrame
        Columns ``bag_pand_id`` (restored to the full prefixed form),
        ``aant_verblijfsobj``, ``dominant_label``, ``hoogste_label``,
        ``laagste_label``. One row per *matched* input id -- ids with no
        row in the RIVM file are simply absent, not filled with NaN rows
        (caller's ``.get()``-style lookup should treat "absent" and
        "matched but null label" as the two distinct cases they are).

    Raises
    ------
    FileNotFoundError
        If ``gpkg_path`` does not exist.
    """
    gpkg_path = Path(gpkg_path)
    if not gpkg_path.exists():
        raise FileNotFoundError(f"RIVM energy-labels GeoPackage not found: {gpkg_path}")

    stripped_to_full = {strip_bag_prefix(pid): pid for pid in bag_pand_ids}
    stripped_ids = list(stripped_to_full.keys())

    conn = sqlite3.connect(f"file:{gpkg_path}?mode=ro", uri=True)
    try:
        # SQLite has a default limit of 999-32766 host parameters per
        # statement depending on build; chunk defensively rather than
        # assume a large IN-list always works in one query.
        chunks = [stripped_ids[i:i + 500] for i in range(0, len(stripped_ids), 500)]
        frames = []
        for chunk in chunks:
            placeholders = ",".join("?" for _ in chunk)
            query = (
                "SELECT identificatie, aant_verblijfsobj, dominant_label, "
                "hoogste_label, laagste_label FROM energielabels_2025 "
                f"WHERE identificatie IN ({placeholders})"
            )
            rows = conn.execute(query, chunk).fetchall()
            frames.append(pd.DataFrame(
                rows,
                columns=["identificatie", "aant_verblijfsobj", "dominant_label",
                         "hoogste_label", "laagste_label"],
            ))
    finally:
        conn.close()

    result = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(
        columns=["identificatie", "aant_verblijfsobj", "dominant_label", "hoogste_label", "laagste_label"],
    )
    result["bag_pand_id"] = result["identificatie"].map(stripped_to_full)
    result = result.drop(columns=["identificatie"])

    n_labeled = result["dominant_label"].notna().sum()
    logger.info(
        "load_labels_for_buildings: %d/%d requested buildings matched, %d (%.1f%%) have a real label",
        len(result), len(bag_pand_ids), n_labeled,
        100 * n_labeled / len(bag_pand_ids) if bag_pand_ids else 0.0,
    )
    return result


__all__ = ["load_labels_for_buildings", "strip_bag_prefix"]
