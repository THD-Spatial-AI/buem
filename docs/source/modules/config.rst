config — Building Configuration
================================

:Source: ``buem/config/``

Purpose
-------

Ingests a building description (JSON dict or API payload), fills in defaults
for every missing attribute, validates the result, and exposes it to the
thermal model as a normalised Python object.

Key Components
--------------

cfg_attribute.py — Attribute Definitions
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Defines **250 +** building attributes in the ``ATTRIBUTE_SPECS`` dictionary.
Each entry specifies:

- **category** — WEATHER, FIXED, BOOLEAN, or OTHER
- **type** — FLOAT, INT, BOOL, STR, SERIES, DATAFRAME, OBJECT, LIST
- **default** — a sensible fallback (e.g. A_ref = 100 m², comfortT_lb = 21 °C)

Selected attributes:

.. list-table::
   :header-rows: 1
   :widths: 22 12 12 54

   * - Attribute
     - Category
     - Type
     - Default / Notes
   * - ``weather``
     - WEATHER
     - DataFrame
     - 8760 h (T, GHI, DNI, DHI), Loenen NL
   * - ``components``
     - OTHER
     - OBJECT
     - Hierarchical envelope (Walls, Roof, Floor, Windows, Doors, Ventilation)
   * - ``A_ref``
     - FIXED
     - FLOAT
     - 100.0 m²
   * - ``thermalClass``
     - FIXED
     - STR
     - ``"medium"``  (very light / light / medium / heavy / very heavy)
   * - ``c_m``
     - FIXED
     - FLOAT
     - 175.0 kJ/(m² K)
   * - ``comfortT_lb`` / ``comfortT_ub``
     - FIXED
     - FLOAT
     - 21.0 / 24.0 °C
   * - ``g_gl_n_Window``
     - FIXED
     - FLOAT
     - 0.5
   * - ``elecLoad``
     - FIXED
     - SERIES
     - Auto-generated from ``OccupancyProfile`` → ``ElectricityConsumptionProfile``
   * - ``ventControl``, ``control``
     - BOOLEAN
     - BOOL
     - Active configuration flags

Electricity and occupancy profiles are generated automatically when not
supplied by the caller.

cfg_building.py — Configuration Container
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Main entry point for consumers:

``CfgBuilding(cfg_dict)``
  Accepts a raw JSON/dict payload. Normalises it using ATTRIBUTE_SPECS
  defaults, converts serialisable dicts to pandas objects, and exposes
  ``to_cfg_dict()`` / ``to_serializable()`` for downstream use.

Helper dataclasses: ``WeatherConfig``, ``BooleanConfig``, ``FixedConfig``.

validator.py — Configuration Validator
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``validate_cfg(cfg_dict) → list[str]``

Returns an empty list when the configuration is valid.  Checks include:

- ``components`` tree present (not legacy ``A_*`` keys)
- Per-component U > 0 or per-element U provided
- Element areas > 0 and unique IDs
- Weather timeseries length consistent (8760 h)

Attribute Precedence
--------------------

When the API receives a request, attributes are resolved in this order:

1. **API payload** (highest priority)
2. **Database** (if a ``building_id`` is provided)
3. **ATTRIBUTE_SPECS defaults** (lowest priority)

Components Structure
--------------------

The ``components`` attribute follows this hierarchy:

.. code-block:: text

   components
   ├── Walls      → U [W/(m²K)], b_transmission, elements[{id, area, azimuth, tilt}]
   ├── Roof       → U, elements[{id, area, azimuth, tilt}]
   ├── Floor      → U, elements[{id, area}]
   ├── Windows    → U, g_gl, elements[{id, area, azimuth, tilt, surface_ref}]
   ├── Doors      → U, elements[{id, area, surface_ref}]
   └── Ventilation → elements[{id, air_changes}]

Orientations use azimuth 0–360° (0 = North, clockwise) and tilt 0–90°
(0 = horizontal, 90 = vertical).
