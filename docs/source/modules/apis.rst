apis — REST API Server
======================

:Source: ``buem/apis/``

Purpose
-------

Expose BuEM as a Flask REST API for external systems.  The server is
typically run behind Gunicorn inside a Docker container.

Endpoints
---------

.. list-table::
   :header-rows: 1
   :widths: 12 18 70

   * - Method
     - Route
     - Description
   * - POST
     - ``/api/run``
     - Run the thermal model for a single building configuration (JSON).
       Returns heating/cooling summary ± full timeseries.
   * - POST
     - ``/api/process``
     - Process a GeoJSON FeatureCollection through the batch pipeline
       (``GeoJsonProcessor``).  Returns a FeatureCollection with results
       appended to each feature.
   * - GET
     - ``/api/files/<filename>``
     - Download a result file (timeseries JSON).  Paths are
       sanitised to prevent directory traversal.
   * - GET
     - ``/api/health``
     - Health check — returns status, version, timestamp.

Query parameters (``/api/run``, ``/api/process``):

- ``include_timeseries`` (bool) — attach hourly arrays to the response
- ``use_milp`` (bool) — use the experimental MILP solver path

Files
-----

api_server.py
  ``create_app()`` — Flask application factory.  Registers blueprints
  ``model_bp`` and ``files_bp``, configures rotating log handler (5 MB,
  3 backups).

model_api.py
  ``/api/run`` and ``/api/process`` implementations.  Validates payload via
  ``CfgBuilding`` → ``validate_cfg()``, runs model, optionally forwards
  results to an external URL.

files_api.py
  ``/api/files/<filename>`` — wraps ``send_from_directory()`` with
  filename sanitisation.  Result directory is set by the
  ``BUEM_RESULTS_DIR`` environment variable.
