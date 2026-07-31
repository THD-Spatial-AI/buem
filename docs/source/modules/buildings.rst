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

- ``lod2_mapper.LOD2Mapper`` — main pipeline entry point
- ``wall_classifier.SharedWallDetector`` — party wall detection
- ``element_factory`` — window, door, ventilation element creation
- ``tabula_helpers`` — TABULA variant selection, window ratios, safe numerics

datasources
^^^^^^^^^^^
Data ingestion from PostgreSQL (``pg_source``) or Excel (``excel_source``).

generator
^^^^^^^^^
v3 GeoJSON file writer (``json_generator``).


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

   * - Roof azimuth is always 0° (placeholder)
     - Roof azimuth has no role in the ISO 13790 5R1C model; the solar irradiance
       on roofs (horizontal windows) uses tilt only.

   * - Wall azimuth: negative or NaN → 0° (North)
     - Some LOD2 databases store −1 for unknown azimuth.  North is chosen as
       a conservative fallback (lowest solar gains in the Northern Hemisphere).


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
