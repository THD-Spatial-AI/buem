API Integration
===============

BuEM exposes a REST API that receives GeoJSON building descriptions and
returns thermal-load results.  This section explains the endpoints, payload
formats, and Docker setup needed to integrate BuEM with other models.

.. note::
   The request/response schema (currently v3) is a **versioned, mutually
   agreed contract with EnerPlanET**, not something BuEM changes
   unilaterally — see ``src/buem/integration/json_schema/VERSIONING.md``
   for the semver/release policy and the repository root ``CLAUDE.md``
   "Guardrails" section for how proposed (not-yet-agreed) changes are
   staged as a draft version before becoming official.

.. toctree::
   :maxdepth: 2

   docker_setup
   api_endpoints
   request_format
   response_format
   error_handling
   examples