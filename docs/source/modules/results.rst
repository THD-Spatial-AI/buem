results — Plotting & Diagnostics
=================================

:Source: ``buem/results/standard_plots.py``

.. warning::
   **Currently broken/missing.** ``src/buem/results/`` has no Python
   module at all today (only a ``.model_cache/`` cache directory) — the
   ``standard_plots.py``/``PlotVariables`` described below don't exist in
   the current codebase, even though ``buem/main.py`` still imports
   ``buem.results.standard_plots.PlotVariables`` (the exact
   ``ModuleNotFoundError`` tracked in the repo root ``CLAUDE.md``'s "Open
   follow-ups"). This page documents the *intended* design as it existed
   before that refactor, for whoever picks this back up — update it once
   the module is actually reimplemented, not before.

Purpose (intended)
-------------------

Produce diagnostic plots from thermal-model output.

PlotVariables (intended)
-------------------------

``plot_variables(model_heat, model_cool, period)``

Creates a three-panel figure:

.. list-table::
   :header-rows: 1
   :widths: 10 20 70

   * - Panel
     - Y-axis
     - Series
   * - 1
     - °C
     - T_m, T_sur, T_air, comfort bounds, T_external
   * - 2
     - kWh/h
     - Heating demand, Cooling demand
   * - 3
     - kWh/h
     - Solar gains through windows, Solar gains through opaque elements

The ``period`` argument selects the aggregation window (``'day'``,
``'month'``, or ``'year'``).

Summary statistics (total energy, peak load) are computed and printed
alongside the plot.
