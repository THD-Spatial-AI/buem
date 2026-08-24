"""
CBS StatLine OData client -- real Dutch regional energy-consumption
statistics, queried live (no bundled/cached copy, no new HTTP-library
dependency: stdlib ``urllib.request`` + ``json``).

Table 81528NED, "Energieverbruik particuliere woningen; woningtype en
regio's" -- real average annual gas (m3) and electricity (kWh)
consumption per dwelling, by housing type and region (national/
provincial/municipal). Freely queryable via OData, **no CBS-microdata
gating** (see ``nl_building_classifier``'s own docstring for that
distinct, access-gated dataset) -- this is CBS's open StatLine API.

Schema (confirmed 2026-08-18 via the same live queries this module
wraps, not assumed): dimensions ``RegioS`` (region code, e.g. ``"GM0200"``
for Apeldoorn), ``Perioden`` (year, e.g. ``"2024JJ00"``),
``Woningkenmerken`` (housing type, see ``HOUSING_TYPE_CODES`` below);
measures ``GemiddeldAardgasverbruik_1`` (m3/yr) and
``GemiddeldeElektriciteitslevering_2`` (kWh/yr).
"""

from __future__ import annotations

import json
import logging
import urllib.parse
import urllib.request
from dataclasses import dataclass

logger = logging.getLogger(__name__)

_BASE_URL = "https://opendata.cbs.nl/ODataApi/odata/81528NED/TypedDataSet"

# Woningkenmerken codes -> the CBS woningtype categories
# nl_building_classifier's own docstring already documents (Dutch label,
# buem building_type/neighbour_status mapping). T001100 is CBS's own
# "all dwellings" aggregate, not a real structural type.
HOUSING_TYPE_CODES: dict[str, str] = {
    "all": "T001100",
    "detached": "ZW10320",         # vrijstaande woning -> SFH, B_Alone
    "semi_detached": "ZW10300",    # 2-onder-1-kapwoning -> SFH, B_N1 (pair)
    "mid_terrace": "ZW25805",      # tussenwoning -> TH, B_N2
    "corner": "ZW25806",           # hoekwoning -> TH, B_N1
    "apartment": "ZW25810",        # appartement -> MFH/AB
}

# buem's own building_type/neighbour_status -> the CBS housing-type key
# that matches it, for looking up a comparison figure given a buem-side
# classification (nl_building_classifier's own mapping, reversed).
BUEM_TYPE_TO_CBS_KEY: dict[tuple[str, str], str] = {
    ("SFH", "B_Alone"): "detached",
    ("SFH", "B_N1"): "semi_detached",
    ("TH", "B_N1"): "corner",
    ("TH", "B_N2"): "mid_terrace",
    ("MFH", "B_Alone"): "apartment",
    ("MFH", "B_N1"): "apartment",
    ("MFH", "B_N2"): "apartment",
    ("AB", "B_Alone"): "apartment",
    ("AB", "B_N1"): "apartment",
    ("AB", "B_N2"): "apartment",
}


@dataclass(frozen=True)
class CbsConsumptionFigure:
    """One (region, year, housing type) row from CBS table 81528NED."""

    region_code: str
    period: str
    housing_type_key: str
    gas_m3_per_year: float | None
    electricity_kwh_per_year: float | None


def _fetch_json(url: str, timeout: float = 30.0) -> dict:
    with urllib.request.urlopen(url, timeout=timeout) as resp:  # noqa: S310 -- fixed, hardcoded CBS host
        return json.load(resp)


def fetch_consumption(
    region_code: str, period: str, housing_type_keys: list[str] | None = None,
) -> dict[str, CbsConsumptionFigure]:
    """Query real gas/electricity consumption for one region/year.

    Parameters
    ----------
    region_code : str
        CBS ``RegioS`` code, e.g. ``"GM0200"`` for Apeldoorn (Loenen's
        own municipality). Municipality codes are the real BAG/CBS
        ``GM<4 digits>`` scheme -- the same ``"0200"`` prefix already
        seen throughout every Loenen ``bag_pand_id`` this session.
    period : str
        CBS ``Perioden`` code, e.g. ``"2024JJ00"`` (whole-year 2024).
    housing_type_keys : list of str, optional
        Which of ``HOUSING_TYPE_CODES``' keys to fetch (default: all of
        them).

    Returns
    -------
    dict
        ``{housing_type_key: CbsConsumptionFigure}`` for every key that
        had a matching row (a key can be absent if CBS has no data for
        that combination -- not filled with a null placeholder).
    """
    keys = housing_type_keys if housing_type_keys is not None else list(HOUSING_TYPE_CODES)
    codes = [HOUSING_TYPE_CODES[k] for k in keys]
    code_to_key = {HOUSING_TYPE_CODES[k]: k for k in keys}

    woning_filter = " or ".join(f"Woningkenmerken eq '{c}'" for c in codes)
    filter_expr = f"RegioS eq '{region_code}' and Perioden eq '{period}' and ({woning_filter})"
    query = urllib.parse.urlencode({
        "$filter": filter_expr,
        "$select": "Woningkenmerken,GemiddeldAardgasverbruik_1,GemiddeldeElektriciteitslevering_2",
    }, safe="'()=")
    url = f"{_BASE_URL}?{query}"

    logger.info("Querying CBS 81528NED: region=%s period=%s housing_types=%s", region_code, period, keys)
    data = _fetch_json(url)

    result: dict[str, CbsConsumptionFigure] = {}
    for row in data.get("value", []):
        wk = row.get("Woningkenmerken", "").strip()
        key = code_to_key.get(wk)
        if key is None:
            continue
        result[key] = CbsConsumptionFigure(
            region_code=region_code,
            period=period,
            housing_type_key=key,
            gas_m3_per_year=row.get("GemiddeldAardgasverbruik_1"),
            electricity_kwh_per_year=row.get("GemiddeldeElektriciteitslevering_2"),
        )

    missing = set(keys) - set(result)
    if missing:
        logger.warning("CBS 81528NED: no data for %s at region=%s period=%s", sorted(missing), region_code, period)
    return result


__all__ = ["BUEM_TYPE_TO_CBS_KEY", "HOUSING_TYPE_CODES", "CbsConsumptionFigure", "fetch_consumption"]
