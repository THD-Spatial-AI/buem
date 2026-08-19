Loenen vs. CBS — gas-consumption validation
=============================================

:Date: 2026-08-18
:Region: Loenen (Gelderland), municipality of Apeldoorn (CBS ``GM0200``)
:Buildings: 3,101 residential — **the whole population, not a sample**
:Result: 3,101 simulated, 0 skipped, 0 errors
:Reference: CBS table 81528NED, period ``2018JJ00``
:Weather: merra-2, 2018, one fetch at the region centroid (52.120 N, 6.026 E)
:Model: comfort band 18–21 °C, window-to-wall ratio 0.5, TABULA
        refurbishment variants active, DHW + gas-cooking modelled
:Runtime: 25.5 min, 16 workers (~2.0 buildings/s)

Reproduce with:

.. code-block:: bash

   python -m buem.analysis.batch --source csv \
       --data-dir src/buem/data/buildings/netherlands \
       --country NL --residential-only --workers 16 --resume \
       --output results/loenen.parquet

   python -m buem.analysis.netherlands.validation \
       --from-parquet results/loenen.parquet --region-code GM0200 [--labeled-only]


.. _two-ways-to-average:

Two ways to average, and why they differ so much
--------------------------------------------------

Results are grouped into nine ``(building_type, neighbour_status)``
groups, because that is the dimension CBS's own housing-type categories
key on. Each group gets its own ratio:

.. code-block:: text

   group ratio = mean simulated heating per dwelling  /  CBS-derived useful heat

Those nine ratios can then be combined two ways, and **the two answers are
very different** (4.77 vs. 3.01), so the distinction matters:

**Mean of group ratios** — add the nine ratios, divide by nine. Every
group counts once, regardless of size. A group of 12 apartment blocks
counts exactly as much as a group of 2,493 detached houses.

**Building-count weighted** — weight each group's ratio by how many real
buildings it contains:

.. code-block:: text

   weighted = Σ(nᵢ × ratioᵢ) / Σ(nᵢ)

Worked example with the real numbers below: MFH B_Alone has a ratio of
16.65 from **19** buildings, while SFH B_Alone has 2.92 from **2,042**.
The unweighted mean lets those 19 buildings pull the headline figure up by
more than a full point; the weighted mean lets them contribute 19/3101 =
0.6 % of it.

**Use the count-weighted figure when asking "how well does buem model
Loenen".** It describes the housing stock. The unweighted mean describes
the list of groups, and is reported here only because the earlier sampled
runs quoted it and a like-for-like comparison needs it.

.. list-table::
   :header-rows: 1
   :widths: 34 13 12 20 21

   * - Sample
     - Buildings
     - Median
     - Mean of group ratios
     - Building-count weighted

   * - All residential
     - 3,101
     - 1.12
     - 4.77
     - 3.01

   * - Label-matched only
     - 742
     - 1.39
     - 2.60
     - 2.16

   * - **All, plausible dwelling counts**
     - **2,934**
     - **1.03**
     - **3.20**
     - **1.81**

   * - Label-matched, plausible counts
     - 716
     - 1.37
     - 2.54
     - 2.03

**The bolded row is the headline figure.** The first two rows include 167
buildings whose recorded dwelling count is demonstrably wrong (see
`Dwelling-count data quality`_); their mean ratio is 24.0, and leaving
them in inflates the all-population figure from 1.81 to 3.01. They are
listed only because they were the published numbers before the problem
was found.

(The label-matched subset is the 23.9 % of buildings carrying a real RIVM
energy label — the ones whose *current* envelope performance, including
any refurbishment, is known rather than inferred from construction year.)

The **median** column deserves attention alongside the means: the median
Loenen building sits at **1.03**, i.e. essentially on top of the CBS
figure. The distribution has a long right tail, so means overstate what a
typical building looks like. Any statement of the form "buem overestimates
by ~3×" describes the tail, not the stock.


All 3,101 residential buildings
---------------------------------

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
     - 24,087
     - 6,103
     - 3.95
   * - AB
     - B_N1
     - 4
     - 7,617
     - 6,103
     - 1.25
   * - AB
     - B_N2
     - 1
     - 15,397
     - 6,103
     - 2.52
   * - MFH
     - B_Alone
     - 19
     - 101,650
     - 6,103
     - 16.65
   * - MFH
     - B_N1
     - 9
     - 42,544
     - 6,103
     - 6.97
   * - SFH
     - B_Alone
     - 2,042
     - 47,914
     - 16,390
     - 2.92
   * - SFH
     - B_N1
     - 451
     - 32,253
     - 11,384
     - 2.83
   * - TH
     - B_N1
     - 261
     - 25,080
     - 9,670
     - 2.59
   * - TH
     - B_N2
     - 307
     - 26,018
     - 8,092
     - 3.22


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
     - 19,154
     - 6,103
     - 3.14
   * - AB
     - B_N1
     - 4
     - 7,617
     - 6,103
     - 1.25
   * - AB
     - B_N2
     - 1
     - 15,397
     - 6,103
     - 2.52
   * - MFH
     - B_Alone
     - 7
     - 19,198
     - 6,103
     - 3.15
   * - MFH
     - B_N1
     - 6
     - 30,409
     - 6,103
     - 4.98
   * - SFH
     - B_Alone
     - 256
     - 39,116
     - 16,390
     - 2.39
   * - SFH
     - B_N1
     - 112
     - 22,816
     - 11,384
     - 2.00
   * - TH
     - B_N1
     - 159
     - 21,589
     - 9,670
     - 2.23
   * - TH
     - B_N2
     - 191
     - 14,255
     - 8,092
     - 1.76

718 of these 742 buildings are SFH or TH, and every one of those four
groups falls between **1.76× and 2.39×**.


Excluding implausible dwelling counts (≤500 m²/dwelling)
----------------------------------------------------------

All 2,934 buildings with a plausible dwelling count:

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
     - 24,361
     - 6,103
     - 3.99
   * - AB
     - B_N1
     - 4
     - 7,617
     - 6,103
     - 1.25
   * - AB
     - B_N2
     - 1
     - 15,397
     - 6,103
     - 2.52
   * - MFH
     - B_Alone
     - 16
     - 45,650
     - 6,103
     - 7.48
   * - MFH
     - B_N1
     - 8
     - 31,345
     - 6,103
     - 5.14
   * - SFH
     - B_Alone
     - 1,902
     - 24,783
     - 16,390
     - **1.51**
   * - SFH
     - B_N1
     - 439
     - 23,649
     - 11,384
     - 2.08
   * - TH
     - B_N1
     - 259
     - 24,190
     - 9,670
     - 2.50
   * - TH
     - B_N2
     - 299
     - 18,787
     - 8,092
     - 2.32

The 2,341 SFH and 558 TH buildings — 99 % of the stock — now sit between
**1.51× and 2.50×**. What remains above 3× is 35 MFH/AB buildings.


What the full population shows that a sample could not
---------------------------------------------------------

Label coverage is *not* the main driver — an earlier reading corrected
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

On the raw figures the label-matched subset looked markedly better than
the population (2.16 vs. 3.01), which suggested that undetected
refurbishment on unlabelled buildings was a major component of the gap.
**That reading does not survive the dwelling-count correction** and is
retracted here. Per-building mean ratios:

.. list-table::
   :header-rows: 1
   :widths: 30 20 25 25

   * - Subset
     - n
     - Raw
     - Plausible counts only

   * - Labelled
     - 742 / 716
     - 2.16
     - 2.03
   * - Unlabelled
     - 2,359 / 2,218
     - 3.27
     - **1.74**

141 of the 167 implausible-dwelling-count buildings are unlabelled, and
they alone produced the apparent difference. Once removed, unlabelled
buildings agree slightly *better* than labelled ones (1.74 vs. 2.03) —
the opposite direction, and small enough that label coverage should not
be treated as a leading explanation either way.

The refurbishment variants and construction eras both order correctly
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Mean heating intensity across the label-matched subset, by the TABULA
refurbishment variant the label selected:

.. list-table::
   :header-rows: 1
   :widths: 40 15 25

   * - Variant
     - n
     - kWh/m²

   * - 1 — as built
     - 334
     - 185.3
   * - 2 — standard refurbishment
     - 322
     - 63.5
   * - 3 — nZEB refurbishment
     - 86
     - 30.7

And across the whole population, by construction-year class:

.. list-table::
   :header-rows: 1
   :widths: 40 15 25

   * - Class
     - n
     - kWh/m²

   * - NL.01 (≤1964)
     - 1,355
     - 266.0
   * - NL.02 (1965–1974)
     - 397
     - 256.3
   * - NL.03 (1975–1991)
     - 456
     - 183.5
   * - NL.04 (1992–2005)
     - 377
     - 101.4
   * - NL.05 (2006–2014)
     - 253
     - 73.0
   * - NL.06 (2015+)
     - 263
     - 60.0

Both series are monotonic in the expected direction, which is a useful
internal consistency check: the model responds to envelope quality the way
it should, whatever the absolute offset against CBS.

.. _dwelling-count data quality:

Dwelling-count data quality
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

**167 buildings (5.4 %) imply more than 500 m² of floor area per
dwelling**, the worst at 42,204 m². Two classified MFH are 19,241 m² and
5,680 m² while recorded as holding two dwellings each. Their mean ratio is
**24.0** — they are not modelling results, they are a broken denominator.

The cause is a missing or wrong RIVM ``aant_verblijfsobj``. CBS publishes
consumption *per dwelling*, so every comparison divides a whole-building
result by that count; when the count is wrong the quotient cannot match
any CBS category, however good the thermal model is. Stage 3's
``MFH_MAX_UNITS ≤ 4`` rule then classifies a very large building recorded
as holding two dwellings as MFH, which is why MFH is the worst-hit group.

This is a real and expected shape of Dutch building stock, not a modelling
artefact to design away: a single BAG *Pand* can be an entire terrace or
apartment block containing many households. The problem is only that the
household count is sometimes absent from the source.

``validation.aggregate_parquet`` therefore **always reports** these rows
and can exclude them via ``--max-m2-per-dwelling`` (suggested 500, the
constant ``IMPLAUSIBLE_M2_PER_DWELLING``). Exclusion is deliberately
**not** the default: it changes the headline number, so it is the
caller's decision. Nothing overwrites the recorded dwelling count —
inventing a plausible one would replace a visibly missing value with an
invisible guess.


Interpreting the remaining gap
---------------------------------

A ratio of 1.0 is not the target, and reaching it would be a warning sign
rather than a success. buem computes **calculated demand under a defined
set of assumptions**; CBS reports **metered gas consumption**. A
persistent gap between the two is the well-documented *prebound effect*
and is expected in the literature for exactly this comparison. The
contributors, in the order they have been quantified here:

.. list-table::
   :header-rows: 1
   :widths: 34 16 50

   * - Contributor
     - Effect
     - Status

   * - Wrong dwelling counts (167 buildings)
     - 3.01 → 1.81
     - **Reportable and filterable**; source data unfixed
   * - Construction-era sampling skew
     - up to 1.9×
     - **Eliminated** — the whole population is simulated
   * - Comfort setpoint (20–24 → 18–21 °C)
     - ~17–18 %
     - Applied
   * - TABULA refurbishment variants
     - ~15 %
     - Applied where a label exists (23.9 %)
   * - Multi-dwelling internal-gain scaling
     - ~10 % on AB/MFH
     - Applied
   * - DHW + gas cooking modelled
     - 5–20 % on 7 of 9 groups
     - Applied
   * - Window U-value (TABULA HR 1.8 vs. real HR++ 1.1–1.2)
     - not yet measured
     - **Open** — the largest identified remaining candidate
   * - Undetected refurbishment on unlabelled buildings
     - ~0.3× and the *opposite* sign
     - Investigated; **not** a leading explanation
   * - Occupant behaviour (prebound effect)
     - unquantified
     - Irreducible in a calculated-demand model

Where this leaves the question "will the gap ever close?": a
building-count-weighted **1.81** with a **median of 1.03** is no longer
the picture of a systematically wrong model. Half of Loenen's buildings
already fall within a few percent of their CBS category. The residual is
concentrated in a right tail and in 35 MFH/AB buildings, and the two
remaining structural candidates (window U-value, and dwelling counts in
the source data) are both tractable. What will *not* close is the
irreducible part: calculated demand under standardised assumptions is a
different quantity from metered consumption, and expecting 1.0 would mean
the model had absorbed the occupants' behaviour along with the physics.
