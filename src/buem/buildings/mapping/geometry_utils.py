"""
Minimal WKB point geometry helpers.

Extracts a real (latitude, longitude) from a building's
``building_centroid_geom`` column -- a hex-encoded EWKB (extended
well-known binary) geometry blob, as produced by PostGIS/pgAdmin CSV
exports (confirmed against the real Netherlands/Loenen export this was
built for).

Deliberately hand-rolled rather than using ``shapely``: only a single
2D/3D POINT geometry needs decoding here (a building's centroid), which
is a fixed, small byte layout -- not worth a new dependency for. Full
polygon geometry (surface area/tilt/azimuth) is a much larger, genuinely
non-trivial 3D computation and is *not* attempted here; see
``CsvBuildingSource``'s own docstring for why that's expected to arrive
pre-computed instead.
"""

from __future__ import annotations

import struct

import pandas as pd
import pyproj

# EWKB geometry-type flag bits (OGC extended WKB, as used by PostGIS)
_EWKB_HAS_Z = 0x80000000
_EWKB_HAS_SRID = 0x20000000
_EWKB_TYPE_MASK = 0xFFFF

_WKB_TYPE_POINT = 1

# Amersfoort / RD New (the Dutch national triangulation grid) -> WGS84.
# Confirmed against a real Loenen building_centroid_geom this module was
# built for (SRID 28992, decoded by hand before this module existed).
_RD_NEW_SRID = 28992
_WGS84_SRID = 4326


def _transformer_for(srid: int) -> pyproj.Transformer:
    return pyproj.Transformer.from_crs(f"EPSG:{srid}", f"EPSG:{_WGS84_SRID}", always_xy=True)


# One transformer per SRID, built lazily and reused -- pyproj.Transformer
# construction is the expensive part, not the actual point transforms.
_TRANSFORMER_CACHE: dict[int, pyproj.Transformer] = {}


def wkb_point_to_lat_lon(hex_wkb: str) -> tuple[float, float]:
    """Decode a hex-encoded EWKB POINT (2D or 3D) to (latitude, longitude).

    Parameters
    ----------
    hex_wkb : str
        The raw hex string from a ``*_geom`` column, e.g.
        ``"0101000020407100..."``.

    Returns
    -------
    (float, float)
        ``(latitude, longitude)`` in WGS84 decimal degrees.

    Raises
    ------
    ValueError
        If the geometry isn't a POINT, or its SRID isn't one this module
        knows how to reproject (currently only EPSG:28992, RD New --
        extend ``_TRANSFORMER_CACHE`` usage if another SRID shows up).
    """
    raw = bytes.fromhex(hex_wkb)
    byte_order = raw[0]
    endian = "<" if byte_order == 1 else ">"

    type_and_flags = struct.unpack(f"{endian}I", raw[1:5])[0]
    geom_type = type_and_flags & _EWKB_TYPE_MASK
    has_srid = bool(type_and_flags & _EWKB_HAS_SRID)
    has_z = bool(type_and_flags & _EWKB_HAS_Z)

    if geom_type != _WKB_TYPE_POINT:
        raise ValueError(f"wkb_point_to_lat_lon: expected a POINT geometry, got type {geom_type}")

    offset = 5
    srid = _RD_NEW_SRID
    if has_srid:
        srid = struct.unpack(f"{endian}I", raw[offset:offset + 4])[0]
        offset += 4

    x, y = struct.unpack(f"{endian}dd", raw[offset:offset + 16])
    # A Z coordinate (building height/elevation) may follow but isn't
    # needed for a lat/lon weather lookup -- read, not used.
    if has_z:
        offset += 16
        struct.unpack(f"{endian}d", raw[offset:offset + 8])

    if srid not in _TRANSFORMER_CACHE:
        _TRANSFORMER_CACHE[srid] = _transformer_for(srid)
    lon, lat = _TRANSFORMER_CACHE[srid].transform(x, y)
    return float(lat), float(lon)


def building_lat_lon(bldg_row: pd.Series) -> tuple[float, float] | None:
    """Extract (latitude, longitude) from a building row's
    ``building_centroid_geom`` column, or ``None`` if absent/invalid
    (e.g. the German Excel source, which has no geometry for most rows
    -- see ``.claude/residential/resolved.md``'s 2026-08-16 entry on why
    this matters)."""
    geom = bldg_row.get("building_centroid_geom")
    if geom is None or (isinstance(geom, float) and pd.isna(geom)):
        return None
    try:
        return wkb_point_to_lat_lon(str(geom))
    except (ValueError, struct.error) as exc:
        import logging
        logging.getLogger(__name__).warning(
            "building_lat_lon: failed to decode geometry (%s) -- treating as absent.", exc,
        )
        return None


__all__ = ["building_lat_lon", "wkb_point_to_lat_lon"]
