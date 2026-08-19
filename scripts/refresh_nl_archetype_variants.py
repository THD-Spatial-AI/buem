"""One-time migration of ``src/buem/data/buildings/netherlands/
lod2_building_feature.csv`` to refurbishment-variant-aware TABULA links.

Earlier versions of ``nl_archetype_mapper.map_buildings`` used a real
energy label to *reassign* a building's construction-year class (storing
the label-implied class in ``construction_year_class``), always linking
the as-built TABULA variant (``Number_BuildingVariant == 1``). The
current logic instead keeps the construction-year-derived era and uses
the label to select the refurbishment variant (1/2/3) within it -- see
``nl_archetype_mapper``'s module docstring.

The raw RIVM energy-labels GeoPackage is not bundled with the
repository, so ``map_buildings`` cannot simply be re-run. This script
migrates the stored columns instead, losslessly: for label-matched rows,
the stored class *is* the label-implied class, and the real construction
year is also stored -- everything the new variant selection needs.

Usage::

    python scripts/refresh_nl_archetype_variants.py
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from buem.buildings.datasources.nl_archetype_mapper import (
    label_to_refurbishment_variant,
    year_to_construction_class,
)
from buem.buildings.mapping.tabula_helpers import lookup_tabula_archetype

_REPO_ROOT = Path(__file__).resolve().parent.parent
_DATA_DIR = _REPO_ROOT / "src" / "buem" / "data" / "buildings" / "netherlands"
_BUILDINGS_CSV = _DATA_DIR / "lod2_building_feature.csv"


def main() -> None:
    buildings = pd.read_csv(_BUILDINGS_CSV)
    tabula = pd.read_csv(_DATA_DIR / "tabula.csv", na_values=["NULL"])
    tabula = tabula[tabula["Code_Country"] == "NL"]

    variants: list[int] = []
    n_relinked = 0
    for idx, row in buildings.iterrows():
        if not row.get("is_residential") or not row.get("matched_via_label"):
            variants.append(1)
            continue

        label_class = row["construction_year_class"]  # label-implied under the old semantics
        year_class = year_to_construction_class(row.get("construction_year"))
        if year_class is None or pd.isna(label_class):
            variants.append(1)
            continue

        variant = label_to_refurbishment_variant(year_class, str(label_class))
        variants.append(variant)

        tabula_row = lookup_tabula_archetype(
            row["building_type"], year_class.split(".")[1], "NL",
            sheet=tabula, variant_number=variant,
        )
        if tabula_row is None:
            continue
        buildings.at[idx, "construction_year_class"] = year_class
        buildings.at[idx, "tabula_variant_code_id"] = float(tabula_row["id"])
        buildings.at[idx, "tabula_variant_code"] = str(tabula_row["Code_BuildingVariant"])
        n_relinked += 1

    buildings["refurbishment_variant"] = variants
    buildings.to_csv(_BUILDINGS_CSV, index=False)

    counts = buildings.loc[buildings["is_residential"] == True, "refurbishment_variant"].value_counts()  # noqa: E712
    print(f"Re-linked {n_relinked} label-matched buildings; variant counts:\n{counts.to_string()}")


if __name__ == "__main__":
    main()
