Integration Examples
====================

Starting the Server
-------------------

.. code-block:: bash

    # Conda
    conda activate buem_env
    python -m buem.apis.api_server

    # Docker
    docker compose up

Health Check
------------

.. code-block:: bash

    curl http://localhost:5000/api/health

Process a GeoJSON File
----------------------

.. code-block:: bash

    curl -X POST http://localhost:5000/api/process \
       -H "Content-Type: application/json" \
       -d @src/buem/integration/sample_request_template.geojson

To include hourly time-series in the response:

.. code-block:: bash

    curl -X POST "http://localhost:5000/api/run?include_timeseries=true" \
       -H "Content-Type: application/json" \
       --data-binary @payload.json

Python Helper
-------------

BuEM ships a convenience script for submitting requests:

.. code-block:: bash

    python -m buem.integration.send_geojson \
        src/buem/integration/sample_request_template.geojson \
        --include-timeseries

Minimal Python Client
---------------------

.. code-block:: python

    import requests

    payload = {
        "type": "FeatureCollection",
        "features": [{
            "type": "Feature",
            "id": "B001",
            "geometry": {"type": "Point", "coordinates": [5.0, 52.0]},
            "properties": {
                "buem": {
                    "building_attributes": {
                        "latitude": 52.0,
                        "longitude": 5.0,
                        "A_ref": 100.0,
                        "components": {
                            "Walls": {"U": 1.5, "elements": [
                                {"id": "W1", "area": 80, "azimuth": 180, "tilt": 90}
                            ]},
                            "Ventilation": {"elements": [
                                {"id": "V1", "air_changes": 0.5}
                            ]}
                        }
                    }
                }
            }
        }]
    }

    resp = requests.post("http://localhost:5000/api/process", json=payload, timeout=60)
    resp.raise_for_status()
    result = resp.json()

    thermal = result["features"][0]["properties"]["buem"]["thermal_load_profile"]
    print(f"Heating: {thermal['heating_total_kWh']:.0f} kWh/yr")
    print(f"Cooling: {thermal['cooling_total_kWh']:.0f} kWh/yr")

Downloading Time-Series Files
-----------------------------

When ``include_timeseries=true``, the response contains a ``timeseries_file`` path.
Retrieve it with:

.. code-block:: bash

    curl -O http://localhost:5000/api/files/buem_ts_<hash>.json.gz

Result Forwarding
-----------------

Add ``forward_url`` to the request payload to have BuEM POST results to an
external endpoint automatically:

.. code-block:: json

    {
        "forward_url": "https://example.com/receiver",
        "include_timeseries": false
    }

Environment Variables
---------------------

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Variable
     - Description
   * - ``BUEM_WEATHER_DIR``
     - Path to weather CSV directory
   * - ``BUEM_CBC_EXE``
     - Path to CBC solver binary (MILP only)
   * - ``BUEM_RESULTS_DIR``
     - Directory for saved result files
   * - ``BUEM_LOG_FILE``
     - Log file path (default: ``logs/buem_api.log``)
