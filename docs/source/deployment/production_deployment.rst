Production Deployment
=====================

Docker is the recommended way to run BuEM in production. The repository
ships a ``Dockerfile`` and ``docker-compose.yml`` that handle the conda
environment, CBC solver binary, and Gunicorn entry-point.

Build and Run
-------------

.. code-block:: bash

    # Build the image
    docker build -t buem:latest .

    # Start via Compose (recommended)
    docker compose up -d

    # Verify
    curl http://localhost:5000/api/health

Environment Variables
---------------------

Set these in ``docker-compose.yml`` or pass with ``-e``:

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Variable
     - Description
   * - ``BUEM_WEATHER_DIR``
     - Path to weather CSV directory inside the container
   * - ``BUEM_CBC_EXE``
     - Path to CBC binary (MILP solver)
   * - ``BUEM_RESULTS_DIR``
     - Directory where result JSON files are stored
   * - ``BUEM_LOG_FILE``
     - Log file path (default ``logs/buem_api.log``)

Gunicorn Tuning
---------------

The entry-point script (``entrypoint.sh``) launches Gunicorn.
Adjust workers and timeout as needed:

.. code-block:: bash

    gunicorn -w 4 -b 0.0.0.0:5000 --timeout 120 buem.apis.api_server:app

A rule of thumb is ``2 * CPU_CORES + 1`` workers. Each worker can
process one building request at a time.

Reverse Proxy
-------------

Place Nginx (or another proxy) in front of Gunicorn for TLS termination
and static-file serving:

.. code-block:: nginx

    upstream buem {
        server 127.0.0.1:5000;
    }

    server {
        listen 80;
        location / {
            proxy_pass http://buem;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_read_timeout 120s;
        }
        location /api/health {
            access_log off;
            proxy_pass http://buem;
        }
    }

Health Checks
-------------

Use the ``/api/health`` endpoint for load-balancer or orchestrator probes:

.. code-block:: yaml

    # docker-compose snippet
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:5000/api/health"]
      interval: 30s
      timeout: 10s
      retries: 3