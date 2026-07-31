integration — GeoJSON Processing
=================================

:Source: ``buem/integration/``

Purpose
-------

Batch-process GeoJSON FeatureCollections through the thermal model and
assemble structured result payloads.

GeoJsonProcessor
----------------

:File: ``geojson_processor.py``

Workflow:

1. Validate the incoming GeoJSON structure (``geojson_validator.py``) —
   the current (v3) request shape nests attributes under
   ``properties.buem.building`` (``envelope``/``thermal``/``solver``);
   the validator converts this internally to the flat
   ``building_attributes`` shape ``AttributeBuilder`` consumes.
2. For each feature:

   a. Build the merged config via ``AttributeBuilder`` (see below).
   b. Run ``ModelBUEM.sim_model()``.
   c. Compute summary statistics (total kWh, peak kW).

3. Return a GeoJSON FeatureCollection with ``thermal_load_profile`` appended
   to each feature's properties.

Result caching (``result_cache.py``) is hash-based: identical building
configurations reuse previously computed results when caching is enabled.

attribute_builder.py
--------------------

``AttributeBuilder.build()`` — see :doc:`config`'s "Attribute Precedence"
for the full payload/database/defaults resolution rules, including which
attributes have no safe default and raise instead. Also routes occupancy
generation: household vs. service-building type selects
``occupancy.HouseholdProfile`` vs. ``occupancy.ServiceBuildingProfile`` —
see :doc:`occupancy`.

send_geojson.py
---------------

Utility script for submitting a GeoJSON file to the API from the command
line — useful during development and integration testing.

Schema CLI
----------

``schema_cli.py`` is a helper tool for versioning and validating BuEM
request/response JSON Schemas (backed by ``schema_manager.py``'s
``SchemaVersionManager``, which auto-discovers versions under
``json_schema/versions/``).  Supports ``list-versions``,
``validate <file>``, ``test-all``, and ``import-version``. Note:
``geojson_validator.py``'s actual runtime request validation does not
consult this manager — it's independent, hand-maintained marshmallow
schemas kept in sync with the current agreed version manually. See
``json_schema/VERSIONING.md`` and the repo root ``CLAUDE.md``
"Guardrails" for how contract changes are governed.
