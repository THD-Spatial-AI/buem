"""
Tests for ``buem.buildings.datasources.rivm_energy_labels`` -- built
against a tiny synthetic SQLite file with the same schema as the real
RIVM GeoPackage (never against the real 3.2GB file in a unit test).
"""
from __future__ import annotations

import sqlite3

import pytest

from buem.buildings.datasources.rivm_energy_labels import load_labels_for_buildings, strip_bag_prefix


def test_strip_bag_prefix():
    assert strip_bag_prefix("NL.IMBAG.Pand.0200100000938969") == "0200100000938969"
    assert strip_bag_prefix("already-bare") == "already-bare"


@pytest.fixture
def synthetic_gpkg(tmp_path):
    """A minimal SQLite file with the real table name/columns -- no
    actual GeoPackage metadata tables needed since the loader only ever
    queries the one feature table directly."""
    path = tmp_path / "energielabels_test.gpkg"
    conn = sqlite3.connect(str(path))
    conn.execute(
        "CREATE TABLE energielabels_2025 ("
        "fid INTEGER PRIMARY KEY, identificatie TEXT, aant_verblijfsobj REAL, "
        "dominant_label TEXT, aant_labels TEXT, hoogste_label TEXT, laagste_label TEXT)"
    )
    conn.executemany(
        "INSERT INTO energielabels_2025 "
        "(identificatie, aant_verblijfsobj, dominant_label, hoogste_label, laagste_label) "
        "VALUES (?, ?, ?, ?, ?)",
        [
            ("0200100000000001", 1.0, "C", "C", "C"),
            ("0200100000000002", 1.0, None, None, None),  # matched, but no real label
            ("0200100000000003", 8.0, "B", "B", "B"),
        ],
    )
    conn.commit()
    conn.close()
    return path


def test_load_labels_for_buildings_matches_and_labels(synthetic_gpkg):
    ids = [
        "NL.IMBAG.Pand.0200100000000001",
        "NL.IMBAG.Pand.0200100000000002",
        "NL.IMBAG.Pand.0200100000000003",
        "NL.IMBAG.Pand.9999999999999999",  # not in the file at all
    ]
    result = load_labels_for_buildings(synthetic_gpkg, ids)

    assert len(result) == 3  # the unmatched id is simply absent, not a NaN row
    by_id = result.set_index("bag_pand_id")
    assert by_id.loc["NL.IMBAG.Pand.0200100000000001", "dominant_label"] == "C"
    assert by_id.loc["NL.IMBAG.Pand.0200100000000003", "aant_verblijfsobj"] == 8.0
    assert by_id.loc["NL.IMBAG.Pand.0200100000000002", "dominant_label"] is None or \
        __import__("pandas").isna(by_id.loc["NL.IMBAG.Pand.0200100000000002", "dominant_label"])


def test_load_labels_for_buildings_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_labels_for_buildings(tmp_path / "does_not_exist.gpkg", ["NL.IMBAG.Pand.1"])


def test_load_labels_for_buildings_empty_id_list(synthetic_gpkg):
    result = load_labels_for_buildings(synthetic_gpkg, [])
    assert len(result) == 0
