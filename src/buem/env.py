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
            load_dotenv(Path(dotenv_home) / ".env", override=False)
        else:
            found = _find_dotenv()
            if found:
                load_dotenv(found, override=False)
    except ImportError:
        pass  # python-dotenv is optional; OS env vars still work

    # 2. Apply defaults relative to the package directory so that an
    #    installed package (or editable install) works out of the box.
    _pkg = Path(__file__).parent
    os.environ.setdefault("BUEM_WEATHER_DIR", str(_pkg / "data"))
    os.environ.setdefault("BUEM_RESULTS_DIR", str(_pkg / "results"))
    os.environ.setdefault("BUEM_LOG_DIR",     str(_pkg / "logs"))
