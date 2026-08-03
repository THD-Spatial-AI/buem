"""Location-keyed on-disk cache wrapping the (compulsory) weather package.

Before weather became per-location, buem loaded exactly one bundled CSV at
module-import time and cached its (expensive, ~2-3s pvlib DISC) processed
form in a single global feather file (see cfg_attribute.py). A dynamic,
per-building weather fetch needs a cache keyed by (provider, lat, lon,
year) instead of one global key, so repeated buildings at the same site
(or across a parallel batch) still avoid repeat fetch/reconstruction cost.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import pandas as pd
from weather import get_point_weather  # type: ignore[import]

logger = logging.getLogger(__name__)


def _cache_dir() -> Path:
    base = os.environ.get(
        "BUEM_WEATHER_DIR",
        os.path.join(os.path.dirname(__file__), "..", "data", "weather"),
    )
    d = Path(base).resolve() / "location_cache"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _cache_path(provider: str, latitude: float, longitude: float, year: int) -> Path:
    key = f"{provider}_{round(latitude, 3)}_{round(longitude, 3)}_{year}"
    return _cache_dir() / f"{key}.feather"


def get_or_fetch_weather(
    latitude: float, longitude: float, year: int, provider: str
) -> pd.DataFrame:
    """Return a cached (or freshly fetched) weather DataFrame.

    Raises
    ------
    FileNotFoundError
        If `weather` has no processed archive for (provider, year) at the
        requested location (set ``BUEM_WEATHER_DATA_DIR`` to point at one).
    """
    path = _cache_path(provider, latitude, longitude, year)
    if path.exists():
        df = pd.read_feather(path)
        df.set_index(df.columns[0], inplace=True)
        df.index = pd.to_datetime(df.index)
        return df

    data_dir = os.environ.get("BUEM_WEATHER_DATA_DIR")
    df = get_point_weather(
        latitude, longitude, year, provider=provider, data_dir=data_dir
    )
    try:
        df.reset_index().to_feather(path)
    except (OSError, ValueError) as exc:
        # Non-critical: caching failure should not block model execution.
        logger.warning("Could not write weather cache %s: %s", path, exc)
    return df


def distinct_locations(
    building_attrs: Iterable[dict[str, Any]],
) -> list[tuple[float, float, int, str]]:
    """Distinct (latitude, longitude, year, provider) across a batch.

    Used to pre-warm the cache for every location in a multi-building run
    before forking parallel workers (see parallelization/parallel_run.py),
    instead of assuming a single global weather dataset.
    """
    from buem.config.cfg_attribute import ATTRIBUTE_SPECS

    default_lat = ATTRIBUTE_SPECS["latitude"].default
    default_lon = ATTRIBUTE_SPECS["longitude"].default
    default_year = ATTRIBUTE_SPECS["year"].default
    default_provider = ATTRIBUTE_SPECS["weather_provider"].default

    seen: set[tuple[float, float, int, str]] = set()
    for attrs in building_attrs:
        seen.add((
            round(float(attrs.get("latitude", default_lat)), 3),
            round(float(attrs.get("longitude", default_lon)), 3),
            int(attrs.get("year", default_year)),
            str(attrs.get("weather_provider", default_provider)),
        ))
    return sorted(seen)
