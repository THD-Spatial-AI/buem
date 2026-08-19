#!/usr/bin/env python3
"""Tests for the CLI: the schema validator, and `buem validate`'s
weather-source check."""

import pytest

from buem.cli import _check_weather_source
from buem.config.building_registry import DEFAULT_WEATHER_PROVIDER

_WEATHER_ENV = ("WEATHER_API_URL", "WEATHER_API_KEY", "BUEM_WEATHER_DATA_DIR", "WEATHER_DATA_DIR")


@pytest.fixture
def clean_weather_env(monkeypatch):
    """Start from no weather configuration at all, so each test sets only
    what it means to exercise (the real machine has .env values loaded)."""
    for var in _WEATHER_ENV:
        monkeypatch.delenv(var, raising=False)


def test_check_weather_source_fails_when_nothing_configured(clean_weather_env):
    """Weather has no fallback, so an unconfigured environment cannot run a
    single building -- validate must not report PASS for it."""
    ok, lines = _check_weather_source()
    assert ok is False
    assert any("neither WEATHER_API_URL nor WEATHER_DATA_DIR" in line for line in lines)


def test_check_weather_source_accepts_http_api(clean_weather_env, monkeypatch):
    monkeypatch.setenv("WEATHER_API_URL", "https://weather.example/api")
    ok, lines = _check_weather_source()
    assert ok is True
    assert "NO WEATHER_API_KEY set" in lines[0]

    monkeypatch.setenv("WEATHER_API_KEY", "secret")
    ok, lines = _check_weather_source()
    assert ok is True
    assert "with API key" in lines[0]


def test_check_weather_source_fails_on_missing_directory(clean_weather_env, monkeypatch, tmp_path):
    monkeypatch.setenv("WEATHER_DATA_DIR", str(tmp_path / "not-there"))
    ok, lines = _check_weather_source()
    assert ok is False
    assert "MISSING" in lines[0]


def test_check_weather_source_warns_but_passes_on_unrecognised_layout(clean_weather_env, monkeypatch, tmp_path):
    """On-disk archive layouts vary between providers and weather versions,
    so an unrecognised one is worth printing but is not proof of breakage —
    it must not turn `buem validate` red."""
    (tmp_path / "some-other-provider").mkdir()
    monkeypatch.setenv("WEATHER_DATA_DIR", str(tmp_path))
    ok, lines = _check_weather_source()
    assert ok is True
    assert "[WARN]" in lines[0]
    assert DEFAULT_WEATHER_PROVIDER in lines[0]


def test_check_weather_source_accepts_provider_dir_spelled_either_way(clean_weather_env, monkeypatch, tmp_path):
    """Archives are written as e.g. 'merra2' while the CLI name is
    'merra-2'; both must be recognised."""
    for name in (DEFAULT_WEATHER_PROVIDER, DEFAULT_WEATHER_PROVIDER.replace("-", "")):
        root = tmp_path / name.replace("-", "_dir_")
        root.mkdir()
        (root / name).mkdir()
        monkeypatch.setenv("WEATHER_DATA_DIR", str(root))
        ok, _ = _check_weather_source()
        assert ok is True, f"provider directory named {name!r} not recognised"


def test_check_weather_source_prefers_buem_specific_var(clean_weather_env, monkeypatch, tmp_path):
    (tmp_path / DEFAULT_WEATHER_PROVIDER).mkdir()
    monkeypatch.setenv("BUEM_WEATHER_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("WEATHER_DATA_DIR", str(tmp_path / "ignored"))
    ok, lines = _check_weather_source()
    assert ok is True
    assert str(tmp_path) in lines[0]


def test_schema_cli():
    """Test the CLI functionality."""
    from buem.integration.scripts.schema_validator import BuemSchemaValidator

    validator = BuemSchemaValidator()
    assert validator is not None, "BuemSchemaValidator should instantiate"


def test_schema_cli_help():
    """--help should exit with code 0."""
    from buem.integration.scripts.schema_validator import BuemSchemaValidator

    # Verify the validator can be created and has expected methods
    validator = BuemSchemaValidator()
    assert hasattr(validator, "validate_file")
    assert hasattr(validator, "print_validation_result")


if __name__ == "__main__":
    test_schema_cli()
    test_schema_cli_help()
    print("All CLI tests passed")
