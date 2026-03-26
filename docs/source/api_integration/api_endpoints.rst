API Endpoints
=============

Base URL: ``http://localhost:5000``  (default)

POST /api/process
-----------------

Submit a GeoJSON **FeatureCollection** for batch thermal analysis.

.. list-table::
   :header-rows: 1
   :widths: 20 15 15 50

   * - Parameter
     - Type
     - Required
     - Description
   * - ``include_timeseries``
     - bool
     - No
     - Attach hourly arrays to each feature (default ``false``)
   * - ``use_milp``
     - bool
     - No
     - Use experimental MILP solver (default ``false``)

.. code-block:: bash

   curl -X POST "http://localhost:5000/api/process?include_timeseries=true" \
     -H "Content-Type: application/json" \
     -d @request.geojson

**200 OK** — returns a GeoJSON FeatureCollection with
``thermal_load_profile`` added to each feature's ``properties.buem``.

POST /api/run
-------------

Run the thermal model for a **single building** configuration (plain JSON,
not GeoJSON).

Same query parameters as ``/api/process``.

.. code-block:: bash

   curl -X POST "http://localhost:5000/api/run" \
     -H "Content-Type: application/json" \
     -d @building.json

**200 OK** — returns heating/cooling summary and optional timeseries.

GET /api/files/<filename>
-------------------------

Download a timeseries result file.

The ``timeseries_file`` path returned in a model response can be used
directly:

.. code-block:: bash

   curl "http://localhost:5000/api/files/buem_ts_abc123.json" -o ts.json

GET /api/health
---------------

Health check.

.. code-block:: json

   {"status": "healthy", "version": "0.1.2", "timestamp": "..."}

Error Responses
---------------

All endpoints return a consistent error envelope:

.. code-block:: text

   400  Invalid JSON or missing fields
   422  Valid JSON but invalid building attributes
   404  File or endpoint not found
   500  Model execution error

.. code-block:: json

   {
     "error": {
       "code": "VALIDATION_ERROR",
       "message": "Building attribute validation failed",
       "details": ["components.Walls.U must be positive"]
     }
   }

.. note::

   Authentication and rate limiting are **not** built into BuEM.  For
   production use, add these at the reverse-proxy layer (e.g. nginx).