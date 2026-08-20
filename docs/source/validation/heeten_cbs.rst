Heeten vs. CBS — gas-consumption validation
=============================================

:Date: 2026-08-21 (third revision — see `Revision history`_)
:Region: Heeten (Overijssel), municipality of Raalte (CBS ``GM0177``)
:Buildings: 1,570 residential + 3 service — **the whole real population,
            not a sample**
:Result: 1,573 simulated, 1,102 excluded (no registered dwelling unit) or
         skipped, 0 errors
:Reference: CBS table 81528NED, period ``2018JJ00``
:Weather: merra-2, 2018, one fetch at the region centroid (52.329 N, 6.280 E)
:Model: same configuration as :doc:`loenen_cbs` (comfort band 18-21 degC,
        window-to-wall ratio 0.5, ``NL.Window.Ins.01`` corrected to HR++,
        the three country-level reference tables copied from
        ``netherlands/Loenen/``), real dwelling counts and
        refurbishment-variant selection, residential classification
        excludes Pand records with no RIVM-registered dwelling unit
        (issue #15)

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


Revision history
-------------------

Three runs, in order, kept in full rather than only showing the latest:

.. list-table::
   :header-rows: 1
   :widths: 30 16 18 18 18

   * - Run
     - Buildings
     - Median (total)
     - Median (heating-only)
     - Count-weighted

   * - 2026-08-20, first run
     - 2,671
     - 2.03
     - 2.07
     - 2.50
   * - 2026-08-20, RIVM data fixed (#13)
     - 2,671
     - 1.81
     - 1.77
     - 2.37
   * - **2026-08-21, contamination fixed (#15)**
     - **1,570**
     - **2.33**
     - **2.42**
     - **2.80**

1. **First run**: Heeten's building data was missing real dwelling
   counts and refurbishment-variant selection entirely (both need the
   raw RIVM energy-labels GeoPackage, not found on this machine at the
   time).
2. **RIVM data fix** (issue #13): the GeoPackage was located and
   ``nl_archetype_mapper.map_buildings()`` re-run against it. A real
   improvement -- but this alone couldn't and didn't reveal the larger
   problem below, since that problem was present in *both* runs above.
3. **Contamination fix** (issue #15, this run): the same cross-check
   against real government housing statistics that revised
   :doc:`loenen_cbs` found buem's Heeten dataset held 2,671 "residential"
   buildings against an official 1,568–1,578 residential addresses for
   the actual village -- 1,101 Pand records with no RIVM-registered
   dwelling unit (garden sheds, garages, farm outbuildings), simulated
   as 1-dwelling SFH by default. Excluding them (the corrected
   population: 1,570, within 0.3% of the official count) raised every
   figure, for the same reason as Loenen: the excluded buildings had
   near-zero absolute heating demand and near-zero ratios, and were
   diluting the real housing stock's numbers downward. Full mechanism in
   :doc:`loenen_cbs`'s `Correction: the population was contaminated
   <loenen_cbs.html#correction-the-population-was-contaminated>`_
   section -- identical cause, independently confirmed on a second,
   geographically distinct region.


Headline
-----------

Two metrics, not one -- see :doc:`loenen_cbs`'s own "Two ways to average"
section for the group-level version of this distinction. ``total`` is
(heating + dhw + cooking) against CBS's unstripped gas-total; ``heating-only``
is space heating alone against CBS's gas figure with the national 78%
space-heating share stripped off.

.. list-table::
   :header-rows: 1
   :widths: 30 14 20 20 16

   * - Metric
     - Buildings
     - Median
     - Mean
     - Count-weighted

   * - total
     - 1,570
     - 2.33
     - 2.80
     - 2.80
   * - heating-only
     - 1,570
     - 2.42
     - 2.96
     - --

.. list-table::
   :header-rows: 1
   :widths: 30 14 20 20

   * - Sample
     - Buildings
     - Median (total)
     - Median (heating-only)

   * - Label-matched only
     - 637
     - 1.52
     - 1.36
   * - Unlabelled
     - 933
     - 2.86
     - 3.07

**The median Heeten building sits at 2.33–2.42** — buem's simulated
heating demand runs a little over double the CBS-derived figure for a
typical building, on the *real* housing stock. As with Loenen, label
coverage is a real explanatory factor: label-matched buildings agree
markedly better than unlabelled ones, since only a labelled building gets
real TABULA refurbishment-variant credit.


All 1,570 residential buildings, by (building type, neighbour status)
---------------------------------------------------------------------------

.. list-table::
   :header-rows: 1
   :widths: 10 12 10 18 18 12

   * - type
     - neigh
     - n
     - buem heat kWh
     - CBS→kWh
     - ratio
   * - AB
     - B_Alone
     - 7
     - 25,867
     - 6,946
     - 3.72
   * - AB
     - B_N1
     - 2
     - 16,870
     - 6,946
     - 2.43
   * - AB
     - B_N2
     - 1
     - 8,443
     - 6,946
     - 1.22
   * - MFH
     - B_Alone
     - 40
     - 43,930
     - 6,946
     - 6.32
   * - MFH
     - B_N1
     - 5
     - 72,629
     - 6,946
     - 10.46
   * - SFH
     - B_Alone
     - 714
     - 44,910
     - 18,200
     - **2.47**
   * - SFH
     - B_N1
     - 322
     - 45,152
     - 14,507
     - **3.11**
   * - TH
     - B_N1
     - 219
     - 34,580
     - 12,836
     - 2.69
   * - TH
     - B_N2
     - 260
     - 31,483
     - 11,518
     - 2.73

The 714+322 SFH and 219+260 TH buildings — 99% of the stock — sit
between **2.47× and 3.11×** on a group basis. What remains above 5× is
MFH/AB (45+10 = 55 buildings), the same small-N groups flagged as the
largest outlier for Loenen.


By type and construction-year class
---------------------------------------

.. list-table::
   :header-rows: 1
   :widths: 10 16 10 16 16 16

   * - type
     - era
     - n
     - median (total)
     - median (heating-only)
     - median kWh/m²
   * - SFH
     - NL.01 (<=1964)
     - 341
     - 3.48
     - 3.83
     - 288.8
   * - SFH
     - NL.02 (1965-74)
     - 101
     - 3.72
     - 4.13
     - 314.5
   * - SFH
     - NL.03 (1975-91)
     - 209
     - 2.91
     - 3.13
     - 199.7
   * - SFH
     - NL.04 (1992-2005)
     - 211
     - 1.90
     - 1.90
     - 131.6
   * - SFH
     - NL.05 (2006-14)
     - 106
     - 1.41
     - 1.29
     - 106.4
   * - SFH
     - NL.06 (2015-)
     - 68
     - 1.48
     - 1.40
     - 99.0
   * - TH
     - NL.01 (<=1964)
     - 31
     - 4.46
     - 4.97
     - 376.5
   * - TH
     - NL.02 (1965-74)
     - 36
     - 1.30
     - 0.99
     - 104.7
   * - TH
     - NL.03 (1975-91)
     - 238
     - 2.69
     - 2.70
     - 167.9
   * - TH
     - NL.04 (1992-2005)
     - 72
     - 2.64
     - 2.62
     - 111.1
   * - TH
     - NL.05 (2006-14)
     - 38
     - 1.90
     - 1.76
     - 94.2
   * - TH
     - NL.06 (2015-)
     - 64
     - 1.64
     - 1.39
     - 85.9
   * - MFH
     - NL.01 (<=1964)
     - 31
     - 4.15
     - 4.06
     - 308.8
   * - MFH
     - NL.02 (1965-74)
     - 6
     - 10.00
     - 11.37
     - 207.9
   * - MFH
     - NL.03 (1975-91)
     - 2
     - 10.53
     - 12.04
     - 248.6
   * - MFH
     - NL.04 (1992-2005)
     - 2
     - 3.68
     - 3.47
     - 144.8
   * - MFH
     - NL.06 (2015-)
     - 4
     - 1.66
     - 0.95
     - 125.4
   * - AB
     - NL.01 (<=1964)
     - 3
     - 1.25
     - 0.43
     - 119.2
   * - AB
     - NL.02 (1965-74)
     - 1
     - 18.37
     - 21.83
     - 291.7
   * - AB
     - NL.03 (1975-91)
     - 2
     - 1.18
     - 0.35
     - 109.1
   * - AB
     - NL.04 (1992-2005)
     - 1
     - 1.22
     - 0.39
     - 112.7
   * - AB
     - NL.05 (2006-14)
     - 1
     - 1.51
     - 0.76
     - 136.3
   * - AB
     - NL.06 (2015-)
     - 2
     - 1.29
     - 0.49
     - 118.2

Same shape as Loenen — the ratio falls toward 1x in the newest
construction eras across every type. MFH's building count (45, unchanged
from before this correction — MFH/AB buildings were never among the
excluded non-dwellings, matching Loenen's own finding that the exclusion
concentrated entirely in SFH/TH) is real, not a sampling artefact.


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

Unaffected by the population correction (service buildings don't carry
dwelling counts or residential classification) — unchanged across all
three runs, consistent with Loenen's 286 kWh/m2 (2 warehouses).

Reverified live, not assumed: the ``occupancy.ServiceBuildingProfile``
connection both regions' service buildings depend on is still working
against the currently-installed package (v5.0.0) --
``tests/test_building_types.py::test_dummy_fixture_runs_end_to_end[...office...]``
and ``tests/test_service_buildings.py::
test_bundled_reference_tables_cover_every_occupancy_service_type`` both
exercise it directly and pass, independent of these batch runs.


Loenen and Heeten, now much closer together
--------------------------------------------------

Before the contamination fix, Heeten looked structurally different from
Loenen (median 1.77–1.81 vs. Loenen's 0.98–1.18 — issue #14 investigated
this at length and found a real, measured explanation: Heeten's real SFH
stock runs ~56% larger by floor area than Loenen's). After the identical
contamination fix applied to both regions, the two are much closer:

.. list-table::
   :header-rows: 1
   :widths: 26 18 18

   * - Metric
     - Loenen median
     - Heeten median

   * - total
     - 2.19
     - 2.33
   * - heating-only
     - 2.14
     - 2.42

A real difference remains (Heeten still runs somewhat higher, consistent
with issue #14's house-size finding, which is independent of the
contamination fix and still holds), but it is now a ~5-10% difference,
not the ~80% one that originally justified issue #14's own investigation.
Most of what looked like a Heeten-specific anomaly was, in the end, the
same population-contamination problem, just present to a different
degree in each region's raw data (Loenen 2.16x inflated, Heeten 1.69x).


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
     - 2.14
     - 2.33
     - 2.26
     - 3,031
   * - heating-only
     - 2.19
     - 2.42
     - 2.31
     - 3,031

Both regions are on equal methodological footing and much closer
together than before, so this combined figure is now a reasonably
meaningful population statistic — not just a sample-size convenience.
It still pools two distinct municipalities against two distinct CBS
reference figures, so treat it as a description of this specific
3,031-building sample rather than a single universal "buem accuracy"
constant; each region's own numbers remain the more precise reference for
a claim about that region specifically.
