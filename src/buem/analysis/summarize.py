"""
Annual/monthly aggregation of ``provider_comparison.ProviderRunResult``s --
both the simulated heating/cooling/electricity demand and the raw weather
inputs (T/GHI/DHI/DNI) themselves, including pairwise GHI difference
metrics between providers.
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from buem.analysis.provider_comparison import ProviderRunResult


@dataclass
class DemandSummary:
    """Annual and monthly heating/cooling/electricity totals per provider."""

    annual_kWh: pd.DataFrame  # index: provider, columns: heating/cooling/elec
    monthly_kWh: pd.DataFrame  # index: month (1-12), columns: MultiIndex (metric, provider)


@dataclass
class WeatherSummary:
    """Annual/monthly weather-variable stats per provider, plus pairwise
    GHI difference metrics."""

    annual_stats: pd.DataFrame  # index: provider, columns: T_mean/T_min/T_max/GHI_sum/DNI_sum/DHI_sum
    monthly_mean: pd.DataFrame  # index: month, columns: MultiIndex (variable, provider)
    ghi_pairwise_diff: pd.DataFrame  # index: provider pair, columns: mean_abs_diff_Wm2, monthly totals in the same table's `pct_diff_*` columns


def summarize_demand(results: dict[str, ProviderRunResult]) -> DemandSummary:
    """Annual + monthly heating/cooling/electricity totals (kWh), one row
    per provider (annual) or per calendar month (monthly). Cooling is
    reported as a positive magnitude (buem's own internal sign convention
    is negative)."""
    annual_rows = {}
    monthly_frames = {}
    for provider, r in results.items():
        annual_rows[provider] = {
            "heating_kWh": float(r.heating_kW.sum()),
            "cooling_kWh": float(r.cooling_kW.abs().sum()),
            "elec_kWh": float(r.elec_kW.sum()),
        }
        df = pd.DataFrame({
            "heating_kWh": r.heating_kW,
            "cooling_kWh": r.cooling_kW.abs(),
            "elec_kWh": r.elec_kW,
        })
        df["month"] = df.index.month
        monthly_frames[provider] = df.groupby("month")[["heating_kWh", "cooling_kWh", "elec_kWh"]].sum()

    annual = pd.DataFrame(annual_rows).T
    annual.index.name = "provider"

    monthly = pd.concat(monthly_frames, axis=1, names=["provider", "metric"])
    monthly = monthly.reorder_levels(["metric", "provider"], axis=1).sort_index(axis=1)
    monthly.index.name = "month"

    return DemandSummary(annual_kWh=annual, monthly_kWh=monthly)


def summarize_weather(results: dict[str, ProviderRunResult]) -> WeatherSummary:
    """Annual/monthly T/GHI/DHI/DNI stats per provider, plus pairwise GHI
    difference metrics between every pair of providers -- directly
    answering "check T, GHI, DNI, and GHI difference between models"."""
    annual_rows = {}
    monthly_mean_frames = {}
    ghi_series: dict[str, pd.Series] = {}

    for provider, r in results.items():
        w = r.weather
        annual_rows[provider] = {
            "T_mean_degC": float(w["T"].mean()),
            "T_min_degC": float(w["T"].min()),
            "T_max_degC": float(w["T"].max()),
            "GHI_sum_kWh_m2": float(w["GHI"].sum() / 1000.0),
            "DNI_sum_kWh_m2": float(w["DNI"].sum() / 1000.0),
            "DHI_sum_kWh_m2": float(w["DHI"].sum() / 1000.0),
        }
        monthly = w.copy()
        monthly["month"] = monthly.index.month
        monthly_mean_frames[provider] = monthly.groupby("month")[["T", "GHI", "DNI", "DHI"]].mean()
        ghi_series[provider] = w["GHI"]

    annual = pd.DataFrame(annual_rows).T
    annual.index.name = "provider"

    monthly_mean = pd.concat(monthly_mean_frames, axis=1, names=["provider", "variable"])
    monthly_mean = monthly_mean.reorder_levels(["variable", "provider"], axis=1).sort_index(axis=1)
    monthly_mean.index.name = "month"

    ghi_pairwise_diff = _pairwise_ghi_diff(ghi_series)

    return WeatherSummary(annual_stats=annual, monthly_mean=monthly_mean, ghi_pairwise_diff=ghi_pairwise_diff)


def _pairwise_ghi_diff(ghi_series: dict[str, pd.Series]) -> pd.DataFrame:
    """Mean absolute hourly GHI difference (W/m2) and annual-total percent
    difference for every pair of providers.

    Compares by **position**, not by timestamp label: providers use
    genuinely different hour-labeling conventions (merra-2's index sits at
    the half-hour/interval-midpoint, era5-land/cosmo-rea6 on-the-hour --
    see ``weather_providers``'s own module docstring) that don't align via
    a plain pandas index subtraction (silently producing all-NaN results
    if attempted -- confirmed the hard way building this module). All
    series are guaranteed the same length, in chronological order, one row
    per hour of the same calendar year -- ``extract_provider_weather()``
    enforces exactly ``_expected_hours(year)`` rows per provider -- so a
    positional (array) comparison is the correct one here, not a bug
    worked around.
    """
    providers = list(ghi_series)
    rows = []
    for i, p1 in enumerate(providers):
        for p2 in providers[i + 1:]:
            a1, a2 = ghi_series[p1].to_numpy(), ghi_series[p2].to_numpy()
            mean_abs_diff = float(abs(a1 - a2).mean())
            total1, total2 = float(a1.sum()), float(a2.sum())
            pct_diff = (total1 - total2) / ((total1 + total2) / 2) * 100.0 if (total1 + total2) else 0.0
            rows.append({
                "pair": f"{p1} vs {p2}",
                "mean_abs_hourly_diff_Wm2": mean_abs_diff,
                "annual_total_pct_diff": pct_diff,
            })
    # A single-provider run has zero pairs -- pd.DataFrame([]) has no
    # columns at all, so set_index("pair") would raise KeyError. Build the
    # (empty) frame with the right columns/index name explicitly instead,
    # so callers (report.py, summarize_weather()'s own return value) get a
    # consistently-shaped, if empty, table rather than a crash.
    if not rows:
        return pd.DataFrame(
            columns=["mean_abs_hourly_diff_Wm2", "annual_total_pct_diff"],
        ).rename_axis("pair")
    return pd.DataFrame(rows).set_index("pair")


__all__ = ["DemandSummary", "WeatherSummary", "summarize_demand", "summarize_weather"]
