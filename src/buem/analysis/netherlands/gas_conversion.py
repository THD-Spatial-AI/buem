"""
Dutch natural gas -> useful heat conversion, for comparing CBS's real
regional gas-consumption statistics (``cbs_reference``, m3/year, *total*
household gas) against ``ModelBUEM``'s simulated heating demand (kWh,
*space heating only*).

Deliberately three separate, independently-documented, independently-
adjustable constants rather than one collapsed ratio (per the user,
2026-08-18: "Why value of gas -> heat conversion are you considering,
let me know?") -- each has its own provenance and its own uncertainty,
and collapsing them would hide exactly where a disagreement should be
resolved:

1. **Calorific value** (``GAS_CALORIFIC_VALUE_KWH_PER_M3``): converts raw
   m3 to raw energy content. Solid, not really a judgment call -- this is
   the official Dutch standard (Gasunie/CBS "bovenwaarde", 35.17 MJ/m3 =
   9.769 kWh/m3), used by every Dutch energy supplier for billing and by
   CBS itself for its own published conversions. Verified via web search
   against multiple independent Dutch sources, 2026-08-18 -- not
   invented, not the "common ~10 kWh/m3 rule of thumb" some consumer
   sites use loosely.

2. **Space-heating share** (``SPACE_HEATING_SHARE_OF_GAS``): CBS's own
   81528NED gas figure is *total* household gas -- space heating **and**
   domestic hot water **and** cooking. ``ModelBUEM`` currently simulates
   space heating only (checked directly: ``q_w_nd``, TABULA's own
   hot-water-demand parameter, is carried in ``ThermalProperties`` but
   never actually read by ``model_buem.sim_model()`` -- no DHW
   simulation exists to compare against, so it must be subtracted from
   the CBS side instead). CBS's own 2016 national breakdown (the most
   authoritative match, since it's the same organization as 81528NED
   itself): 78% heating / 20% hot water / 2% cooking. A single national
   average applied uniformly across housing types -- the real per-type
   split isn't published anywhere found during this session's research,
   and likely varies (a bigger detached home's DHW share is probably
   proportionally smaller than a small apartment's) -- flagged as the
   least-verified of the three factors precisely because it's a blended
   average, not because the *source figure* itself is weak.

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

GAS_CALORIFIC_VALUE_KWH_PER_M3 = 9.769
"""Official Dutch natural gas upper calorific value (35.17 MJ/m3, the
Slochteren/G-gas billing standard). Source: Gasunie/CBS, cross-checked
against multiple independent Dutch energy-supplier references,
2026-08-18. Not the fuzzy "~10 kWh/m3" figure some consumer sites use."""

SPACE_HEATING_SHARE_OF_GAS = 0.78
"""Fraction of a typical Dutch household's total gas consumption used
for space heating specifically (vs. domestic hot water ~20%, cooking
~2%). Source: CBS's own 2016 national household energy breakdown -- a
blended national average, not housing-type-specific. See module
docstring for why this, not the boiler-efficiency factor, is the one
most likely to need real per-type data if this comparison is refined."""

BOILER_EFFICIENCY_UPPER_VALUE = 0.90
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
    "GAS_CALORIFIC_VALUE_KWH_PER_M3",
    "SPACE_HEATING_SHARE_OF_GAS",
    "GasToHeatBreakdown",
    "gas_m3_to_useful_heat_kwh",
]
