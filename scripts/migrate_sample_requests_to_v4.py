"""One-time migration of the bundled example requests to the v4 format.

``src/buem/integration/`` shipped two example requests written in the
superseded flat ``building_attributes`` shape. That format is no longer
accepted (see ``BuemSchema.require_building_envelope``), so the examples
are rewritten here into the current ``building``/``envelope`` structure
and consolidated into a single ``sample_request.geojson`` -- there is
only one supported request version, so a version-suffixed filename no
longer conveys anything.

Usage::

    python scripts/migrate_sample_requests_to_v4.py
"""

from __future__ import annotations

import json
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_INTEGRATION_DIR = _REPO_ROOT / "src" / "buem" / "integration"
_LEGACY = ("sample_request_v2.geojson", "sample_request_template.geojson")
_TARGET = _INTEGRATION_DIR / "sample_request.geojson"

# Element types whose entries live under building.envelope.elements, and
# the component keys they came from in the flat format.
_COMPONENT_TO_ELEMENT_TYPE = {
    "Walls": "wall",
    "Roof": "roof",
    "Floor": "floor",
    "Windows": "window",
    "Doors": "door",
}


def _to_v4(legacy: dict) -> dict:
    feature = legacy["features"][0]
    props = feature["properties"]
    attrs = props["buem"]["building_attributes"]
    components = attrs.get("components", {})

    elements: list[dict] = []
    for comp_key, comp in components.items():
        element_type = _COMPONENT_TO_ELEMENT_TYPE.get(comp_key)
        if element_type is None:  # Ventilation carries no geometry
            continue
        for elem in comp.get("elements", []):
            entry = {
                "id": elem["id"],
                "type": element_type,
                "area": {"value": float(elem["area"]), "unit": "m2"},
            }
            if elem.get("azimuth") is not None:
                entry["azimuth"] = {"value": float(elem["azimuth"]), "unit": "deg"}
            if elem.get("tilt") is not None:
                entry["tilt"] = {"value": float(elem["tilt"]), "unit": "deg"}
            if elem.get("surface") is not None:
                entry["parent_id"] = elem["surface"]
            # U lives on the element itself; fall back to the component's
            # shared value when an element does not override it.
            u_value = elem.get("U", comp.get("U"))
            if u_value is not None:
                entry["U"] = {"value": float(u_value), "unit": "W/(m2K)"}
            if elem.get("g_gl", comp.get("g_gl")) is not None:
                entry["g_gl"] = {
                    "value": float(elem.get("g_gl", comp.get("g_gl"))), "unit": "-",
                }
            elements.append(entry)

    thermal: dict = {}
    vent = components.get("Ventilation", {})
    if vent.get("n_air_use") is not None:
        thermal["n_air_use"] = {"value": float(vent["n_air_use"]), "unit": "1/h"}

    building: dict = {
        "name": feature.get("id", "sample_building"),
        "A_ref": {"value": float(attrs["A_ref"]), "unit": "m2"},
        "h_room": {"value": float(attrs["h_room"]), "unit": "m"},
        "envelope": {"elements": elements},
    }
    if thermal:
        building["thermal"] = thermal

    buem: dict = {"building": building}
    if props["buem"].get("use_milp") is not None:
        buem["use_milp"] = props["buem"]["use_milp"]

    new_props = {k: v for k, v in props.items() if k != "buem"}
    new_props["buem"] = buem

    return {
        "type": "FeatureCollection",
        "timeStamp": legacy.get("timeStamp", "2018-01-01T00:00:00Z"),
        "features": [{
            "type": "Feature",
            "id": feature.get("id", "building_001"),
            # Coordinates carry latitude/longitude in the current format.
            "geometry": {
                "type": "Point",
                "coordinates": [float(attrs["longitude"]), float(attrs["latitude"])],
            },
            "properties": new_props,
        }],
    }


def main() -> None:
    source = _INTEGRATION_DIR / _LEGACY[0]
    if not source.exists():
        raise FileNotFoundError(f"{source} not found -- already migrated?")

    converted = _to_v4(json.loads(source.read_text(encoding="utf-8")))
    _TARGET.write_text(json.dumps(converted, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {_TARGET}")

    for name in _LEGACY:
        legacy_path = _INTEGRATION_DIR / name
        if legacy_path.exists():
            legacy_path.unlink()
            print(f"Removed superseded {legacy_path.name}")


if __name__ == "__main__":
    main()
