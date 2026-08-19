"""One-time, reproducible extraction of real DHW/cooking reference
constants into ``src/buem/data/reference/dhw_cooking_constants.csv``.

Not part of the installed ``buem`` package -- a dev-only tool, run once
(or re-run if the source workbook is ever replaced), mirroring
occupancy's own ``scripts/extract_dhw_tapping_categories.py`` /
``extract_crest_tpm.py`` pattern exactly (same UU-BUEM org convention).

Consolidates the deterministic "physical constant"-style values used by
`buem.thermal.dhw_cooking`/`buem.analysis.netherlands.gas_conversion`
into one editable table, the same way occupancy's
``dhw_tapping_categories.csv`` centralizes its own deterministic values
-- see ``buem.config.reference_values`` for the loader this feeds.

**Requires** ``openpyxl`` (not a runtime/dev dependency of buem itself --
install ad hoc: ``pip install openpyxl`` before running this script).

**Source**: ``src/buem/data/reference/Demo_EN_12831-3_DHW_needs_2021-09-02.xlsx``
(EPB Center's free EN 12831-3:2017 demonstration spreadsheet), present
locally but **gitignored, not committed** -- its EPB Center redistribution
license hasn't been verified, the same posture this repo already takes
with occupancy's CREST workbooks (CC BY-NC-ND, also not redistributed).
Obtain it directly from https://epb.center/document/demo-en-12831-3/ if
missing locally, and place it at the path above before running this
script.

**What this reads**:

- ``Method_input`` sheet -- "Operating conditions data": delivery/tap
  water temperature (row labelled "Delivery water temperature", column D)
  and cold-mains temperature ("Cold water temperature", column D).
- Same sheet -- "Needs definition based on water volume" -> "It is a
  dwelling" block: the worked single-family-dwelling example's Annex
  Table B.5 volume ("Specific need", column D, "l/p day") and its own
  paired reference hot/cold-water temperatures ("Reference hot water
  temperature"/"Reference cold water temperature", column D).

**Values NOT read from the workbook** (kept as separately-documented,
independently-sourced constants in the output CSV rather than invented
matches for workbook cells that don't exist): the CBS 2016 gas-share
splits (heating/DHW/cooking), the Dutch gas calorific value, the boiler-
efficiency assumption, and the (deliberately superseded, kept for
reference) NTA 8800 figure -- see each row's own ``source`` value.

Usage::

    python scripts/extract_dhw_reference_values.py
"""

from __future__ import annotations

import csv
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_WORKBOOK_PATH = _REPO_ROOT / "src" / "buem" / "data" / "reference" / "Demo_EN_12831-3_DHW_needs_2021-09-02.xlsx"
_OUTPUT_PATH = _REPO_ROOT / "src" / "buem" / "data" / "reference" / "dhw_cooking_constants.csv"

_EN_12831_3_SOURCE = (
    "EN 12831-3:2017 (via EPB Center's free Demo_EN_12831-3_DHW_needs_"
    "2021-09-02.xlsx, Method_input sheet)"
)


def _read_workbook_values() -> dict[str, float]:
    """Read the four real Method_input cells this extraction needs.
    Deliberately narrow (four specific labelled rows), not a generic
    sheet dump -- see this module's own docstring for exactly which."""
    import openpyxl

    wb = openpyxl.load_workbook(_WORKBOOK_PATH, data_only=True, read_only=True)
    ws = wb["Method_input"]

    wanted = {
        "Delivery water temperature": "delivery_temp_c",
        "Cold water temperature": "cold_mains_temp_c",
        "Reference hot water temperature": "reference_hot_temp_c",
        "Reference cold water temperature": "reference_cold_temp_c",
        "Specific need": "liters_per_person_day",
    }
    # Exact-label matching disambiguates real "Specific need" (the
    # dwelling l/p-day row we want) from the sheet's other, differently-
    # worded rows ("Specific energy need", "Specific need when not
    # dwelling") -- confirmed by direct inspection this session, only one
    # row in this sheet is labelled exactly "Specific need".
    # Row layout (confirmed by direct inspection): 0=Name, 1=Symbol,
    # 2=Software name, 3=Unit, 4=Value.
    found: dict[str, float] = {}
    for row in ws.iter_rows(min_row=1, max_row=40, max_col=5):
        label = row[0].value
        if isinstance(label, str) and label.strip() in wanted:
            key = wanted[label.strip()]
            found.setdefault(key, float(row[4].value))
    missing = set(wanted.values()) - set(found)
    if missing:
        raise ValueError(f"Expected labelled rows not found in Method_input: {sorted(missing)}")
    return found


def main() -> None:
    if not _WORKBOOK_PATH.exists():
        raise FileNotFoundError(
            f"{_WORKBOOK_PATH} not found -- download it from "
            "https://epb.center/document/demo-en-12831-3/ and place it there "
            "before running this script (see this module's docstring)."
        )
    values = _read_workbook_values()
    delta_t_operating = values["delivery_temp_c"] - values["cold_mains_temp_c"]
    delta_t_reference = values["reference_hot_temp_c"] - values["reference_cold_temp_c"]

    rows = [
        {
            "name": "WATER_DENSITY_KG_PER_L", "value": 1.0, "unit": "kg/L",
            "source": "Standard approximation, close enough across DHW temperature range",
        },
        {
            "name": "WATER_SPECIFIC_HEAT_KJ_PER_KGK", "value": 4.186, "unit": "kJ/(kg*K)",
            "source": "Standard textbook value",
        },
        {
            "name": "DHW_DELTA_T_K", "value": round(delta_t_operating, 2), "unit": "K",
            "source": (
                f"{_EN_12831_3_SOURCE}: real operating-conditions delivery/cold-mains "
                f"temperatures ({values['delivery_temp_c']}C - {values['cold_mains_temp_c']}C)"
            ),
        },
        {
            "name": "DHW_DELTA_T_K_REFERENCE", "value": round(delta_t_reference, 2), "unit": "K",
            "source": (
                f"{_EN_12831_3_SOURCE}: reference-need-normalization temperatures "
                f"({values['reference_hot_temp_c']}C - {values['reference_cold_temp_c']}C), "
                "distinct from the real operating-conditions pair above"
            ),
        },
        {
            "name": "DHW_LITERS_PER_PERSON_DAY_EN12831_3",
            "value": values["liters_per_person_day"], "unit": "L/person/day",
            "source": f"{_EN_12831_3_SOURCE}: Annex Table B.5, single family dwellings AVG",
        },
        {
            "name": "DHW_ANNUAL_KWH_PER_PERSON_NTA8800", "value": 545.0, "unit": "kWh/person/year",
            "source": (
                "NTA 8800 secondary citation (WebSearch, 2026-08-17) -- kept for reference "
                "only, NOT the default: fails its own internal-consistency check against "
                "the separately-cited 40.3 L/person/day figure (see dhw_cooking.py docstring)"
            ),
        },
        {
            "name": "SPACE_HEATING_SHARE_OF_GAS", "value": 0.78, "unit": "fraction",
            "source": "CBS 2016 national household gas breakdown (heating/DHW/cooking)",
        },
        {
            "name": "DHW_SHARE_OF_GAS", "value": 0.20, "unit": "fraction",
            "source": "CBS 2016 national household gas breakdown (heating/DHW/cooking)",
        },
        {
            "name": "COOKING_SHARE_OF_GAS", "value": 0.02, "unit": "fraction",
            "source": "CBS 2016 national household gas breakdown (heating/DHW/cooking)",
        },
        {
            "name": "GAS_CALORIFIC_VALUE_KWH_PER_M3", "value": 9.769, "unit": "kWh/m3",
            "source": "Gasunie/CBS Slochteren G-gas upper calorific value standard (35.17 MJ/m3)",
        },
        {
            "name": "BOILER_EFFICIENCY_UPPER_VALUE", "value": 0.90, "unit": "fraction",
            "source": "Typical modern HR (condensing) boiler assumption, round starting value",
        },
    ]

    with _OUTPUT_PATH.open("w", newline="", encoding="utf-8") as handle:
        handle.write(
            "# Deterministic DHW/gas-cooking reference constants -- single point of\n"
            "# configuration, mirroring occupancy's households/data/dhw_tapping_categories.csv\n"
            "# pattern. Loaded by buem.config.reference_values.load_dhw_cooking_constants().\n"
            "# Generated by scripts/extract_dhw_reference_values.py -- re-run that script to\n"
            "# regenerate the EN-12831-3-sourced rows from the source workbook; other rows\n"
            "# (CBS shares, calorific value, boiler efficiency, the legacy NTA 8800 figure) are\n"
            "# independently-documented constants the script also writes, not workbook reads --\n"
            "# see the script's own docstring for exactly which is which. Hand-editing any\n"
            "# value directly in this file is supported and expected -- update the `source`\n"
            "# column too if you do, so provenance stays honest.\n"
        )
        writer = csv.DictWriter(handle, fieldnames=["name", "value", "unit", "source"])
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote {len(rows)} rows to {_OUTPUT_PATH}")


if __name__ == "__main__":
    main()
