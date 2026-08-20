Heeten vs. CBS — gas-consumption validation
=============================================

:Date: 2026-08-20 (first run), corrected same day once the raw RIVM
       energy-labels GeoPackage was located (see `What changed`_)
:Region: Heeten (Overijssel), municipality of Raalte (CBS ``GM0177``)
:Buildings: 2,671 residential + 3 service — the whole population
:Result: 2,674 simulated, 1 skipped (sub-threshold structure), 0 errors
:Reference: CBS table 81528NED, period ``2018JJ00``
:Weather: merra-2, 2018, one fetch at the region centroid (52.329 N, 6.280 E)
:Model: same configuration as :doc:`loenen_cbs` (comfort band 18-21 degC,
        window-to-wall ratio 0.5, ``NL.Window.Ins.01`` corrected to HR++,
        the three country-level reference tables copied from
        ``netherlands/Loenen/``), **including** real dwelling counts and
        refurbishment-variant selection — see `What changed`_.

Reproduce with:

.. code-block:: bash

   python scripts/reclassify_with_rivm_labels.py src/buem/data/buildings/netherlands/Heeten \
       --gpkg-path /path/to/energielabels_2025.gpkg

   python -m buem.analysis.batch --source csv \
       --data-dir src/buem/data/buildings/netherlands/Heeten \
       --country NL --workers 18 \
       --output results/heeten.parquet

   python -c "
   from buem.analysis.netherlands.validation import per_building_ratios, stratified_ratio_table
   r = per_building_ratios('results/heeten.parquet', region_code='GM0177', period='2018JJ00', metric='total')
   print(stratified_ratio_table(r))
   "


What changed
---------------

The same-day first run of this validation (see git history for the
original numbers) found Heeten's building data missing two corrections
Loenen's had: no real per-building dwelling counts at all, and none of
its 638 label-matched buildings selecting a refurbished TABULA variant —
both need the raw RIVM energy-labels GeoPackage
(``bag_pand_id``/``aant_verblijfsobj``/``dominant_label``), which wasn't
found on this machine at the time.

It has since been located
(``D:\test\data\energy_labels\energielabels_2025\energielabels_2025.gpkg``,
the same nationwide 11.35M-row export Loenen's own data was built from —
confirmed by a direct query: all 2,671 Heeten buildings match, 638 with a
real label, exactly Heeten's already-recorded coverage). New
``scripts/reclassify_with_rivm_labels.py`` re-runs
``nl_archetype_mapper.map_buildings()`` — existing, unmodified code, doing
exactly what it always does — against the real GeoPackage and rewrites
Heeten's building table in place. Effect, in one pass:

.. list-table::
   :header-rows: 1
   :widths: 40 20 20

   * - Refurbishment variant
     - Before
     - After

   * - 1 — as built
     - 2,671 (100%)
     - 2,360 (88.4%)
   * - 2 — standard refurbishment
     - 0
     - 262 (9.8%)
   * - 3 — nZEB refurbishment
     - 0
     - 53 (2.0%)

Dwelling counts: 2,322 of 2,671 buildings now carry a real RIVM
``aant_verblijfsobj``-sourced count; the remaining 349 (13.1%) still use
the floor-area fallback (issue #6's mechanism), where the registered
count was implausible or absent even in the real RIVM data. Loenen's
building_type/neighbour_status/is_residential/matched_via_label/
residential_units were re-verified unchanged under the identical
pipeline (a real idempotency check, not assumed) — this only touched
Heeten.


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
     - 1.81
     - 2.37
     - 2.37
   * - heating-only
     - 2,671
     - 1.77
     - 2.46
     - --

A real, substantial improvement over the first run (median 2.03 -> 1.81
total, 2.07 -> 1.77 heating-only; count-weighted 2.50 -> 2.37) — but
**still well above Loenen's 0.98 (heating-only median) / 1.78-1.79
(count-weighted)**, not explained by the RIVM data gap this fix closed.
See `Residual gap, unexplained`_.


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
     - 585
     - 2.67
     - 2.91
   * - SFH
     - NL.02 (1965-74)
     - 256
     - 2.52
     - 2.72
   * - SFH
     - NL.03 (1975-91)
     - 484
     - 1.83
     - 1.81
   * - SFH
     - NL.04 (1992-2005)
     - 369
     - 1.15
     - 1.01
   * - SFH
     - NL.05 (2006-14)
     - 216
     - 0.84
     - 0.59
   * - SFH
     - NL.06 (2015-)
     - 159
     - 0.89
     - 0.68
   * - TH
     - NL.01 (<=1964)
     - 38
     - 3.82
     - 4.14
   * - TH
     - NL.02 (1965-74)
     - 61
     - 1.22
     - 0.88
   * - TH
     - NL.03 (1975-91)
     - 264
     - 2.42
     - 2.35
   * - TH
     - NL.04 (1992-2005)
     - 76
     - 2.39
     - 2.38
   * - TH
     - NL.05 (2006-14)
     - 40
     - 1.87
     - 1.72
   * - TH
     - NL.06 (2015-)
     - 68
     - 1.62
     - 1.37
   * - MFH
     - NL.01 (<=1964)
     - 31
     - 4.15
     - 4.06
   * - MFH
     - NL.02 (1965-74)
     - 6
     - 10.00
     - 11.37
   * - MFH
     - NL.03 (1975-91)
     - 2
     - 10.53
     - 12.04
   * - MFH
     - NL.04 (1992-2005)
     - 2
     - 3.68
     - 3.47
   * - MFH
     - NL.06 (2015-)
     - 4
     - 1.66
     - 0.95
   * - AB
     - NL.01 (<=1964)
     - 3
     - 1.25
     - 0.43
   * - AB
     - NL.02 (1965-74)
     - 1
     - 18.37
     - 21.83
   * - AB
     - NL.03 (1975-91)
     - 2
     - 1.18
     - 0.35
   * - AB
     - NL.04 (1992-2005)
     - 1
     - 1.22
     - 0.39
   * - AB
     - NL.05 (2006-14)
     - 1
     - 1.51
     - 0.76
   * - AB
     - NL.06 (2015-)
     - 2
     - 1.29
     - 0.49

Same shape as Loenen -- the ratio falls toward 1x in the newest
construction eras across every type, and every SFH/TH era's median
dropped from the first run once refurbishment credit applied. MFH's
NL.05 stratum (2 buildings in the first run) reclassified into other
eras once the real label class informed a small number of borderline
cases -- expected at this sample size, not a data error (see
`What changed`_'s idempotency note for Loenen, where the identical
pipeline reproduced its existing data exactly).


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

Unaffected by this fix (service buildings don't carry dwelling counts or
refurbishment variants) -- unchanged from the first run, still consistent
with Loenen's 286 kWh/m2 (2 warehouses).

Reverified live, not assumed: the ``occupancy.ServiceBuildingProfile``
connection both regions' service buildings depend on is still working
against the currently-installed package (v5.0.0) --
``tests/test_building_types.py::test_dummy_fixture_runs_end_to_end[...office...]``
and ``tests/test_service_buildings.py::
test_bundled_reference_tables_cover_every_occupancy_service_type`` both
exercise it directly and pass, independent of these batch runs.


.. _residual-gap-unexplained:

Residual gap, unexplained
------------------------------

Both regions now went through the identical pipeline against the same
real RIVM data — the difference between them (Heeten's 1.77-1.81 vs.
Loenen's 0.98-1.79, depending on metric) is no longer a data-quality
artifact, and is not yet explained. Candidates not yet checked:

- Real geometry/opening-synthesis quality differences between the two
  regions' underlying CityJSON extractions (Heeten's TABULA-match log
  shows more "no TABULA archetype resolved... synthesizing... from safe-
  default ratios" fallbacks than Loenen's per-building run logged — not
  yet quantified against Loenen's own rate).
- A genuine regional difference in Raalte's real gas consumption pattern
  vs. Apeldoorn's, independent of buem.
- Weather-point sensitivity: Heeten's own centroid (52.329N, 6.280E) is a
  different merra-2 cell than Loenen's (52.120N, 6.026E).

Tracked as a new issue rather than assumed to be one of the above.


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
     - 1.18 (0.98 heating-only)
     - 1.81
     - 1.44
     - 5,772
   * - heating-only
     - 0.98
     - 1.77
     - 1.32
     - 5,772

Both regions are now on equal methodological footing -- this is a real
population comparison, not one mixing a corrected region with an
uncorrected one as the first run did. It is not a single validated
"buem-vs-CBS" figure to quote on its own, though: it pools two distinct
municipalities against two distinct CBS reference figures, which is a
population statistic over the *combined sample*, not a statement about
either municipality individually or the model in general. Use each
region's own numbers (:doc:`loenen_cbs`, this page) for a claim about
that region; use the combined figure only to describe this specific
5,772-building sample.
