"""Centralised environment bootstrap for BUEM.

Loads .env from the project root (searched upward from this file, or from
``BUEM_HOME`` if set) and applies sensible path defaults relative to the
installed package location.  Safe to call multiple times.
"""
from __future__ import annotations

import os
from pathlib import Path

_loaded = False


def _find_dotenv() -> Path | None:
    """Walk upward from this file to find the nearest .env."""
    for parent in Path(__file__).resolve().parents:
        candidate = parent / ".env"
        if candidate.is_file():
            return candidate
    return None


def load_env() -> None:
    """Load .env and set default env vars for all BUEM paths.

    Called automatically on first import of ``buem`` and explicitly by the
    CLI entry-point.  Subsequent calls are no-ops.
    """
    global _loaded
    if _loaded:
        return
    _loaded = True

    # 1. Load .env (does not override variables already set in the environment)
    try:
        from dotenv import load_dotenv

        dotenv_home = os.environ.get("BUEM_HOME")
        if dotenv_home:
            found = Path(dotenv_home) / ".env"
            load_dotenv(found, override=False)
        else:
            found = _find_dotenv()
            if found:
                load_dotenv(found, override=False)

        # Resolve any relative paths in BUEM_ env vars to absolute, using the
        # .env file location (project root) as the base.  Without this, a value
        # like "./src/buem/data/weather" is ambiguous — it depends on whatever
        # the cwd happens to be at import time.
        if found and found.is_file():
            _root = found.parent
            for _var in (
                "BUEM_WEATHER_DIR", "BUEM_RESULTS_DIR", "BUEM_LOG_DIR",
                "BUEM_CBC_EXE", "BUEM_LOG_FILE", "BUEM_ELEC_PROFILE_DIR",
            ):
                _val = os.environ.get(_var)
                if _val and not Path(_val).is_absolute():
                    os.environ[_var] = str((_root / _val).resolve())
    except ImportError:
        pass  # python-dotenv is optional; OS env vars still work

    # 2. Apply defaults relative to the package directory so that an
    #    installed package (or editable install) works out of the box.
    _pkg = Path(__file__).parent
    os.environ.setdefault("BUEM_WEATHER_DIR", str(_pkg / "data" / "weather"))
    os.environ.setdefault("BUEM_RESULTS_DIR", str(_pkg / "results"))
    os.environ.setdefault("BUEM_LOG_DIR",     str(_pkg / "logs"))
    os.environ.setdefault("BUEM_ELEC_PROFILE_DIR", str(_pkg / "data" / "electricity_profiles"))
