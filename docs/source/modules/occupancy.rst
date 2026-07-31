occupancy — Occupancy & Electricity Profiles
=============================================

:Source: `UU-BUEM/occupancy <https://github.com/UU-BUEM/occupancy>`_ (external, optional)

Purpose
-------

Generate stochastic annual occupancy schedules and hourly
electricity/internal-gains profiles, for both households and
non-residential (service) buildings.

.. note::
   Occupancy modeling was split out of buem into its own repository.
   Install it with ``pip install buem[occupancy]``; without it,
   ``AttributeBuilder.generate_electricity_profile`` raises ``ImportError``
   rather than silently falling back to a placeholder profile — see
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

Both paths converge on ``occupancy.to_buem_profiles(result)``, which
converts either result type into buem's four required series — this
conversion is use-type-agnostic (confirmed by direct inspection of
``occupancy.core.buem_adapter``): ``occ_sleeping`` simply stays at 0 for
service-building types that never register overnight presence, rather
than needing separate household/service-building formulas.

- ``Q_ig`` — internal gains [kW]
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
   Known gap: ``building_type`` currently only selects *which* occupancy
   generator runs — it doesn't yet pick a household-size-appropriate
   occupancy archetype (occupancy's own archetypes — ``generic``,
   ``working_couple``, ``family_with_children``, ``retired_single``,
   ``student_shared`` — vary by composition) when the caller doesn't
   specify ``num_persons`` explicitly. See buem's
   ``.claude/residential/open.md``.
