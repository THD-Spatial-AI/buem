Heeten vs. CBS — gas-consumption validation
=============================================

:Date: 2026-08-20 (first population-complete run for this region)
:Region: Heeten (Overijssel), municipality of Raalte (CBS ``GM0177``)
:Buildings: 2,671 residential + 3 service — the whole population
:Result: 2,674 simulated, 1 skipped (sub-threshold structure), 0 errors
:Reference: CBS table 81528NED, period ``2018JJ00``
:Weather: merra-2, 2018, one fetch at the region centroid (52.329 N, 6.280 E)
:Model: same configuration as :doc:`loenen_cbs` (comfort band 18-21 degC,
        window-to-wall ratio 0.5, ``NL.Window.Ins.01`` corrected to HR++,
        the three country-level reference tables copied from
        ``netherlands/Loenen/``) -- **except** dwelling counts and
        refurbishment-variant selection, see `Data quality`_ below.

Reproduce with:

.. code-block:: bash

   python scripts/repair_nl_dwelling_counts.py src/buem/data/buildings/netherlands/Heeten

   python -m buem.analysis.batch --source csv \
       --data-dir src/buem/data/buildings/netherlands/Heeten \
       --country NL --workers 16 --resume \
       --output results/heeten.parquet

   python -c "
   from buem.analysis.netherlands.validation import per_building_ratios, stratified_ratio_table
   r = per_building_ratios('results/heeten.parquet', region_code='GM0177', period='2018JJ00', metric='total')
   print(stratified_ratio_table(r))
   "


Headline
-----------

Two metrics, not one -- see :doc:`loenen_cbs`'s own "Two ways to average"
section for the group-level version of this distinction. ``total`` is
(heating + dhw + cooking) against CBS's unstripped gas-total; ``heating-only``
is space heating alone against CBS's gas figure with the national 78%
space-heating share stripped off (the metric behind Loenen's previously-
published median).

.. list-table::
   :header-rows: 1
   :widths: 30 14 20 20 16

   * - Metric
     - Buildings
     - Median
     - Mean
     - Count-weighted

   * - total
     - 2,671
     - 2.03
     - 2.50
     - 2.50

   * - heating-only
     - 2,671
     - 2.07
     - 2.62
     - --

Both sit well above Loenen's current 0.98 (heating-only median) / 1.78-1.79
(count-weighted). This is **not** a different model behaviour on the same
data quality -- see `Data quality`_ below for why.


All 2,671 residential buildings, by type and construction-year class
-------------------------------------------------------------------------

.. list-table::
   :header-rows: 1
   :widths: 10 16 10 16 16

   * - type
     - era
     - n
     - median (total)
     - median (heating-only)
   * - SFH
     - NL.01 (<=1964)
     - 522
     - 3.03
     - 3.36
   * - SFH
     - NL.02 (1965-74)
     - 265
     - 3.02
     - 3.34
   * - SFH
     - NL.03 (1975-91)
     - 492
     - 2.15
     - 2.20
   * - SFH
     - NL.04 (1992-2005)
     - 363
     - 1.33
     - 1.22
   * - SFH
     - NL.05 (2006-14)
     - 263
     - 0.94
     - 0.75
   * - SFH
     - NL.06 (2015-)
     - 164
     - 0.87
     - 0.65
   * - TH
     - NL.01 (<=1964)
     - 33
     - 4.46
     - 4.97
   * - TH
     - NL.02 (1965-74)
     - 45
     - 2.53
     - 2.51
   * - TH
     - NL.03 (1975-91)
     - 163
     - 4.24
     - 4.66
   * - TH
     - NL.04 (1992-2005)
     - 99
     - 2.29
     - 2.25
   * - TH
     - NL.05 (2006-14)
     - 135
     - 1.54
     - 1.29
   * - TH
     - NL.06 (2015-)
     - 72
     - 1.45
     - 1.14
   * - MFH
     - NL.01 (<=1964)
     - 24
     - 4.25
     - 4.19
   * - MFH
     - NL.02 (1965-74)
     - 4
     - 15.52
     - 18.27
   * - MFH
     - NL.03 (1975-91)
     - 9
     - 10.57
     - 12.09
   * - MFH
     - NL.04 (1992-2005)
     - 3
     - 5.43
     - 5.66
   * - MFH
     - NL.05 (2006-14)
     - 2
     - 1.72
     - 1.02
   * - MFH
     - NL.06 (2015-)
     - 3
     - 1.65
     - 0.93
   * - AB
     - NL.01 (<=1964)
     - 1
     - 3.78
     - 3.60
   * - AB
     - NL.02 (1965-74)
     - 1
     - 18.37
     - 21.83
   * - AB
     - NL.03 (1975-91)
     - 1
     - 2.16
     - 1.57
   * - AB
     - NL.04 (1992-2005)
     - 1
     - 1.40
     - 0.63
   * - AB
     - NL.05 (2006-14)
     - 5
     - 1.40
     - 0.62
   * - AB
     - NL.06 (2015-)
     - 1
     - 1.17
     - 0.34

Same shape as Loenen -- the ratio falls toward 1x in the newest construction
eras across every type -- just uniformly higher, consistent with the
as-built-only envelope explanation below rather than a different underlying
model behaviour.


Service buildings
---------------------

.. list-table::
   :header-rows: 1
   :widths: 20 20 10 20 20

   * - type
     - era
     - n
     - mean kWh/m2
     - median kWh/m2
   * - warehouse
     - unknown
     - 3
     - 289.4
     - 289.2

``construction_year_class`` is never populated for service buildings (only
the residential TABULA-era classification stage writes it) -- reported as
"unknown" rather than silently dropped. Consistent with Loenen's 286 kWh/m2
(2 warehouses) and its own previously-published 273/285 kWh/m2 figures.

Reverified live, not assumed: the ``occupancy.ServiceBuildingProfile``
connection both regions' service buildings depend on is still working
against the currently-installed package (v5.0.0) --
``tests/test_building_types.py::test_dummy_fixture_runs_end_to_end[...office...]``
and ``tests/test_service_buildings.py::
test_bundled_reference_tables_cover_every_occupancy_service_type`` both
exercise it directly and pass, independent of these batch runs.


.. _data-quality:

Data quality
---------------

Heeten's building data is not at the same maturity as Loenen's. Its
geometry and classification are real and were already verified to
generalize cleanly from Loenen's pipeline with zero code changes (see
``docs/source/modules/netherlands.rst``'s "Multiple regions" section), but
two corrections applied to Loenen's data specifically were never run
against Heeten's, because both need a raw RIVM energy-labels/dwelling-count
source (``bag_pand_id`` / ``aant_verblijfsobj`` / ``dominant_label``) that
is not present on this machine.

**Dwelling counts** -- not merely wrong in places, as 167 of Loenen's were
(see issue #6), but **entirely absent**: no ``residential_units`` column
existed before this run. Worked around with the same floor-area fallback
issue #6 introduced (``nl_archetype_mapper.repair_dwelling_counts()``),
applied to the whole population rather than just the exceptions it was
designed for: 349 of 2,671 buildings (13.1%) got a floor-area estimate,
the remaining 2,322 default to 1 dwelling.

**Refurbishment variant** -- 638 of 2,671 buildings (23.9%, matching
Loenen's own real-label coverage almost exactly) have a real matched RIVM
energy label, but **none of them use it**: every Heeten building simulates
TABULA's as-built envelope. The label class (A-G) needed to select
standard-vs-nZEB was never persisted when Heeten's ``map_buildings()`` ran
-- its data predates that feature. Unlike the dwelling count, there is no
floor-area-style fallback for this.

A local CityJSON geometry export for Heeten was checked
(``D:\test\envelope-extractor\data\envelope\heeten.city.json``) -- it
carries only 3D BAG attributes (roof type, wall/roof/ground areas,
heights, construction year), no RIVM label or dwelling-count fields, so it
does not close this gap.

**Expected size of the effect**, from Loenen's own history: migrating just
refurbishment-variant selection (before the window-U or dwelling-count
fixes existed) moved its label-matched subset's mean ratio from 4.96 to
4.22. Heeten is still missing that migration entirely, on top of the
dwelling-count gap -- consistent with, and a plausible full explanation
for, why its ratio sits closer to where Loenen's stood earlier in this
validation effort than to its current, corrected figure. Tracked in
`issue #13 <https://github.com/UU-BUEM/buem/issues/13>`_ rather than fixed
here.


Combined with Loenen
------------------------

Pooling both regions' per-building ratios directly:

.. list-table::
   :header-rows: 1
   :widths: 26 18 18 18 20

   * - Metric
     - Loenen median
     - Heeten median
     - Combined median
     - Combined n

   * - total
     - 0.98 (see note)
     - 2.03
     - 1.55
     - 5,772
   * - heating-only
     - 0.98
     - 2.07
     - 1.42
     - 5,772

.. note::
   Loenen's own headline in :doc:`loenen_cbs` (0.98) uses the
   heating-only metric; its ``total``-metric median is 1.18. Both are
   reported here for a like-for-like comparison against Heeten's two
   metrics.

**Not a population-representative figure to quote on its own.** The
combined median (1.42-1.55) mixes a fully-corrected region with one still
missing two of the three corrections that took Loenen from a mid-3x ratio
toward parity -- it describes neither region accurately. Use Loenen's own
numbers as the current read of model performance, and Heeten's as a
geometry/classification pipeline check (which it passes cleanly) rather
than a second independent CBS validation point, until issue #13 closes.
