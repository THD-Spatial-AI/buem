occupancy — Occupancy & Electricity Profiles
=============================================

:Source: `UU-BUEM/occupancy <https://github.com/UU-BUEM/occupancy>`_ (external, compulsory)

Purpose
-------

Generate stochastic annual occupancy schedules and hourly
electricity/internal-gains profiles, for both households and
non-residential (service) buildings.

.. note::
   Occupancy modeling was split out of buem into its own repository, and
   is a **compulsory** dependency (2026-08-07) — imported unconditionally,
   same treatment as ``weather``. There is no synthetic fallback:
   ``AttributeBuilder.generate_electricity_profile`` raises if the
   generation itself fails, and a missing ``occupancy`` install now fails
   at module-import time rather than at first request — see
   ``modules/config.rst``'s note on required attributes for the same
   "raise rather than silently substitute" convention.

HouseholdProfile / ElectricityConsumptionProfile
-------------------------------------------------

For residential buildings (TABULA size classes ``SFH``/``MFH``/``TH``/
``AB``): ``occupancy.HouseholdProfile(num_persons, year, seed)`` generates
per-hour occupancy state, wrapped by
``occupancy.ElectricityConsumptionProfile`` to add appliance/equipment
power.

ServiceBuildingProfile
-----------------------

For non-residential buildings, any of occupancy's 8 registered
service-building types (``supermarket``, ``office``, ``restaurant``,
``school``, ``hotel``, ``bakery``, ``warehouse``, ``clinic``):
``occupancy.ServiceBuildingProfile(building_type, year, capacity, seed)`` —
occupancy and equipment power are combined in a single profile (no
separate electricity-profile wrapper needed, unlike households).
``capacity`` is optional; when omitted, the service type's own registered
default capacity applies.

to_buem_profiles
-----------------

Both paths converge on ``occupancy.to_buem_profiles(result, floor_area_m2=...)``,
which converts either result type into buem's four required series — this
conversion is use-type-agnostic (confirmed by direct inspection of
``occupancy.core.buem_adapter``): ``occ_sleeping`` simply stays at 0 for
service-building types that never register overnight presence, rather
than needing separate household/service-building formulas.

- ``Q_ig`` — internal gains [kW]. For service buildings, blends occupancy's
  per-occupant gain with an area-normalized equipment/lighting component
  (occupancy v3.1.0+, ``gain_w_per_m2`` per building type) when
  ``floor_area_m2`` is given — see Integration below. Households don't get
  this component (occupancy's household archetypes leave ``gain_w_per_m2``
  unset).
- ``elecLoad`` — electricity load [kW]
- ``occ_nothome`` — fraction of occupants away, per hour
- ``occ_sleeping`` — fraction of present occupants asleep/inactive, per hour

Integration
-----------

:File: ``src/buem/integration/scripts/attribute_builder.py``
   (``AttributeBuilder.generate_electricity_profile``)

Branches on ``building_type`` (from the merged request attributes):

1. A TABULA residential code (``RESIDENTIAL_BUILDING_TYPES`` in
   ``src/buem/config/cfg_attribute.py`` — ``SFH``/``MFH``/``TH``/``AB``,
   or unset) → ``HouseholdProfile`` + ``ElectricityConsumptionProfile``,
   using the request's ``num_persons``.
2. Any of occupancy's 8 service-building type ids → ``ServiceBuildingProfile``,
   using the request's ``capacity`` (may be omitted).
3. Anything else → a clear ``ValueError`` naming the valid set, rather than
   silently defaulting to a household.

The resulting ``Q_ig``/``elecLoad``/``occ_nothome``/``occ_sleeping`` series
are reindexed onto the weather timeseries and written into the merged
config passed to ``ModelBUEM``.

.. note::
   Archetype selection (2026-08-07): a new optional ``archetype`` request
   attribute is passed straight through to ``HouseholdProfile`` when
   supplied. When omitted, ``cfg_attribute.DEFAULT_ARCHETYPE_BY_BUILDING_TYPE``
   maps ``building_type`` to one of occupancy's registered archetypes
   (``generic``, ``working_couple``, ``family_with_children``,
   ``retired_single``, ``student_shared``) as a first-pass default —
   **a heuristic, not a derivation**: TABULA's ``SFH``/``MFH``/``TH``/``AB``
   describe building form, not household composition, so ``num_persons``
   remains the dominant, caller-driven signal. See buem's
   ``.claude/residential/resolved.md``.

.. note::
   Floor-area-normalized gains (2026-08-07, occupancy v3.1.0+): the
   service-building branch resolves ``floor_area_m2`` from the request's
   ``A_ref`` and passes it to ``to_buem_profiles()``, blending an
   area-driven equipment/lighting component into ``Q_ig`` rather than
   using occupant count alone. The residential branch always passes
   ``None`` (household archetypes carry no ``gain_w_per_m2``). One
   residual caveat: a v3-format request that omits ``A_ref`` gets a flat
   ``100.0`` placeholder from ``geojson_validator.py``, not the true
   geometry-derived floor area computed later by ``CfgBuilding`` — a
   pre-existing, separately tracked issue this inherits rather than
   introduces. See ``.claude/occupancy_gains_handoff.md`` "Gap 1".

.. note::
   ``capacity``/``num_persons``/``archetype`` now also reach a real v3
   (live) API request (2026-08-07) — ``geojson_validator.py::
   _convert_v3_to_v2()`` forwards them from the request's ``building``
   object. ``seed`` is deliberately not forwarded (or accepted by any
   request schema at all): it's an internal RNG-reproducibility knob, not
   a client-facing modeling input. See ``.claude/occupancy_gains_handoff.md``
   "Gap 2" and its "Seed ownership" note.

.. note::
   ``occupancy.SERVICE_BUILDING_TYPES`` (top-level export, occupancy
   v3.1.0+) is the single runtime source of truth for the 8 registered
   service-building type ids. The ``versions/v4/`` draft schema's
   ``building_type`` enum is a necessarily-static snapshot of the same
   set (JSON Schema can't import it); ``tests/test_building_types.py::
   test_v4_building_type_enum_matches_occupancy`` is a drift guard that
   fails CI if the two fall out of sync. See
   ``.claude/occupancy_gains_handoff.md`` "Gap 3".
