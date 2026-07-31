weather — Location-Specific Weather Input
==========================================

:Source: ``src/buem/config/weather_cache.py``; real implementation in
   `UU-BUEM/weather <https://github.com/UU-BUEM/weather>`_ (external, optional)

.. note::
   Weather fetching/processing was split out of buem into its own
   repository — COSMO-REA6/ERA5-Land/MERRA-2 download, decompression,
   grid handling, and CLI tooling all live there now, with their own
   docs. This page covers only buem's thin integration surface; see
   `UU-BUEM/weather's docs <https://github.com/UU-BUEM/weather/tree/main/docs>`_
   for real internals (pipeline, grid/projection handling, containerised
   deployment, CLI reference) rather than duplicating them here.

Purpose
-------

Fetch a location-specific hourly weather DataFrame (``T``, ``GHI``,
``DHI``, ``DNI``) for a building's ``(latitude, longitude, year,
provider)``, with an on-disk cache so repeated buildings at the same site
(or across a parallel batch run) avoid repeat fetch/reconstruction cost.

weather_cache.py
-----------------

- ``weather_available() -> bool`` — whether the optional ``weather``
  package (``pip install buem[weather]``) is importable.
- ``get_or_fetch_weather(latitude, longitude, year, provider) -> pd.DataFrame`` —
  returns a cached DataFrame if one exists at
  ``BUEM_WEATHER_DIR/location_cache/<provider>_<lat>_<lon>_<year>.feather``,
  otherwise calls ``weather.get_point_weather(...)`` and caches the
  result. Raises ``ImportError`` if the package isn't installed,
  ``FileNotFoundError``/``KeyError``/``OSError``/``ValueError`` if the
  package is installed but has no data for that specific location/year/
  provider.
- ``distinct_locations(building_attrs)`` — used to pre-warm the cache for
  every distinct ``(lat, lon, year, provider)`` in a batch before forking
  parallel workers.

Integration
-----------

:File: ``src/buem/integration/scripts/attribute_builder.py``
   (``AttributeBuilder.generate_weather_profile``)

- If ``use_provided_weather`` is set, or the ``weather`` package isn't
  installed at all, keeps the bundled default weather CSV
  (``src/buem/config/cfg_attribute.py``'s module-level fallback) — a
  documented, deliberate "optional extra not installed" leniency.
- Otherwise fetches real per-location weather via
  ``get_or_fetch_weather``. A fetch failure for the *specific requested*
  location (package installed, but no data for this location/year/
  provider) now **raises** by default rather than silently substituting
  the bundled reference-location weather — pass
  ``AttributeBuilder(..., allow_weather_fallback=True)`` to opt back into
  the lenient behavior for offline/dev use. An ``ImportError`` from one of
  ``weather``'s own optional extras (e.g. ``xarray``/``netcdf4`` for
  point-query) being missing is still treated as the same "extra not
  installed" leniency, since it's the same underlying situation one layer
  deeper.

Solar gains on building surfaces (plane-of-array irradiance per element,
via pvlib's isotropic sky model) are computed by ``ModelBUEM`` itself —
see ``modules/thermal.rst`` — from the horizontal-plane ``T``/``GHI``/
``DHI``/``DNI`` this module supplies; the ``weather`` package does not do
that transposition.
