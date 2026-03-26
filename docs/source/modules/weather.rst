weather — Weather Data Processing
==================================

:Source: ``buem/weather/from_csv.py``

Purpose
-------

Load meteorological data from CSV and reconstruct physically-consistent DNI
(Direct Normal Irradiance) for use in solar-gain calculations.

CsvWeatherData
--------------

The main class reads COSMO-REA6 (or similar NWP) CSV files containing hourly:

- **T** — air temperature [°C]
- **GHI** — global horizontal irradiance [W/m²]
- **DNI** — direct normal irradiance [W/m²]
- **DHI** — diffuse horizontal irradiance [W/m²]

DNI Reconstruction
~~~~~~~~~~~~~~~~~~

NWP models store DNI as :math:`(GHI - DHI) / \cos(\theta_z)`.  Near the
horizon :math:`\cos(\theta_z) \to 0`, producing unphysical spikes
(> 4000 W/m² observed).

BuEM applies **pvlib's DISC decomposition** (Iqbal 1983) to re-derive DNI
empirically from GHI.  The result is capped at extraterrestrial irradiance
(1316–1413 W/m² seasonal).  DHI is then back-computed as
:math:`DHI = GHI - DNI \cos(\theta_z)`.

Caching
~~~~~~~

Processed data is stored as a ``.feather`` file next to the source CSV,
avoiding the 2–3 s pvlib computation on worker-process re-imports.

Default Weather File
--------------------

BuEM ships with ``COSMO_Year__ix_390_650.csv`` — a representative weather
year extracted from the COSMO-REA6 reanalysis for Loenen, Netherlands.
