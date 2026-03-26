technology — Building Technology Models
=======================================

:Source: ``buem/technology/``

Purpose
-------

Model specific HVAC or heating technologies that interact with the thermal
load profiles produced by the 5R1C model.

Existing Technologies
---------------------

ExistingFireplace (``existing/fireplace.py``)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Generates an hourly binary (on / off) profile for a fireplace or stove.

Inputs: ``OccupancyProfile``, ``CsvWeatherData``.

Logic:

1. Normalise occupancy activity within a rolling week:
   :math:`f_{act} = n_{active} / \max_{7\text{d}}(n_{active})`.
2. Compute a temperature factor (1 at :math:`T_{on}`, 0 at :math:`T_{off}`,
   linear between).
3. Probability = :math:`f_{act} \times f_{temp}`.
4. Stochastic Bernoulli draw per hour (seeded RNG).

Default parameters: :math:`T_{on} = 5\,°C` (forced ON),
:math:`T_{off} = 21\,°C` (forced OFF).

New Technologies
----------------

HeatPump (``new/heatpump.py``)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Currently an **empty stub** — placeholder for a future heat-pump model.
