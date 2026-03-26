Response Format
===============

BuEM returns a GeoJSON FeatureCollection with thermal-load results appended
to each feature.

Top-Level Response
------------------

.. code-block:: javascript

   {
     "type": "FeatureCollection",
     "processed_at": "2026-03-26T10:30:00Z",
     "processing_elapsed_s": 2.45,
     "features": [/* ... */]
   }

Thermal Load Profile
--------------------

Each processed feature receives a ``thermal_load_profile`` inside
``properties.buem``:

.. list-table::
   :header-rows: 1
   :widths: 28 12 60

   * - Field
     - Units
     - Description
   * - ``heating_total_kWh``
     - kWh
     - Annual heating demand
   * - ``heating_peak_kW``
     - kW
     - Peak heating power
   * - ``cooling_total_kWh``
     - kWh
     - Annual cooling demand (absolute value)
   * - ``cooling_peak_kW``
     - kW
     - Peak cooling power (absolute value)
   * - ``electricity_total_kWh``
     - kWh
     - Annual building electricity (excl. HVAC)
   * - ``electricity_peak_kW``
     - kW
     - Peak electricity demand
   * - ``n_points``
     - —
     - Number of hourly data points (8760)
   * - ``elapsed_s``
     - s
     - Processing time for this building
   * - ``timeseries_file``
     - —
     - Download path (present when ``include_timeseries=true``)

Internally the solver returns positive :math:`Q_{\text{HC}}` for heating and
negative for cooling.  The API converts cooling to absolute values for
consistency.

Timeseries File
---------------

When ``include_timeseries=true``, a JSON file is written to disk and its path
is returned in ``timeseries_file``.  Download it via the ``/api/files/``
endpoint:

.. code-block:: bash

   curl "http://localhost:5000/api/files/buem_ts_abc123.json" -o ts.json

Structure:

.. code-block:: json

   {
     "index": ["2018-01-01T00:00:00Z", "..."],
     "heat":  [2.1, 2.3, "..."],
     "cool":  [-0.5, -0.8, "..."],
     "electricity": [0.8, 0.9, "..."]
   }

Feature-Level Errors
--------------------

If a building fails validation or execution, the feature still appears in the
response with an ``error`` field instead of ``thermal_load_profile``:

.. code-block:: json

   {
     "type": "Feature",
     "id": "B002",
     "properties": {
       "buem": {
         "error": "components.Walls.U must be positive"
       }
     }
   }