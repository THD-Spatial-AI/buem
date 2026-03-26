results — Plotting & Diagnostics
=================================

:Source: ``buem/results/standard_plots.py``

Purpose
-------

Produce diagnostic plots from thermal-model output.

PlotVariables
-------------

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
