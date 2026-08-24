Loenen vs. CBS — gas-consumption validation
=============================================

:Date: 2026-08-21 (major correction — see `Correction: the population was contaminated`_)
:Region: Loenen (Gelderland), municipality of Apeldoorn (CBS ``GM0200``)
:Buildings: 1,461 residential + 2 service — **the whole real population, not a sample**
:Result: 1,463 simulated, 1,642 excluded (no registered dwelling unit) or skipped, 0 errors
:Reference: CBS table 81528NED, period ``2018JJ00``
:Weather: merra-2, 2018, one fetch at the region centroid (52.120 N, 6.026 E)
:Model: comfort band 18–21 °C, window-to-wall ratio 0.5, TABULA
        refurbishment variants active, DHW + gas cooking modelled,
        ``NL.Window.Ins.01`` corrected to HR++ (U 1.15), dwelling counts
        repaired from floor area where the registered ones were impossible,
        residential classification excludes Pand records with no
        RIVM-registered dwelling unit (issue #15)
:Runtime: ~36 min, 18 workers (~1.5 buildings/s)

Reproduce with:

.. code-block:: bash

   python scripts/reclassify_with_rivm_labels.py src/buem/data/buildings/netherlands/Loenen \
       --gpkg-path /path/to/energielabels_2025.gpkg

   python -m buem.analysis.batch --source csv \
       --data-dir src/buem/data/buildings/netherlands/Loenen \
       --country NL --workers 18 \
       --output results/loenen.parquet

   python -m buem.analysis.netherlands.validation \
       --from-parquet results/loenen.parquet --region-code GM0200 [--labeled-only]


.. _correction-population-contaminated:

Correction: the population was contaminated
------------------------------------------------

**Every figure below through 2026-08-20 (count-weighted 1.78, median 0.98)
was computed against a population that was 2.16× too large** — cross-
checking against real government housing statistics (BAG-derived, via a
public aggregator) found buem's Loenen dataset held 3,101 "residential"
buildings against an official 1,424–1,435 residential addresses for the
actual village.

Root cause (`issue #15
<https://github.com/UU-BUEM/buem/issues/15>`_): BAG registers every
physical structure as its own Pand, including garden sheds, garages, and
farm outbuildings. Nothing in the classification pipeline excluded them
from the residential path — they simply had no explicit
``is_greenhouse_or_warehouse``/``is_glass_roof`` flag, so they fell
through to being classified as 1-dwelling SFH by default, same as a real
house. Confirmed with real numbers, not assumed: buildings under 30 m²
footprint had a RIVM-registered residential unit only ~5% of the time.
The RIVM energy-labels GeoPackage's own ``aant_verblijfsobj`` field
already available to this pipeline distinguishes them precisely — a Pand
present in that data with no unit registered under it at all is not a
dwelling. Filtering on this (rather than an arbitrary size cutoff)
reproduces the real village address count almost exactly: 1,461 vs.
official 1,424–1,435.

**This did not make the headline ratio better. It made it worse, by a
lot, because of *how* the contaminating buildings were failing.** A
garden shed has almost no real heating demand in absolute terms (a few
hundred to a few thousand kWh/year for a whole "dwelling"), so it also
gets a very low buem/CBS ratio — median 0.52 across the 1,640 excluded
buildings, confirmed directly by comparing their pre-fix ratios to the
buildings that remain. Mixed into a population of 3,101, those ~1,640
low-ratio non-dwellings pulled the population median down from where the
real housing stock alone sits. The real houses were there the whole
time; they were just outnumbered by sheds in the sample.

.. list-table::
   :header-rows: 1
   :widths: 36 18 18 18

   * - Sample
     - Buildings
     - Median (heating-only)
     - Count-weighted

   * - 2026-08-19 (contaminated)
     - 3,101
     - 0.98
     - 1.78
   * - **2026-08-21 (corrected)**
     - **1,461**
     - **2.19**
     - **2.61**

The corrected figure is buem's real read on Loenen: it is not close
agreement, and 0.98 was never a defensible "the model matches CBS"
result — it was an artefact of averaging real houses against thousands
of garden sheds.


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
     - **1,461**
     - **2.19**
     - **3.24**
     - **2.61**

   * - Label-matched only
     - 742
     - 1.18
     - 1.97
     - —
   * - Unlabelled
     - 719
     - 3.31
     - 3.27
     - —

**The median Loenen building sits at 2.19** — buem's simulated heating
demand runs a little over double the CBS-derived figure for a typical
building. The distribution still has a long right tail (mean 2.74 for
this same population), so the mean overstates the typical case further
still, but the median itself is now the honest number, not one flattered
by contamination.

**Label coverage is a real explanatory factor again.** With the
population corrected, label-matched buildings agree markedly better
(median 1.18) than unlabelled ones (median 3.31) — the opposite of
"label coverage is not a leading explanation," this doc's own
2026-08-19 conclusion (see `Label coverage is not a leading explanation`_
below, kept for the historical record rather than deleted). That earlier
finding was itself computed against the contaminated population; once
non-dwellings are removed, the gap reappears and is now large. This
makes physical sense: a labelled building gets real refurbishment-variant
credit; an unlabelled one defaults to TABULA's as-built envelope
regardless of its real, unknown refurbishment status.

No dwelling-count plausibility filter changes this materially: 2 of
1,463 buildings still imply an unusually large area per dwelling — both
are the two warehouses, a false positive from the plausibility check
(``aggregate_parquet``'s own warning) not yet skipping non-residential
rows, not a real residential dwelling-count problem.


.. _two-ways-to-average:

Two ways to average, and why they differ
-------------------------------------------

Results are grouped into nine ``(building_type, neighbour_status)``
groups, because that is the dimension CBS's housing-type categories key
on. Each group gets its own ratio:

.. code-block:: text

   group ratio = mean simulated heating per dwelling  /  CBS-derived useful heat

Those nine ratios combine two ways, and the answers differ a lot (3.24 vs
2.61):

**Mean of group ratios** — add the nine, divide by nine. Every group
counts once regardless of size, so 9 apartment blocks count as much as
704 detached houses.

**Building-count weighted** — weight each ratio by how many real buildings
it covers:

.. code-block:: text

   weighted = Σ(nᵢ × ratioᵢ) / Σ(nᵢ)

**Use the count-weighted figure** when asking how well buem models Loenen
— it describes the housing stock. The unweighted mean describes the list
of groups, and is reported only because earlier runs quoted it.


All 1,461 residential buildings
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
     - 27,826
     - 7,825
     - 3.56
   * - AB
     - B_N1
     - 4
     - 13,604
     - 7,825
     - 1.74
   * - AB
     - B_N2
     - 1
     - 20,523
     - 7,825
     - 2.62
   * - MFH
     - B_Alone
     - 19
     - 46,692
     - 7,825
     - 5.97
   * - MFH
     - B_N1
     - 9
     - 36,999
     - 7,825
     - 4.73
   * - SFH
     - B_Alone
     - 704
     - 49,853
     - 21,013
     - **2.37**
   * - SFH
     - B_N1
     - 238
     - 42,239
     - 14,595
     - **2.89**
   * - TH
     - B_N1
     - 210
     - 33,853
     - 12,397
     - 2.73
   * - TH
     - B_N2
     - 269
     - 26,674
     - 10,375
     - 2.57

The 704+238 SFH and 210+269 TH buildings — 97% of the stock — sit
between **1.74× and 5.97×**, most of them (SFH/TH, 96% of the stock)
clustered narrower, **2.37×–2.89×**. What remains above 3× on a group
basis is MFH/AB (28+12 = 40 buildings) — the same small-N groups flagged
as the largest outlier before this correction, and still the largest
outlier after it.

The ``CBS→kWh`` column also differs from the 2026-08-19 run's for the
*same* category/region/period (e.g. apartment: 6,103 then, 7,825 now) --
not a transcription error or a constants change here (verified: the
conversion constants in ``dhw_cooking_constants.csv`` are unchanged, and
890 m³ x 9.769 kWh/m³ x 0.9 reproduces 7,825 exactly). ``fetch_consumption``
queries CBS's live API fresh each run, and the raw gas-m³ figure it
returned for this same historical region/period genuinely differs between
the two dates -- confirmed by back-converting the old table's kWh figure,
which implies ~694 m³ where the live query now returns 890 m³. Not
investigated further here (why CBS's own reported figure for a supposedly-
fixed historical period changed) -- noted so a reader comparing the two
tables' CBS columns doesn't assume a transcription error.


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
being skipped, averaging 286 kWh/m² — comparable to the residential
NL.01 mean (208 kWh/m² on the 2026-08-21-corrected population; see
`Internal consistency`_). They carry no CBS housing-type key, so they do
not enter the ratios above.


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

The refurbishment-variant table is unchanged by the 2026-08-21 population
correction: none of the excluded non-dwellings were label-matched, so
this exact subset of 742 buildings is identical before and after.

By construction-year class, whole population (now 1,461, and now shows
all six classes -- the previous table only had data through NL.03):

.. list-table::
   :header-rows: 1
   :widths: 45 20 25

   * - Class
     - n
     - kWh/m²

   * - NL.01 (≤1964)
     - 735
     - 208.4
   * - NL.02 (1965–1974)
     - 227
     - 190.3
   * - NL.03 (1975–1991)
     - 198
     - 142.7
   * - NL.04 (1992–2005)
     - 139
     - 81.9
   * - NL.05 (2006–2014)
     - 45
     - 79.0
   * - NL.06 (2015–)
     - 117
     - 68.3


.. _dwelling-count data quality:

Dwelling-count data quality
------------------------------

CBS publishes consumption **per dwelling**, so every comparison divides a
whole-building result by ``residential_units`` — and buem scales
occupancy's internal gains by the same count before the solve. A wrong
count therefore corrupts the result twice, in opposite directions.

On the real residential population (corrected 2026-08-21, see
`Correction: the population was contaminated`_), 79 buildings (5.4 %,
coincidentally the same share as the 167/3,101 figure this section
originally reported against the since-corrected larger population) had
registered counts implying more than 500 m² per dwelling. Their mean
ratio was similarly broken before repair — a bad denominator, not a
modelling result.

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
not exist. Result: 79 repaired (71 SFH, 4 MFH, 3 TH, 1 AB), 0 implausible
remaining.

**Known limitation**: most of the repairs are SFH, and some are more likely
large agricultural buildings than housing — where neither one 2,000 m²
dwelling nor thirteen 150 m² ones is right. The estimate at least yields a
plausible per-dwelling intensity, but telling barns from housing needs a
use-class signal the pipeline does not carry.


Label coverage: reversed twice, now a real factor
------------------------------------------------------

This conclusion has flipped twice as the population's data quality was
corrected, worth recording in full rather than only keeping the latest
answer:

1. **2026-08-18, raw figures**: label-matched buildings looked markedly
   better than the population (2.16 vs 3.01), suggesting undetected
   refurbishment on unlabelled buildings was a major driver.
2. **2026-08-19, dwelling counts repaired**: that reading was retracted
   — 141 of the 167 dwelling-count-affected buildings were unlabelled,
   so the apparent effect was really the dwelling-count fix in
   disguise. With counts repaired, unlabelled agreed *slightly better*
   than labelled (1.74 vs 1.89) — the opposite direction, small enough
   that label coverage was concluded not to be a leading explanation.
3. **2026-08-21, population contaminated by non-dwellings**: also
   retracted. With sheds/garages removed (see `Correction: the
   population was contaminated`_), label-matched buildings again agree
   markedly better than unlabelled (median 1.18 vs 3.31) — this time not
   an artefact of dwelling counts (those were already fixed in step 2),
   but of the *same* contamination that affected the headline. See
   `Headline`_.

Label coverage **is** a real, substantial explanatory factor: a
labelled building gets real TABULA refurbishment-variant credit, an
unlabelled one defaults to the as-built envelope regardless of its true,
unknown condition.


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

   * - **Non-dwelling contamination (1,640 buildings)**
     - **0.98 → 2.19 median**
     - **Fixed** at source (issue #15) — the dominant correction, and in
       the opposite direction from every other fix in this table
   * - Wrong dwelling counts (167 buildings)
     - 3.01 → 1.81 (on the *then*-contaminated population)
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
     - 3.4–6.5× (now: 1.74×–5.97× on the corrected population)
     - **Open** — small-N, still the largest remaining group-level
       outlier
   * - Occupant behaviour (prebound effect)
     - unquantified
     - Irreducible in a calculated-demand model

**This is now the picture of a model that runs meaningfully hot, not one
that matches CBS.** With the population corrected, buem's median
building simulates roughly double its CBS-derived reference (2.19), and
count-weighted the housing stock as a whole runs 2.61×. Every other fix
in this table pushed the ratio *down*; correcting the population pushed
it back *up* by more than every other fix combined pushed it down —
which is the right outcome for a correction, not a sign the earlier work
was wasted: the earlier fixes (window U-value, refurbishment variants,
comfort setpoint, DHW/cooking) are all still real and still applied, and
still improve buem's accuracy on the *real* housing stock. They were
just being measured against the wrong population until now. What remains
open is a real, unresolved gap between calculated and metered demand,
not yet decomposed further than the contributors already applied above.
