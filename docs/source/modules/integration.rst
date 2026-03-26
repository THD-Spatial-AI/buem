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

1. Validate the incoming GeoJSON structure (features, ``properties.buem``).
2. For each feature:

   a. Extract ``building_attributes`` from ``properties.buem``.
   b. Merge with database attributes (if a ``db_fetcher`` is provided) and
      ATTRIBUTE_SPECS defaults.
   c. Run ``ModelBUEM.sim_model()``.
   d. Compute summary statistics (total kWh, peak kW).

3. Return a GeoJSON FeatureCollection with ``thermal_load_profile`` appended
   to each feature's properties.

Result caching is hash-based: identical building configurations reuse
previously computed results when caching is enabled.

attribute_builder.py
--------------------

Merges three attribute sources in priority order:

1. Feature payload
2. Database record
3. ``ATTRIBUTE_SPECS`` defaults

send_geojson.py
---------------

Utility script for submitting a GeoJSON file to the API from the command
line — useful during development and integration testing.

Schema CLI
----------

``schema_cli.py`` is a helper tool for versioning and validating BuEM
request/response JSON Schemas.  Supports ``list-versions``,
``validate <file>``, ``test-all``, and ``import-version``.
