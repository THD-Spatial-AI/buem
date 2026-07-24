"""Load a caller-supplied electricity load profile from a file path.

Referenced by path (buem.inputs.electricity_load_profile.path) rather than
inlined in the request JSON, per the v4 contract — an 8760-value array inline
would make every request unwieldy. The file must already be accessible inside
this container (shared Docker volume). Supported formats: CSV (single column,
optional header), JSON array, or gzipped JSON array (.gz).
"""
import csv
import gzip
import json
import os


def load_electricity_load_profile(path: str) -> list:
    """Read an electricity load profile file and return a list of floats.

    Parameters
    ----------
    path : str
        Path to the profile file, readable from inside this container.

    Returns
    -------
    list of float

    Raises
    ------
    FileNotFoundError
        If path does not exist.
    ValueError
        If the file extension isn't recognised, or its content can't be
        parsed into a flat list of numbers.
    """
    if not os.path.isfile(path):
        raise FileNotFoundError(f"electricity_load_profile path not found: {path}")

    lower = path.lower()
    if lower.endswith(".csv"):
        return _load_csv(path)
    if lower.endswith(".json.gz") or lower.endswith(".gz"):
        return _load_json(gzip.open(path, "rt", encoding="utf-8"))
    if lower.endswith(".json"):
        return _load_json(open(path, "r", encoding="utf-8"))
    raise ValueError(
        f"electricity_load_profile: unrecognised file extension for {path!r} "
        "— expected .csv, .json, or .json.gz"
    )


def _load_csv(path: str) -> list:
    with open(path, "r", encoding="utf-8", newline="") as fh:
        reader = csv.reader(fh)
        rows = [row[0] for row in reader if row]
    if rows and not _is_number(rows[0]):
        rows = rows[1:]  # header row (e.g. "demand")
    try:
        return [float(v) for v in rows]
    except ValueError as exc:
        raise ValueError(f"electricity_load_profile: non-numeric value in {path}: {exc}") from exc


def _load_json(fh) -> list:
    with fh:
        data = json.load(fh)
    if not isinstance(data, list):
        raise ValueError("electricity_load_profile: JSON content must be a flat array of numbers")
    try:
        return [float(v) for v in data]
    except (TypeError, ValueError) as exc:
        raise ValueError(f"electricity_load_profile: non-numeric value in JSON array: {exc}") from exc


def _is_number(s: str) -> bool:
    try:
        float(s)
        return True
    except ValueError:
        return False
