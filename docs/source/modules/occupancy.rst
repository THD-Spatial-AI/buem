occupancy — Occupancy & Electricity Profiles
=============================================

:Source: ``buem/occupancy/``

Purpose
-------

Generate stochastic annual occupancy schedules and realistic hourly
electricity-consumption profiles for residential buildings.

OccupancyProfile
----------------

:File: ``occupancy_profile.py``

Produces an 8760-row DataFrame with per-hour:

- ``n_home`` — number of persons at home
- ``n_active`` — number awake and active
- ``activity`` — categorical state (``not_home`` / ``at_home_inactive`` / ``at_home_active``)

Behaviour:

- Weekday vs weekend probability tables (e.g. 10 % home at 3 AM weekday,
  20 % weekend)
- Per-person binomial draw:
  :math:`\text{persons\_home} \sim \text{Binomial}(n,\, p_{\text{home}}(\text{hour}, \text{day type}))`
- Reproducible via a NumPy RNG seed

ElectricityConsumptionProfile
-----------------------------

:File: ``electricity_consumption.py``

Implements the **Richardson et al. (2010)** behavioural appliance model.

For each hour:

1. Evaluate occupancy-dependent activation probabilities per appliance
   (cooking, TV, laundry, cleaning, ironing, fridge, background loads).
2. Modulate by a weekday/weekend × hour-of-day behaviour table.
3. Stochastically switch appliances on/off.
4. Weight by rated power (e.g. cooking 3–4 kW, fridge 0.1 kW).
5. Sum → total electricity load (kWh/h).

Typical output for a four-person dwelling: 0.5–1.5 kW.

Integration
-----------

When the API payload does not supply an ``elecLoad`` series,
``cfg_attribute.py`` auto-generates one via the pipeline:

``OccupancyProfile`` → ``ElectricityConsumptionProfile`` → ``elecLoad`` series
