"""
Tests for ``buem.analysis.netherlands.cbs_reference`` -- the HTTP call
itself is mocked (no real network access in a unit test); the query
construction and response parsing are exercised for real.
"""
from __future__ import annotations

from buem.analysis.netherlands import cbs_reference
from buem.analysis.netherlands.cbs_reference import (
    BUEM_TYPE_TO_CBS_KEY,
    HOUSING_TYPE_CODES,
    fetch_consumption,
)


def _fake_cbs_response(rows):
    return {"value": rows}


def test_fetch_consumption_parses_real_shaped_response(monkeypatch):
    """A response shaped like the real 2024 Apeldoorn query this module
    was built against."""
    captured_url = {}

    def fake_fetch_json(url, timeout=30.0):
        captured_url["url"] = url
        return _fake_cbs_response([
            {"Woningkenmerken": "ZW10320", "GemiddeldAardgasverbruik_1": 1380.0,
             "GemiddeldeElektriciteitslevering_2": 4010.0},
            {"Woningkenmerken": "ZW25805", "GemiddeldAardgasverbruik_1": 770.0,
             "GemiddeldeElektriciteitslevering_2": 2460.0},
        ])

    monkeypatch.setattr(cbs_reference, "_fetch_json", fake_fetch_json)
    result = fetch_consumption("GM0200", "2024JJ00", ["detached", "mid_terrace"])

    assert set(result) == {"detached", "mid_terrace"}
    assert result["detached"].gas_m3_per_year == 1380.0
    assert result["detached"].electricity_kwh_per_year == 4010.0
    assert result["mid_terrace"].gas_m3_per_year == 770.0
    # region/period filters actually made it into the query URL
    assert "GM0200" in captured_url["url"]
    assert "2024JJ00" in captured_url["url"]


def test_fetch_consumption_missing_key_logged_not_filled(monkeypatch, caplog):
    """A requested housing type CBS has no row for is simply absent from
    the result, not filled with a null placeholder."""
    monkeypatch.setattr(cbs_reference, "_fetch_json", lambda url, timeout=30.0: _fake_cbs_response([]))
    with caplog.at_level("WARNING"):
        result = fetch_consumption("GM0200", "2024JJ00", ["detached"])
    assert result == {}
    assert "detached" in caplog.text


def test_fetch_consumption_defaults_to_all_housing_types(monkeypatch):
    requested = {}

    def fake_fetch_json(url, timeout=30.0):
        requested["url"] = url
        return _fake_cbs_response([])

    monkeypatch.setattr(cbs_reference, "_fetch_json", fake_fetch_json)
    fetch_consumption("GM0200", "2024JJ00")
    for code in HOUSING_TYPE_CODES.values():
        assert code in requested["url"]


def test_buem_type_to_cbs_key_covers_every_real_classifier_output():
    """Every (building_type, neighbour_status) pair
    nl_building_classifier.classify_building_type() can actually produce
    must have a CBS mapping -- otherwise a real building would silently
    get no comparison figure. Enumerated by actually calling the real
    classifier across its input space, not a hand-listed cross product
    (e.g. (SFH, B_N2) and (TH, B_Alone) are never produced, and
    shouldn't be expected to have a mapping either)."""
    from buem.buildings.mapping.nl_building_classifier import classify_building_type

    reachable = set()
    for degree in (0, 1, 2, 3):
        for component_size in (1, 2, 3, 5):
            for units in (None, 1, 3, 10):
                reachable.add(classify_building_type(degree, component_size, units))

    for pair in reachable:
        assert pair in BUEM_TYPE_TO_CBS_KEY, f"no CBS mapping for real classifier output {pair!r}"
