Loenen vs. CBS — gas-consumption validation
=============================================

:Date: 2026-08-19 (supersedes the 2026-08-18 run; see `Change since 2026-08-18`_)
:Region: Loenen (Gelderland), municipality of Apeldoorn (CBS ``GM0200``)
:Buildings: 3,101 residential + 2 service — **the whole population, not a sample**
:Result: 3,103 simulated, 2 skipped (sub-threshold structures), 0 errors
:Reference: CBS table 81528NED, period ``2018JJ00``
:Weather: merra-2, 2018, one fetch at the region centroid (52.120 N, 6.026 E)
:Model: comfort band 18–21 °C, window-to-wall ratio 0.5, TABULA
        refurbishment variants active, DHW + gas cooking modelled,
        ``NL.Window.Ins.01`` corrected to HR++ (U 1.15), dwelling counts
        repaired from floor area where the registered ones were impossible
:Runtime: 33 min, 16 workers (~1.6 buildings/s)

Reproduce with:

.. code-block:: bash

   python scripts/repair_nl_dwelling_counts.py

   python -m buem.analysis.batch --source csv \
       --data-dir src/buem/data/buildings/netherlands \
       --country NL --workers 16 --resume \
       --output results/loenen.parquet

   python -m buem.analysis.netherlands.validation \
       --from-parquet results/loenen.parquet --region-code GM0200 [--labeled-only]


Headline
-----------

.. list-table::
   :header-rows: 1
   :widths: 30 14 12 22 22

   * - Sample
     - Buildings
     - Median
     - Mean of group ratios
     - Building-count weighted

   * - **All residential**
     - **3,101**
     - **0.98**
     - **2.94**
     - **1.78**

   * - Label-matched only
     - 742
     - 1.18
     - 2.34
     - 1.89

   * - Unlabelled
     - 2,359
     - 0.86
     - —
     - 1.74

**The median Loenen building sits at 0.98** — essentially on top of its
CBS category, and marginally below rather than above it. The distribution
has a long right tail, so the mean overstates what a typical building
looks like: any "buem overestimates by N×" statement describes the tail,
not the stock.

No plausibility filter is applied, or needed. The dwelling counts that
previously required one are repaired at source, and re-running with
``--max-m2-per-dwelling 500`` now changes nothing at all.


.. _two-ways-to-average:

Two ways to average, and why they differ
-------------------------------------------

Results are grouped into nine ``(building_type, neighbour_status)``
groups, because that is the dimension CBS's housing-type categories key
on. Each group gets its own ratio:

.. code-block:: text

   group ratio = mean simulated heating per dwelling  /  CBS-derived useful heat

Those nine ratios combine two ways, and the answers differ a lot (2.94 vs
1.78):

**Mean of group ratios** — add the nine, divide by nine. Every group
counts once regardless of size, so 12 apartment blocks count as much as
2,493 detached houses.

**Building-count weighted** — weight each ratio by how many real buildings
it covers:

.. code-block:: text

   weighted = Σ(nᵢ × ratioᵢ) / Σ(nᵢ)

Worked example from the table below: MFH B_Alone is 6.46 from **19**
buildings, SFH B_Alone is 1.50 from **2,042**. Unweighted, those 19
buildings pull the headline up by more than a point; weighted, they
contribute 19/3101 = 0.6 % of it.

**Use the count-weighted figure** when asking how well buem models Loenen
— it describes the housing stock. The unweighted mean describes the list
of groups, and is reported only because earlier runs quoted it.


All 3,101 residential buildings
----------------------------------

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
     - 21,024
     - 6,103
     - 3.44
   * - AB
     - B_N1
     - 4
     - 7,158
     - 6,103
     - 1.17
   * - AB
     - B_N2
     - 1
     - 13,904
     - 6,103
     - 2.28
   * - MFH
     - B_Alone
     - 19
     - 39,419
     - 6,103
     - 6.46
   * - MFH
     - B_N1
     - 9
     - 29,968
     - 6,103
     - 4.91
   * - SFH
     - B_Alone
     - 2,042
     - 24,585
     - 16,390
     - **1.50**
   * - SFH
     - B_N1
     - 451
     - 23,350
     - 11,384
     - 2.05
   * - TH
     - B_N1
     - 261
     - 23,478
     - 9,670
     - 2.43
   * - TH
     - B_N2
     - 307
     - 18,302
     - 8,092
     - 2.26

The 2,493 SFH and 568 TH buildings — 99 % of the stock — sit between
**1.50× and 2.43×**. What remains above 3× is 28 MFH and 12 AB buildings.


The 742 label-matched buildings
----------------------------------

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
     - 6
     - 15,581
     - 6,103
     - 2.55
   * - AB
     - B_N1
     - 4
     - 7,158
     - 6,103
     - 1.17
   * - AB
     - B_N2
     - 1
     - 13,904
     - 6,103
     - 2.28
   * - MFH
     - B_Alone
     - 7
     - 16,023
     - 6,103
     - 2.63
   * - MFH
     - B_N1
     - 6
     - 30,259
     - 6,103
     - 4.96
   * - SFH
     - B_Alone
     - 256
     - 31,181
     - 16,390
     - 1.90
   * - SFH
     - B_N1
     - 112
     - 20,973
     - 11,384
     - 1.84
   * - TH
     - B_N1
     - 159
     - 20,575
     - 9,670
     - 2.13
   * - TH
     - B_N2
     - 191
     - 12,850
     - 8,092
     - 1.59


Change since 2026-08-18
--------------------------

Three fixes landed between the two runs. Their combined effect on the
count-weighted figure:

.. list-table::
   :header-rows: 1
   :widths: 46 18 18 18

   * - Configuration
     - All
     - Labelled
     - Median (all)

   * - 2026-08-18, as published
     - 3.01
     - 2.16
     - 1.12
   * - 2026-08-18, filtering bad dwelling counts
     - 1.81
     - 2.03
     - 1.03
   * - **2026-08-19, all three fixes**
     - **1.78**
     - **1.89**
     - **0.98**

**Window U-value.** TABULA's standard window measure
``NL.Window.Ins.01`` assumed R = 0.556 (U = 1.80, plain HR glazing) where
Dutch stock refurbished to that label tier now has HR++ at 1.1–1.2.
Corrected to U = 1.15 via ``refurbishment_measure_reference.csv``.

The effect isolates cleanly, because only refurbished variants carry a
window measure at all — mean heating intensity across the label-matched
subset:

.. list-table::
   :header-rows: 1
   :widths: 40 15 15 15 15

   * - Refurbishment variant
     - n
     - Before
     - After
     - Change

   * - 1 — as built (no window measure)
     - 334
     - 185.3
     - 184.9
     - −0.2 %
   * - **2 — standard refurbishment**
     - **322**
     - **63.5**
     - **50.7**
     - **−20.2 %**
   * - 3 — nZEB refurbishment
     - 86
     - 30.7
     - 29.6
     - −3.6 %

Variant 1 is the control: it carries no window measure to correct, and its
flatness confirms the −20 % on variant 2 is the glazing fix rather than
anything else that changed in the run.

**Dwelling counts.** 167 residential buildings had registered counts
implying over 500 m² per dwelling; those are now derived from floor area
(see `Dwelling-count data quality`_). This fixes the per-dwelling
denominator and gives multi-dwelling blocks their real internal gains.

**Service buildings.** Both Loenen warehouses now simulate rather than
being skipped, at 273 and 285 kWh/m² — comparable to the residential
NL.01 mean of 263. They carry no CBS housing-type key, so they do not
enter the ratios above.


Internal consistency
-----------------------

Both series order monotonically in the expected direction, which is a
useful check independent of the absolute offset against CBS.

Mean heating intensity by refurbishment variant, label-matched subset:

.. list-table::
   :header-rows: 1
   :widths: 45 20 25

   * - Variant
     - n
     - kWh/m²

   * - 1 — as built
     - 334
     - 184.9
   * - 2 — standard refurbishment
     - 322
     - 50.7
   * - 3 — nZEB refurbishment
     - 86
     - 29.6

And by construction-year class, whole population:

.. list-table::
   :header-rows: 1
   :widths: 45 20 25

   * - Class
     - n
     - kWh/m²

   * - NL.01 (≤1964)
     - 1,355
     - 263.3
   * - NL.02 (1965–1974)
     - 397
     - 253.4
   * - NL.03 (1975–1991)
     - 456
     - 181.0


.. _dwelling-count data quality:

Dwelling-count data quality
------------------------------

CBS publishes consumption **per dwelling**, so every comparison divides a
whole-building result by ``residential_units`` — and buem scales
occupancy's internal gains by the same count before the solve. A wrong
count therefore corrupts the result twice, in opposite directions.

167 residential buildings (5.4 %) had registered counts implying more
than 500 m² per dwelling, the worst at 42,204 m²; one 19,241 m² block was
recorded as holding two. Their mean ratio was 24.0 — a broken
denominator, not a modelling result.

This is *not* an artefact to design away. A single BAG *Pand* can
legitimately be an entire terrace or block housing many households, which
is exactly what TABULA's own AB/MFH archetypes model (``n_Apartment``
15–56). The defect is only that RIVM sometimes registers part of a Pand's
sub-units.

``scripts/repair_nl_dwelling_counts.py`` derives a count from floor area
where the registered one cannot be right, writing
``residential_units_recorded`` and ``residential_units_source`` alongside
it so a derived value can never be mistaken for registered data. It never
reduces a registered count, does not act where the implied dwelling size
is already plausible, and skips non-residential buildings entirely — a
warehouse has no dwellings, and giving it a derived count would scale
occupancy's service-building profile by a household multiplier that does
not exist. Result: 167 repaired, 0 implausible remaining.

**Known limitation**: 152 of the 167 are SFH, and some are more likely
large agricultural buildings than housing — where neither one 2,000 m²
dwelling nor thirteen 150 m² ones is right. The estimate at least yields a
plausible per-dwelling intensity, but telling barns from housing needs a
use-class signal the pipeline does not carry.


Label coverage is not a leading explanation
----------------------------------------------

On the 2026-08-18 raw figures the label-matched subset looked markedly
better than the population (2.16 vs 3.01), suggesting undetected
refurbishment on unlabelled buildings was a major driver. **That reading
was an artefact** of the dwelling-count problem — 141 of the 167 affected
buildings were unlabelled — and is retracted.

With the data repaired, unlabelled buildings agree slightly *better* than
labelled ones (1.74 vs 1.89, medians 0.86 vs 1.18). The difference is
small and in the opposite direction, so label coverage should not be
treated as a leading explanation either way.


Interpreting the remaining gap
---------------------------------

A ratio of 1.0 is not the target, and reaching it would be a warning sign
rather than a success: buem computes **calculated demand under defined
assumptions**, CBS reports **metered consumption**, and the gap between
them is the documented prebound effect.

.. list-table::
   :header-rows: 1
   :widths: 34 16 50

   * - Contributor
     - Effect
     - Status

   * - Wrong dwelling counts (167 buildings)
     - 3.01 → 1.81
     - **Fixed** at source
   * - Construction-era sampling skew
     - up to 1.9×
     - **Eliminated** — whole population simulated
   * - Comfort setpoint (20–24 → 18–21 °C)
     - ~17–18 %
     - Applied
   * - Window U-value (HR 1.80 → HR++ 1.15)
     - −20 % on refurbished stock
     - **Fixed**
   * - TABULA refurbishment variants
     - ~15 %
     - Applied where a label exists (23.9 %)
   * - Multi-dwelling internal-gain scaling
     - ~10 % on AB/MFH
     - Applied
   * - DHW + gas cooking modelled
     - 5–20 % on 7 of 9 groups
     - Applied
   * - MFH/AB group ratios (28 + 12 buildings)
     - 3.4–6.5×
     - **Open** — small-N, and the largest remaining outlier
   * - Occupant behaviour (prebound effect)
     - unquantified
     - Irreducible in a calculated-demand model

With a count-weighted **1.78** and a median of **0.98**, this is no longer
the picture of a systematically wrong model: half of Loenen's buildings
land within a couple of percent of their CBS category. What remains is
concentrated in a right tail and in 40 apartment-type buildings, where
small-N and per-building envelope accuracy dominate.
