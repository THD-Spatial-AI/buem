"""
Reusable tooling for comparing buem's simulated heating/cooling/electricity
demand -- and the raw weather inputs feeding it -- across weather providers,
for one or many buildings picked directly from the bundled TABULA Excel/
PostgreSQL source.

Not part of the live API request-handling path (``buem.integration``) or
the offline GeoJSON-generation pipeline (``buem.buildings.pipeline``) --
this is an analysis/reporting layer sitting on top of both, built to
replace one-off scratchpad scripts with real, importable, tested code.

See ``python -m buem.analysis.batch --help`` for the many-building entry
point, or import ``provider_comparison``/``report`` directly for a single
building.
"""
