"""
Tests for ``buem.config.validator.validate_cfg()``.

Focused on the U-value check specifically: regression coverage for the
2026-08-14 fix (see CHANGELOG.md, .claude/residential/resolved.md) where
``U <= 0`` was rejected wholesale, breaking the documented party-wall
convention (``U == 0``, ``b_transmission == 0`` -- see
``buem.buildings.mapping.wall_classifier``'s ``SharedWallDetector``
docstring). The fix narrowed the check to ``U < 0`` only.
"""
from __future__ import annotations

from buem.config.validator import validate_cfg


def _minimal_cfg(walls: dict) -> dict:
    """A cfg dict with just enough shape for validate_cfg's own checks --
    every other required component present and valid, only ``Walls``
    varies per test. Element ids are unique *across all components* --
    validate_cfg checks id uniqueness globally, not per-component, so
    other components use a distinct prefix to avoid colliding with
    whatever ids a test's own ``walls`` dict uses (``w0``, ``w1``, ...)."""
    return {
        "components": {
            "Walls": walls,
            "Windows": {"U": 1.2, "elements": [{"id": "win1", "area": 2.0, "U": 1.2}]},
            "Roof": {"U": 0.3, "elements": [{"id": "roof1", "area": 50.0, "U": 0.3}]},
            "Floor": {"U": 0.4, "elements": [{"id": "floor1", "area": 50.0, "U": 0.4}]},
            "Doors": {"U": 1.5, "elements": [{"id": "door1", "area": 1.5, "U": 1.5}]},
        },
        "weather": list(range(10)),
    }


def test_component_level_u_zero_is_valid():
    """U=0 at the component level (e.g. every wall in this component is a
    party wall) must not be flagged -- this is the exact regression."""
    cfg = _minimal_cfg({"U": 0.0, "elements": [{"id": "w1", "area": 10.0, "b_transmission": 0.0}]})
    assert validate_cfg(cfg) == []


def test_component_level_u_negative_is_invalid():
    cfg = _minimal_cfg({"U": -0.5, "elements": [{"id": "w1", "area": 10.0}]})
    issues = validate_cfg(cfg)
    assert any("Walls.U must not be negative" in issue for issue in issues)


def test_per_element_u_zero_is_valid_when_component_level_u_missing():
    """No component-level U at all, but every element has its own U --
    including a genuine party wall at U=0 -- must still validate clean."""
    cfg = _minimal_cfg({
        "elements": [
            {"id": "w1", "area": 10.0, "U": 0.3, "b_transmission": 1.0},
            {"id": "w2", "area": 8.0, "U": 0.0, "b_transmission": 0.0},
        ],
    })
    assert validate_cfg(cfg) == []


def test_per_element_u_negative_is_invalid_when_component_level_u_missing():
    cfg = _minimal_cfg({
        "elements": [
            {"id": "w1", "area": 10.0, "U": 0.3},
            {"id": "w2", "area": 8.0, "U": -1.0},
        ],
    })
    issues = validate_cfg(cfg)
    assert any("elements[1].U must not be negative" in issue for issue in issues)


def test_a_fully_shared_building_all_zero_u_walls_is_valid():
    """The realistic case that originally broke: a component-level U of
    0.0 because every wall in the component is shared (mirrors the real
    building this bug was found on, id 30542 -- 15/15 walls shared)."""
    cfg = _minimal_cfg({
        "U": 0.0,
        "elements": [
            {"id": f"w{i}", "area": 10.0, "b_transmission": 0.0} for i in range(15)
        ],
    })
    assert validate_cfg(cfg) == []
