Introduction
============

BuEM (Building Energy Model) is an open-source tool that calculates hourly
heating and cooling loads for buildings.  It implements the **ISO 13790 5R1C**
(five-resistor, one-capacitor) thermal-network model and solves an annual
energy-balance problem using a linear-programming (LP) formulation.

How It Works
------------

Given a building description (envelope U-values, areas, orientations) and a
year of hourly weather data, BuEM:

1. Constructs a 5R1C thermal network (air node, surface node, mass node).
2. Distributes solar and internal gains across these nodes per ISO 13790 §C.2.
3. Formulates the annual energy balance as an LP that minimises
   :math:`\sum |Q_{\text{HC}}|` subject to dead-band comfort constraints.
4. Solves with CVXPY (CLARABEL or OSQP) to obtain hourly heating/cooling
   profiles.

An experimental MILP path is also available, which separates heating and
cooling into independent variables using binary indicators.

Key Features
------------

- **Physics-based**: EN ISO 13790 5R1C with annual-periodic boundary conditions
- **LP / MILP solver**: CVXPY with CBC fallback; dead-band comfort modelling
- **Solar gains**: pvlib isotropic-sky model for plane-of-array irradiance
- **Stochastic occupancy**: Richardson-model electricity profiles
- **REST API**: Flask + Gunicorn; GeoJSON in, GeoJSON out
- **Docker-ready**: single ``docker compose up`` for production use

Target Users
------------

**Developers / Integrators** who connect BuEM to other simulation tools
(district heating models, urban energy platforms) via its REST API in
Docker containers.

**Researchers** who need quick, standards-based thermal-load estimates for
large building stocks.