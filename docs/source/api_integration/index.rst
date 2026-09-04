API Integration
===============

BuEM exposes a REST API that receives GeoJSON building descriptions and
returns thermal-load results.  This section explains the endpoints, payload
formats, and Docker setup needed to integrate BuEM with other models.

.. note::
   The request/response schema (currently contract v5) is owned by
   ``enerplanet/buem-gateway`` — BuEM keeps a pinned, verbatim copy in
   ``src/buem/integration/json_schema/`` (see that folder's
   ``README.md``), not something this repo changes unilaterally. See the
   repository root ``CLAUDE.md`` "Guardrails" section for how contract
   changes are proposed and how the pinned copy is re-synced.

.. toctree::
   :maxdepth: 2

   docker_setup
   api_endpoints
   request_format
   response_format
   error_handling
   examples