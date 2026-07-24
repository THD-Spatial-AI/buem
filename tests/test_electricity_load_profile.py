"""Tests for load_electricity_load_profile (electricity_load_profile.py):
directory allowlisting and sanitized error messages for a caller-controlled
file path (buem.inputs.electricity_load_profile.path).
"""
import gzip
import json

import pytest

from buem.integration.scripts.electricity_load_profile import load_electricity_load_profile


@pytest.fixture
def profile_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("BUEM_ELEC_PROFILE_DIR", str(tmp_path))
    return tmp_path


def test_loads_valid_csv(profile_dir):
    (profile_dir / "profile.csv").write_text("demand\n1.0\n2.5\n3.0\n")
    assert load_electricity_load_profile(str(profile_dir / "profile.csv")) == [1.0, 2.5, 3.0]


def test_loads_valid_json(profile_dir):
    (profile_dir / "profile.json").write_text(json.dumps([1.0, 2.0, 3.0]))
    assert load_electricity_load_profile(str(profile_dir / "profile.json")) == [1.0, 2.0, 3.0]


def test_loads_valid_json_gz(profile_dir):
    path = profile_dir / "profile.json.gz"
    with gzip.open(path, "wt", encoding="utf-8") as fh:
        json.dump([4.0, 5.0], fh)
    assert load_electricity_load_profile(str(path)) == [4.0, 5.0]


def test_rejects_path_outside_allowed_dir(profile_dir, tmp_path_factory):
    outside_dir = tmp_path_factory.mktemp("outside")
    secret = outside_dir / "secret.csv"
    secret.write_text("s3cr3t-value\n")

    with pytest.raises(ValueError) as exc_info:
        load_electricity_load_profile(str(secret))

    message = str(exc_info.value)
    assert message == "electricity_load_profile: path outside allowed directory"
    assert str(secret) not in message
    assert "s3cr3t-value" not in message


def test_rejects_traversal_path(profile_dir):
    with pytest.raises(ValueError, match="path outside allowed directory"):
        load_electricity_load_profile("../etc/passwd")


def test_rejects_nonexistent_file_without_confirming_absence(profile_dir):
    with pytest.raises(ValueError, match="file not found"):
        load_electricity_load_profile(str(profile_dir / "does_not_exist.csv"))


def test_nonnumeric_csv_error_does_not_leak_value(profile_dir):
    (profile_dir / "bad.csv").write_text("demand\nnot-a-number\n2.0\n")

    with pytest.raises(ValueError) as exc_info:
        load_electricity_load_profile(str(profile_dir / "bad.csv"))

    message = str(exc_info.value)
    assert "not-a-number" not in message
    assert "could not parse" in message


def test_nonnumeric_json_error_does_not_leak_value(profile_dir):
    (profile_dir / "bad.json").write_text(json.dumps(["oops", 2.0]))

    with pytest.raises(ValueError) as exc_info:
        load_electricity_load_profile(str(profile_dir / "bad.json"))

    message = str(exc_info.value)
    assert "oops" not in message
    assert "could not parse" in message
