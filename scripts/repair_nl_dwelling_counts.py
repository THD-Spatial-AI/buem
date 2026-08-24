"""Add floor-area-derived dwelling counts to a Netherlands region's
building table, where the registered count cannot be right.

CBS publishes household energy consumption per dwelling, and buem scales
occupancy's internal gains by the same count, so a wrong
``residential_units`` corrupts the comparison in both directions. A single
BAG Pand can legitimately be a whole terrace or apartment block, and
RIVM's ``aant_verblijfsobj`` sometimes registers only part of its
sub-units -- leaving buildings that imply thousands of square metres per
household.

Rewrites ``lod2_building_feature.csv`` in place, adding
``residential_units_recorded`` and ``residential_units_source`` alongside
the repaired ``residential_units`` so a derived value can never be
mistaken for registered data.

    python scripts/repair_nl_dwelling_counts.py [data_dir]

Idempotent: re-running finds nothing further to repair.
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

import pandas as pd

from buem.buildings.datasources.nl_archetype_mapper import (
    IMPLAUSIBLE_M2_PER_DWELLING,
    repair_dwelling_counts,
)

DEFAULT_DATA_DIR = Path("src/buem/data/buildings/netherlands/Loenen")


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    args = argv if argv is not None else sys.argv[1:]
    data_dir = Path(args[0]) if args else DEFAULT_DATA_DIR
    path = data_dir / "lod2_building_feature.csv"
    if not path.exists():
        print(f"ERROR: {path} not found", file=sys.stderr)
        return 1

    before = pd.read_csv(path, na_values=["NULL"], low_memory=False)
    storeys = before.get("number_of_storeys", pd.Series(1.0, index=before.index)).fillna(1.0).clip(lower=1.0)
    area = before.get("area_total_floor", pd.Series(0.0, index=before.index)).fillna(0.0) * storeys
    # Non-residential buildings have no dwellings, so a large area per
    # "dwelling" is expected there and is not a data defect to count.
    residential = (
        before["is_residential"].fillna(False).astype(bool)
        if "is_residential" in before.columns
        else pd.Series(True, index=before.index)
    )
    recorded_col = (
        "residential_units_recorded" if "residential_units_recorded" in before.columns
        else "residential_units"
    )
    units = before.get(recorded_col, pd.Series(1.0, index=before.index)).fillna(1.0).clip(lower=1.0)
    n_bad_before = int(((area / units > IMPLAUSIBLE_M2_PER_DWELLING) & residential).sum())

    after = repair_dwelling_counts(before)

    new_units = after["residential_units"].clip(lower=1.0)
    n_bad_after = int(((area / new_units > IMPLAUSIBLE_M2_PER_DWELLING) & residential).sum())
    n_changed = int((after["residential_units_source"] == "floor_area_estimate").sum())

    after.to_csv(path, index=False)
    print(f"Wrote {path}")
    print(f"  buildings:                            {len(after)}")
    print(f"  residential:                          {int(residential.sum())}")
    print(f"  implausible before (residential):     {n_bad_before}")
    print(f"  dwelling counts estimated:            {n_changed}")
    print(f"  implausible after (residential):      {n_bad_after}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
