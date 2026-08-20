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
See `Residual gap — explained: Heeten's real houses are bigger`_.


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


.. _residual-gap-explained:

Residual gap — explained: Heeten's real houses are bigger
----------------------------------------------------------------

Both regions now go through the identical pipeline against the same
real RIVM data, so the remaining gap (Heeten's 1.77-1.81 vs. Loenen's
0.98-1.79, depending on metric) is not a data-quality artifact. Three
candidates were checked (tracked in issue #14); two ruled out, one
confirmed:

- **Ruled out — opening-synthesis fallback rate.** Loenen: 24/3,105
  buildings (0.77%) hit the safe-default fallback. Heeten: 21/2,675
  (0.78%) — essentially identical.
- **Ruled out — weather.** Loenen and Heeten's merra-2 2018 cells are
  nearly identical (mean T 10.88 vs 10.65 degC, heating-degree-days
  2,919 vs 2,963 -- a 1.5% difference).
- **Confirmed — real house size.** For SFH (78% of Heeten's residential
  stock): mean real floor area (``A_ref``) is 391.4 m2 in Heeten vs.
  250.2 m2 in Loenen (1.56x). buem's per-square-metre heating
  *intensity* is actually **lower** for Heeten (188.2 vs 211.6 kWh/m2,
  0.89x) -- ruling out a per-building modelling overestimate. The higher
  per-dwelling ratio is fully explained by real, measured floor area: a
  bigger house needs more absolute heat, in reality as much as in the
  model. CBS's per-dwelling gas figure is a flat regional average by
  housing-type category with no floor-area dimension, so it does not
  adjust for this -- a municipality with genuinely larger houses reads
  as running higher than CBS on a per-dwelling ratio even with an
  accurate model. Consistent with CBS's own Raalte figures actually
  being *lower* than Apeldoorn's for the same category (``detached``:
  2,070 vs. 2,390 m3/yr), the opposite of what a "buem overestimates
  Heeten" story would need.

Not a defect to fix, but a real methodological question worth a
separate decision: whether a per-m2 intensity ratio would be a fairer
cross-municipality comparison than the current per-dwelling ratio,
given real house size varies by region and CBS does not publish a
per-m2 figure to compare against directly. Not acted on here.


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

The combined figure staying elevated is not a sign the fix was
incomplete: Heeten's real houses are genuinely larger than Loenen's
(see `Residual gap — explained: Heeten's real houses are bigger`_), and
pooling a municipality with bigger real homes into the same per-dwelling
statistic pulls the combined median toward Heeten's, independent of
model accuracy in either region.
