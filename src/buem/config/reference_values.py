"""Loader for ``src/buem/data/reference/dhw_cooking_constants.csv`` -- the
single, user-editable point of configuration for DHW/gas-cooking's
deterministic "physical constant"-style values, mirroring occupancy's own
``households/data/dhw_tapping_categories.csv`` pattern (see
``scripts/extract_dhw_reference_values.py``'s docstring for the full
rationale and provenance).

``buem.thermal.dhw_cooking`` derives its module-level constants from this
loader at import time (so `from buem.thermal.dhw_cooking import
DHW_DELTA_T_K` etc. keeps working exactly as before -- this module changes
*where the number comes from*, not the public API). Editing a value in the
CSV and reimporting is sufficient; no Python code changes needed.
"""

from __future__ import annotations

import csv
from functools import lru_cache
from importlib.resources import files

_PACKAGE = "buem.data"
_RESOURCE = "reference/dhw_cooking_constants.csv"


@lru_cache(maxsize=1)
def load_dhw_cooking_constants() -> dict[str, float]:
    """Load ``dhw_cooking_constants.csv`` as a ``{name: value}`` dict.

    Cached (the file is read once per process) -- this is meant to back
    module-level constants resolved at import time, not re-read per call.
    Raises ``ValueError`` naming the problem if a hand-edit breaks the
    file's expected shape (a non-numeric ``value`` cell, a missing
    ``name``/``value`` column), the same "fail loudly at load time"
    convention occupancy's ``load_tapping_categories()`` already
    establishes for this kind of user-editable reference table.
    """
    target = files(_PACKAGE).joinpath(_RESOURCE)
    with target.open("r", encoding="utf-8") as handle:
        reader = csv.DictReader(
            (line for line in handle if not line.lstrip().startswith("#")),
        )
        if reader.fieldnames is None or {"name", "value"} - set(reader.fieldnames):
            raise ValueError(
                f"{_RESOURCE} is missing required columns 'name'/'value' "
                f"(found: {reader.fieldnames})"
            )
        values: dict[str, float] = {}
        for row in reader:
            name = row["name"].strip()
            try:
                values[name] = float(row["value"])
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    f"{_RESOURCE}: row {name!r} has a non-numeric value "
                    f"{row['value']!r}"
                ) from exc
    if not values:
        raise ValueError(f"{_RESOURCE} contains no data rows")
    return values


__all__ = ["load_dhw_cooking_constants"]
