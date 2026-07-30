"""
File-based result cache for BUEM thermal model outputs.

Hashes the fully-resolved cfg dict (post CfgBuilding.to_cfg_dict()) into a
deterministic SHA-256 key, then stores/retrieves the run_model() result dict
as a pickle file.

Thread- and process-safe: uses atomic rename for writes so readers never see
partial files.  No external dependencies beyond the standard library.
"""

import hashlib
import json
import logging
import os
import pickle
import tempfile
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# Default cache directory lives inside the package results folder: src/buem/results/.model_cache
_DEFAULT_CACHE_DIR = Path(__file__).resolve().parent.parent.parent / "results" / ".model_cache"
CACHE_DIR = Path(os.environ.get("BUEM_RESULT_CACHE_DIR", str(_DEFAULT_CACHE_DIR)))


def _make_hashable(obj: Any) -> Any:
    """Recursively convert cfg-dict values into a JSON-serialisable/hashable form."""
    if isinstance(obj, pd.DataFrame):
        # Round floats to 6 decimals to avoid floating-point jitter
        return ("__df__", tuple(obj.columns), tuple(
            tuple(round(v, 6) if isinstance(v, float) else v for v in row)
            for row in obj.itertuples(index=True, name=None)
        ))
    if isinstance(obj, pd.Series):
        return ("__series__", tuple(
            (str(idx), round(v, 6) if isinstance(v, float) else v)
            for idx, v in obj.items()
        ))
    if isinstance(obj, np.ndarray):
        return ("__ndarray__", tuple(round(float(x), 6) for x in obj.ravel()))
    if isinstance(obj, dict):
        return tuple(sorted((k, _make_hashable(v)) for k, v in obj.items()))
    if isinstance(obj, (list, tuple)):
        return tuple(_make_hashable(x) for x in obj)
    if isinstance(obj, float):
        return round(obj, 6)
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return round(float(obj), 6)
    return obj


def compute_cfg_hash(cfg: dict[str, Any]) -> str:
    """Return a hex SHA-256 digest that uniquely identifies the model inputs."""
    canonical = _make_hashable(cfg)
    raw = json.dumps(canonical, sort_keys=True, default=str).encode()
    return hashlib.sha256(raw).hexdigest()


def get_cached_result(cache_key: str) -> dict[str, Any] | None:
    """Return the cached result dict, or None on miss."""
    path = CACHE_DIR / f"{cache_key}.pkl"
    if not path.exists():
        return None
    try:
        with open(path, "rb") as f:
            return pickle.load(f)
    except Exception as exc:
        logger.debug(f"Cache read error for {cache_key}: {exc}")
        return None


def store_result(cache_key: str, result: dict[str, Any]) -> None:
    """Persist *result* under *cache_key* (atomic write via rename)."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    tmp_fd, tmp_path = tempfile.mkstemp(dir=str(CACHE_DIR), suffix=".tmp")
    try:
        with os.fdopen(tmp_fd, "wb") as f:
            pickle.dump(result, f, protocol=pickle.HIGHEST_PROTOCOL)
        dest = CACHE_DIR / f"{cache_key}.pkl"
        os.replace(tmp_path, str(dest))
    except Exception as exc:
        logger.debug(f"Cache write error for {cache_key}: {exc}")
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


def clear_cache() -> int:
    """Remove all cached results.  Returns count of files deleted."""
    if not CACHE_DIR.exists():
        return 0
    count = 0
    for p in CACHE_DIR.glob("*.pkl"):
        try:
            p.unlink()
            count += 1
        except OSError:
            pass
    return count
