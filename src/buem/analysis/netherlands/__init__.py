"""
Netherlands-specific analysis/validation tooling.

Separate from ``buem.buildings.datasources``/``mapping``'s own NL-specific
modules (``cityjson_extractor``, ``rivm_energy_labels``,
``nl_archetype_mapper``, ``nl_building_classifier``) -- those build the
*data* (geometry, archetype links); this package *analyzes* buem's own
simulated output using that data, matching ``buem.analysis``'s existing
charter ("reusable tooling for comparing buem's simulated heating/
cooling/electricity demand... across weather providers/buildings") rather
than being grouped with the data-ingestion layer. A home for NL-specific
analysis work as it accumulates (2026-08-18: ``cbs_reference``,
``gas_conversion``, ``validation``), not a one-off script location.
"""
