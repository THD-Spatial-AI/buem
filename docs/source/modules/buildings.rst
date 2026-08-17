Buildings Module
================

The ``buem.buildings`` module maps raw LOD2 geometry and TABULA typology data
into canonical ``Building`` objects.  These objects carry all envelope, thermal,
and identity information required by the thermal model.

.. contents:: Sections
   :local:
   :depth: 2


Sub-packages
------------

components
^^^^^^^^^^
Dataclass definitions for each envelope element type: wall, roof, floor,
window, door, and ventilation.  All inherit from ``EnvelopeElement``
(``components.base``).

mapping
^^^^^^^
Orchestration of the LOD2 + TABULA pipeline:

- ``lod2_mapper.LOD2Mapper`` — main pipeline entry point (offline
  Excel/PostgreSQL batch pipeline)
- ``wall_classifier.SharedWallDetector`` — party wall detection (offline
  pipeline only — needs a full cross-building surface table)
- ``element_factory`` — ``WallInfo``, front/back wall identification, and
  window/door/ventilation element creation — shared by both the offline
  pipeline and the live request-handling path below
- ``tabula_helpers`` — TABULA variant selection, window ratios, safe
  numerics, and archetype lookup-by-match (for the live path)
- ``live_synthesis`` — internal LOD2 → LOD3 synthesis for the live
  request-handling path (no attached LOD2 surface table); see
  :ref:`buildings-live-path` below

datasources
^^^^^^^^^^^
Data ingestion from PostgreSQL (``pg_source``), Excel (``excel_source``),
or a plain CSV export in the same schema (``csv_source`` — built for a
one-off regional drop that isn't an Excel workbook or a live Postgres
connection). ``cityjson_extractor``/``nl_archetype_mapper``/
``rivm_energy_labels`` are a related but distinct set of tools: they
*produce* a ``csv_source``-compatible CSV pair directly from a CityJSON
(3D BAG) source plus real Dutch archetype/energy-label data, rather than
reading an existing export — see :doc:`netherlands`.

generator
^^^^^^^^^
v3 GeoJSON file writer (``json_generator``).


.. _buildings-live-path:

LOD2 → LOD3 in the live request-handling path
-----------------------------------------------

Everything documented on this page was originally written for the *offline*
Excel/PostgreSQL batch pipeline (``LOD2Mapper`` above, run via
``python -m buem.buildings.pipeline``). EnerPlanET's API contract
deliberately does **not** require window/door/ventilation ("LOD3") detail
from a client — their UI avoids asking general users to fill it in — so
buem must compute it internally whenever a caller (a live API request,
buem's own module-level config default, or a direct ``CfgBuilding``/
``AttributeBuilder`` call) supplies wall/roof/floor ("LOD2") geometry
without it.

``buem.buildings.mapping.live_synthesis.synthesize_missing_openings()``
applies the *same* documented rules on this page (front/back wall
identification, proportional window/door ratios, ventilation opening
sizing) to that geometry, reusing
:func:`~buem.buildings.mapping.element_factory.synthesize_openings` — the
one function both this offline pipeline and the live path call. It is
wired into ``CfgBuilding.to_cfg_dict()``, the single point both the live
API path (``AttributeBuilder`` → ``CfgBuilding``) and the config-only path
converge on, so both are covered uniformly. Three differences from the
offline pipeline, each a consequence of not having a full per-building
LOD2 surface table available for a single-building request:

- **Party (shared) wall detection** uses each wall's own
  ``b_transmission == 0`` instead of cross-building ``surface_feature_id``
  matching — see "Party (Shared) Walls" below; the resulting rule (no
  windows/doors/ventilation on shared walls) is identical.
- **The TABULA archetype is *matched*, not looked up by a per-building
  foreign key**: from ``building_type`` + ``construction_period`` +
  ``country`` (already forwarded end-to-end from a real v3 API request —
  see ``CLAUDE.md`` "v2 vs v3/v4 request formats"), or an explicit
  ``bldg_tabula_id`` override, via
  :func:`~buem.buildings.mapping.tabula_helpers.lookup_tabula_archetype`
  against the same bundled TABULA reference sheet
  (``tabula_building_child_features.xlsx``, currently ``Code_Country ==
  "DE"`` only).
- **No match falls back to documented safe-default ratios** (below)
  instead of failing — windows measurably affect heat loss/gain even at a
  modest share of envelope area, so buem always synthesizes something
  physically plausible rather than leaving a building with zero glazing.
  A ``logging.warning`` names exactly which component(s) were filled this
  way, so it is visible, not silent.

An explicitly-supplied, non-empty ``Windows``/``Doors``/``Ventilation``
component is never overridden — EnerPlanET "can provide [LOD3 detail]...
but does not have to".

**Window/door azimuth and tilt always match their parent surface**
(``buem.buildings.mapping.live_synthesis.normalize_opening_azimuths()``,
added 2026-08-14): a window or door is physically embedded in its host
wall (or roof, for a skylight) and cannot face a different direction or
slope than that surface. Whenever a Window/Door element declares a
``surface``/``parent_id`` reference to a known Wall or Roof element, its
``azimuth``/``tilt`` are forced to match that surface's own values —
correcting a caller-supplied mismatch (logged as a warning) rather than
rejecting the request over a redundant, derivable field. Applied after
opening synthesis, so it is a no-op for internally-synthesized openings
(already consistent by construction) and only has an effect on explicit
caller-supplied LOD3 detail. Ventilation is excluded — the ISO 13790
model uses only air change rates, not physical opening azimuth/tilt (see
"Ventilation" below), and internally-synthesized ventilation elements
don't carry those fields at all. Elements with no resolvable parent are
left as-is.

**Which walls receive openings stays purely a synthesis-time decision**:
the front/back/side wall eligibility rules below (which wall gets a door,
which get windows, party walls get none) only ever apply when buem itself
is choosing where to place *missing* openings. They are never used to
validate or reject explicitly caller-supplied Windows/Doors/Ventilation
placement — a real building may legitimately have openings that don't
follow this simplified heuristic (e.g. a door on a side wall), and
EnerPlanET's own data is authoritative when supplied.


.. _buildings-assumptions:

Assumptions
-----------

The building mapper makes a number of simplifying assumptions when converting
LOD2 geometry and TABULA statistical data into a thermal model input.  These
are documented here for transparency and reproducibility.

Geometry & Surface Classification
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 45 55

   * - Assumption
     - Rationale / Source

   * - Surfaces with area < 0.01 m² are discarded
     - LOD2 geometry computations produce floating-point artefacts
       (e.g. 1.1 × 10⁻¹⁶ m²) that have no physical meaning.

   * - ``objectclass_id`` 709 → Wall, 710 → Ground, 712 → Roof
     - CityGML LOD2 convention for thematic surfaces.

   * - Wall tilt is always 90° (vertical)
     - LOD2 walls are planar; any stored tilt is ignored.

   * - Roof tilt: negative or NaN → 0° (flat)
     - Negative tilt values in the database are artefacts; 0° is the safe
       default per pvlib convention (horizontal = 0°).

   * - Floor tilt is always 0°; azimuth always 0°
     - Ground slabs are horizontal; azimuth is irrelevant for floors.

   * - Roof azimuth: real value when the source DB has one; negative or
       NaN → 0° (North) — same convention as walls
     - **Corrected 2026-08-18** — previously hardcoded to 0° unconditionally
       on the claim that "roof azimuth has no role in the model." Checked
       against the actual ``model_buem._calcRadiation()`` implementation:
       every element's own azimuth *and* tilt are passed to
       ``pvlib.irradiance.get_total_irradiance()``, so roof solar gain is
       genuinely azimuth-dependent (a west-facing roof plane gets
       different plane-of-array irradiance than an east-facing one at the
       same tilt). The real German LOD2 database has a usable azimuth for
       10,732/16,558 (64.8%) of roof surfaces — was being discarded.
       Netherlands (:doc:`netherlands`) was unaffected — that path always
       computed a real per-plane azimuth from CityJSON geometry directly.

   * - Wall azimuth: negative or NaN → 0° (North)
     - Some LOD2 databases store −1 for unknown azimuth.  North is chosen as
       a conservative fallback (lowest solar gains in the Northern Hemisphere).


.. _buildings-cityjson-geometry:

Netherlands (Loenen) data pipeline
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Everything above this point describes ``LOD2Mapper``'s own assumptions
about its *input* — a source table where ``surface_area``/``tilt``/
``azimuth``/``tabula_variant_code_id`` already exist as columns. For
Germany that table comes from the Excel/PostgreSQL ``city2tabula``
pipeline. The Netherlands (Loenen) pipeline generates that same input
shape from scratch instead (geometry directly from CityJSON, archetype
matching independent of city2tabula) — given how much is specific to it,
it has its own dedicated page rather than living here alongside the
German-pipeline assumption tables above: :doc:`netherlands`.


Party (Shared) Walls
^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 45 55

   * - Assumption
     - Rationale / Source

   * - A wall is *shared* when its ``surface_feature_id`` appears under
       two or more buildings
     - CityGML convention: adjacent buildings reference the same surface.

   * - Shared walls have U = 0, b_transmission = 0
     - Under the assumption that both adjacent buildings maintain similar
       indoor temperatures, no net heat flows across the party wall (analogous
       to TABULA's adiabatic party-wall treatment).

   * - Shared walls receive no windows, doors, or ventilation openings
     - Party walls are interior partition surfaces.


Front / Back Wall Identification
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 45 55

   * - Assumption
     - Rationale / Source

   * - The front wall is the exposed wall with the largest surface area
     - The main entrance façade of European residential buildings is typically
       the widest exposed face.

   * - The back wall is the exposed wall whose azimuth is closest to 180°
       opposite the front wall (within 90° angular tolerance)
     - Provides the opposite façade for cross-ventilation.  If no wall falls
       within 90° of the ideal opposite, no back wall is assigned.

   * - Front wall receives: windows, door, and ventilation opening
     - Typical residential building entrance and primary window façade.

   * - Back wall receives: windows and ventilation opening
     - Rear façade provides cross-ventilation path and secondary glazing.

   * - Side walls receive: windows only (no doors or ventilation)
     - Side elevations have glazing but typically no entrance or openable
       ventilation pathways in the simplified model.


Window Sizing
^^^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 45 55

   * - Assumption
     - Rationale / Source

   * - Window area on each wall = ``(A_Window_<Direction> / A_Wall_1) × LOD2_wall_area``
     - TABULA provides directional window areas for the reference archetype;
       ratios are applied proportionally to actual LOD2 wall sizes.

   * - Walls smaller than 5 m² do not receive any windows
     - Small wall segments (gable fragments, narrow returns, chimney faces)
       rarely contain glazing in practice.

   * - Window elements with area < 0.01 m² are discarded
     - TABULA directional ratios can produce floating-point artefacts
       (e.g. east ratio ≈ 6.7 × 10⁻⁶) that yield negligible window areas.

   * - ``A_Wall_1`` (TABULA reference wall area) is used as the denominator for
       all directional ratios, regardless of which variant was selected
     - TABULA defines window ratios relative to variant 1; maintaining this
       denominator preserves the typological proportions.


Door Sizing
^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 45 55

   * - Assumption
     - Rationale / Source

   * - One door on the front wall only; area = ``(A_Door_1 / A_Wall_1) × front_wall_area``
     - Single main entrance proportional to facade size.

   * - Door is omitted when no front wall exists (all party walls)
     - Fully enclosed buildings (row houses with all shared walls) have no
       exterior entrance in the simplified LOD2 model.


Ventilation
^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 45 55

   * - Assumption
     - Rationale / Source

   * - Front wall ventilation opening: 1.0 m² (capped at 10 % of wall area)
     - Representative of a large window/door openable area for natural
       ventilation on the primary façade.

   * - Back wall ventilation opening: 0.5 m² (capped at 10 % of wall area)
     - Smaller opening on the rear façade for cross-ventilation path.

   * - Cross-ventilation: ``n_air_use`` is split equally between front and
       back openings
     - Balanced airflow when both inlet and outlet are available.

   * - Single-sided ventilation: full ``n_air_use`` on front wall only
     - When no back wall exists, all purposeful ventilation occurs through
       the front façade.

   * - Fully enclosed (all party walls): infiltration-only placeholder
     - No natural ventilation possible; only uncontrolled air leakage.

   * - The thermal model (ISO 13790) uses only air change rates, not
       physical opening areas
     - Opening areas are metadata: they reduce opaque wall area for accurate
       transmission loss accounting and serve as documentation for future
       advanced ventilation models.


TABULA Variant Selection
^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 45 55

   * - Assumption
     - Rationale / Source

   * - For each component (wall, roof, floor), the *primary variant* is the one
       with the largest area AND ``b_transmission > 0``
     - Ensures the dominant exterior-facing variant is used for thermal
       calculations; variants with ``b_transmission = 0`` are interior or
       adiabatic elements.

   * - If no variant has ``b_transmission > 0``, variant 1 is used as fallback
     - Variant 1 is the TABULA typology's main exterior component.


Thermal Properties
^^^^^^^^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 45 55

   * - Assumption
     - Rationale / Source

   * - ``F_sh_hor`` = 0.80 (default horizontal shading factor)
     - ISO 13790 §11.4.4; typical value for moderate European climate with
       some horizon obstructions.

   * - ``F_sh_vert`` = 0.75 (default vertical shading factor)
     - ISO 13790 §11.4.4; accounts for vertical obstructions (neighbouring
       buildings, vegetation).

   * - ``F_f`` = 0.20 (window frame area fraction)
     - ISO 13790 §11.4.5; 20 % frame area is typical for standard window
       frames.

   * - ``F_w`` = 1.0 (window correction factor)
     - Non-scattering glazing per ISO 13790 §11.3.3.

   * - ``b_transmission`` = 0.5 for ground-contact floors (TABULA default)
     - Temperature correction factor for unheated cellar or ground contact.

   * - Missing TABULA values use safe defaults: ``n_air_infiltration`` = 0.5 1/h,
       ``n_air_use`` = 0.5 1/h, ``c_m`` = 165 kJ/(m²K), ``h_room`` = 2.5 m
     - ISO 13790 / TABULA typical values for existing residential buildings.

   * - **Live request-handling path only** (see
       :ref:`buildings-live-path`): when no TABULA archetype can be matched
       for a caller-supplied ``building_type``/``construction_period``/
       ``country``, window/door/ventilation sizing falls back to a flat
       15 % window-to-wall ratio per cardinal direction, a 5 % door-to-wall
       ratio, ``U_Window`` = 2.8 W/(m²K), ``g_gl`` = 0.5, ``U_Door`` =
       3.0 W/(m²K), ``n_air_use`` = 0.5 1/h
     - Not TABULA-derived — a first-pass heuristic, logged as a warning
       naming the affected component(s) rather than applied silently. 15 %
       sits mid-range for existing European residential stock (the bundled
       TABULA archetypes here run roughly 8–25 % depending on era/type);
       the door ratio gives a ~2 m² door on a typical ~40 m² front wall.
       See ``buem.buildings.mapping.live_synthesis``.

   * - ``phi_int`` — specific internal heat gains [W/m²] from TABULA
     - Per-typology internal gains (occupants + appliances).  ``None`` when not
       available → model uses its own scheduling-based internal gains profile.

   * - ``q_w_nd`` — specific hot-water demand [kWh/(m²·a)] from TABULA
     - Annual energy for domestic hot water normalised by reference floor area.
       Ranges from 10 to 15 kWh/(m²·a) in the German TABULA dataset.

   * - ``design_T_min`` — outdoor design temperature [°C] from TABULA ``Theta_e``
     - Used for peak heating load sizing.  Default −12 °C (German DIN 4710).

   * - ``F_red_htr`` — heating reduction factor (0–1) from TABULA ``F_red_htr1``
     - Reduces transmission losses for unheated adjacent spaces (stairwells,
       corridors).  Default 1.0 (no reduction).  German data: 0.85–0.95.

   * - ``comfortT_lb`` — heating setpoint [°C] from TABULA ``theta_i``
     - The matched archetype's own assumed indoor heating setpoint, applied
       as a constant lower comfort bound for every hour (no TABULA-equivalent
       night/weekend setback). Fixed 2026-08-15 — previously never read;
       every LOD2-mapped building silently used the generic 21.0 °C default
       regardless of what its archetype specified. Falls back to 21.0 °C
       when the matched row has no ``theta_i`` value. ``comfortT_ub`` has no
       TABULA row equivalent (TABULA's residential reference calculation is
       heating-only) and keeps its own 24.0 °C default unconditionally.


TABULA Column Mapping
^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 30 30 15 25

   * - v3 Schema Field
     - TABULA Column
     - Unit
     - Default

   * - ``n_air_infiltration``
     - ``n_air_infiltration``
     - 1/h
     - 0.5

   * - ``n_air_use``
     - ``n_air_use``
     - 1/h
     - 0.5

   * - ``c_m``
     - ``c_m``
     - kJ/(m²K)
     - 165.0

   * - ``h_room``
     - ``h_room``
     - m
     - 2.5

   * - ``design_T_min``
     - ``Theta_e``
     - °C
     - −12.0

   * - ``F_sh_hor``
     - ``F_sh_hor``
     - —
     - 0.80

   * - ``F_sh_vert``
     - ``F_sh_vert``
     - —
     - 0.75

   * - ``F_f``
     - ``F_f``
     - —
     - 0.20

   * - ``F_w``
     - ``F_w``
     - —
     - 1.0

   * - ``phi_int``
     - ``phi_int``
     - W/m²
     - (model default)

   * - ``q_w_nd``
     - ``q_w_nd``
     - kWh/(m²a)
     - (not provided)

   * - ``F_red_htr``
     - ``F_red_htr1``
     - —
     - 1.0

   * - ``comfortT_lb``
     - ``theta_i``
     - °C
     - 21.0

   * - per-element ``U``
     - ``U_Wall_1/2/3``, ``U_Roof_1/2``, ``U_Floor_1/2``, ``U_Window_1``, ``U_Door_1``
     - W/(m²K)
     - (required)

   * - per-element ``b_transmission``
     - ``b_Transmission_Wall_1/2/3``, ``b_Transmission_Roof_1/2``, ``b_Transmission_Floor_1/2``
     - —
     - 1.0

   * - per-element ``g_gl``
     - ``g_gl_n_Window_1``
     - —
     - 0.5
