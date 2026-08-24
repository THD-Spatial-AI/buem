"""
Dutch natural gas -> useful heat conversion, for comparing CBS's real
regional gas-consumption statistics (``cbs_reference``, m3/year, *total*
household gas) against ``ModelBUEM``'s simulated heating demand (kWh,
*space heating only*).

Deliberately three separate, independently-documented, independently-
adjustable constants rather than one collapsed ratio -- each has its own
provenance and its own uncertainty, and collapsing them would hide
exactly where a disagreement should be resolved:

1. **Calorific value** (``GAS_CALORIFIC_VALUE_KWH_PER_M3``): converts raw
   m3 to raw energy content. Not a judgment call -- this is the official
   Dutch standard (Gasunie/CBS "bovenwaarde", 35.17 MJ/m3 = 9.769 kWh/m3),
   used by every Dutch energy supplier for billing and by CBS itself for
   its own published conversions. Not the "common ~10 kWh/m3 rule of
   thumb" some consumer sites use loosely.

2. **Space-heating share** (``SPACE_HEATING_SHARE_OF_GAS``): CBS's own
   81528NED gas figure is *total* household gas -- space heating **and**
   domestic hot water **and** cooking combined. Where ``ModelBUEM``
   simulates space heating only and carries no DHW/cooking output of its
   own, this share has to be applied to strip the CBS side down to a
   comparable space-heating-only figure. CBS's own 2016 national
   breakdown (the most authoritative match available, being the same
   organization as 81528NED itself): 78% heating / 20% hot water / 2%
   cooking. A single national average applied uniformly across housing
   types -- a real per-type split is not published anywhere found and
   likely varies (a bigger detached home's DHW share is probably
   proportionally smaller than a small apartment's) -- flagged as the
   least-verified of the three factors precisely because it is a blended
   average, not because the source figure itself is weak.

3. **Boiler efficiency** (``BOILER_EFFICIENCY_UPPER_VALUE``): gas energy
   *input* is not useful heat *delivered* -- a modern HR (condensing)
   boiler recovers ~90-96% of the upper calorific value as useful heat;
   the real Dutch housing stock is a mix of boiler ages, so a single
   blended figure here is the most uncertain of the three (an older,
   non-condensing boiler in an unrenovated pre-1992 home runs
   meaningfully lower than 90%). Set to a round, clearly-labeled 0.90 as
   a starting assumption representing "typical modern condensing
   boiler", not a stock-weighted average -- the single factor here most
   worth revisiting with better data before trusting the comparison
   closely.

Each stage is reported separately by ``gas_m3_to_useful_heat_kwh()`` so a
caller (or a report reader) can see exactly where the chain runs to, not
just the final number.
"""

from __future__ import annotations

from dataclasses import dataclass

from buem.config.reference_values import load_dhw_cooking_constants
from buem.thermal.dhw_cooking import (
    COOKING_SHARE_OF_GAS,
    DHW_SHARE_OF_GAS,
    SPACE_HEATING_SHARE_OF_GAS,
)

# Re-exported from buem.thermal.dhw_cooking rather than defined here --
# these three CBS-2016-sourced shares are also consumed directly by
# ModelBUEM's DHW/cooking post-processing, so `dhw_cooking` is the single
# source of truth; this module keeps the names importable from here too
# (`gas_conversion.SPACE_HEATING_SHARE_OF_GAS` etc.) for backward
# compatibility with existing callers/tests. Full provenance lives on the
# constants themselves at their canonical home.

# Same single-point-of-configuration CSV as dhw_cooking.py's constants
# (src/buem/data/reference/dhw_cooking_constants.csv) -- these two live in
# the same file, read directly here rather than re-exported through
# dhw_cooking.py since they are gas-conversion-specific, not DHW/cooking-
# energy math. Edit the CSV to change either; no Python change needed.
_CONSTANTS = load_dhw_cooking_constants()

GAS_CALORIFIC_VALUE_KWH_PER_M3 = _CONSTANTS["GAS_CALORIFIC_VALUE_KWH_PER_M3"]
"""Official Dutch natural gas upper calorific value (35.17 MJ/m3, the
Slochteren/G-gas billing standard). Source: Gasunie/CBS, cross-checked
against independent Dutch energy-supplier references. Not the fuzzy
"~10 kWh/m3" figure some consumer sites use."""

BOILER_EFFICIENCY_UPPER_VALUE = _CONSTANTS["BOILER_EFFICIENCY_UPPER_VALUE"]
"""Assumed fraction of gas's upper-calorific-value energy content
delivered as useful heat, i.e. after real boiler conversion losses.
~90-96% is typical for a modern HR (condensing) boiler on the upper
value; this is a round, explicitly-labeled starting assumption for
"typical modern boiler", not a stock-weighted average across the real
mix of boiler ages in the Dutch housing stock -- the single factor here
most worth revisiting with better data (see module docstring)."""


@dataclass(frozen=True)
class GasToHeatBreakdown:
    """The conversion chain's result at every stage, not just the end --
    see module docstring for why."""

    gas_m3_per_year: float
    gross_gas_energy_kwh: float          # stage 1: raw calorific content, all end-uses
    space_heating_gas_energy_kwh: float  # stage 2: heating-only share of that
    useful_heat_kwh: float               # stage 3: after boiler efficiency -- comparable to buem's heating_kWh


def gas_m3_to_useful_heat_kwh(
    gas_m3_per_year: float,
    *,
    calorific_value: float = GAS_CALORIFIC_VALUE_KWH_PER_M3,
    space_heating_share: float = SPACE_HEATING_SHARE_OF_GAS,
    boiler_efficiency: float = BOILER_EFFICIENCY_UPPER_VALUE,
) -> GasToHeatBreakdown:
    """Convert a real CBS gas-consumption figure (m3/year, total
    household use) into an estimate of useful space-heating energy
    delivered (kWh/year) -- the quantity comparable to ``ModelBUEM``'s
    own simulated ``heating_kWh`` output. Every stage's own default comes
    from this module's top-level constants; pass overrides to explore
    sensitivity without editing them.
    """
    gross = gas_m3_per_year * calorific_value
    space_heating_gas = gross * space_heating_share
    useful_heat = space_heating_gas * boiler_efficiency
    return GasToHeatBreakdown(
        gas_m3_per_year=gas_m3_per_year,
        gross_gas_energy_kwh=gross,
        space_heating_gas_energy_kwh=space_heating_gas,
        useful_heat_kwh=useful_heat,
    )


__all__ = [
    "BOILER_EFFICIENCY_UPPER_VALUE",
    "COOKING_SHARE_OF_GAS",
    "DHW_SHARE_OF_GAS",
    "GAS_CALORIFIC_VALUE_KWH_PER_M3",
    "SPACE_HEATING_SHARE_OF_GAS",
    "GasToHeatBreakdown",
    "gas_m3_to_useful_heat_kwh",
]
