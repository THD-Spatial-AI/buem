"""
v3 GeoJSON file writer.

Converts canonical ``Building`` objects into v3-schema-compliant GeoJSON files.
Supports both single-building files (one FeatureCollection per file) and batch
writing of multiple buildings to a target directory.

Output directory structure
--------------------------
::

    data/buildings/germany/mainkopen/
        building_44424.geojson
        building_44425.geojson
        ...
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from buem.buildings.building import Building

logger = logging.getLogger(__name__)


class GeoJsonBuildingWriter:
    """Write Building objects to v3-schema GeoJSON files.

    Parameters
    ----------
    output_dir : str or Path
        Target directory for GeoJSON files.
    indent : int
        JSON indentation level (default ``2``).
    """

    def __init__(self, output_dir: str | Path, indent: int = 2):
        self.output_dir = Path(output_dir)
        self.indent = indent

    def write_building(self, building: Building) -> Path:
        """Write a single building to a GeoJSON file.

        The file is named ``building_{building_feature_id}.geojson``.

        Parameters
        ----------
        building : Building
            The building to serialise.

        Returns
        -------
        Path
            Path to the written file.
        """
        feature = building.to_v3_geojson_feature()
        collection = _wrap_feature_collection([feature])

        self.output_dir.mkdir(parents=True, exist_ok=True)
        bid = building.identity.building_feature_id
        filename = f"building_{bid}.json"
        filepath = self.output_dir / filename

        filepath.write_text(
            json.dumps(collection, indent=self.indent, ensure_ascii=False),
            encoding="utf-8",
        )
        logger.debug("Wrote %s", filepath)
        return filepath

    def write_batch(
        self,
        buildings: List[Building],
        mode: str = "individual",
    ) -> List[Path]:
        """Write multiple buildings to GeoJSON files.

        Parameters
        ----------
        buildings : list of Building
            Buildings to write.
        mode : str
            ``"individual"`` — one file per building (default).
            ``"single"`` — all buildings in one FeatureCollection file.

        Returns
        -------
        list of Path
            Paths to the written files.
        """
        self.output_dir.mkdir(parents=True, exist_ok=True)
        paths: List[Path] = []

        if mode == "single":
            features = [b.to_v3_geojson_feature() for b in buildings]
            collection = _wrap_feature_collection(features)
            filepath = self.output_dir / "all_buildings.json"
            filepath.write_text(
                json.dumps(collection, indent=self.indent, ensure_ascii=False),
                encoding="utf-8",
            )
            paths.append(filepath)
            logger.info("Wrote %d buildings to %s", len(buildings), filepath)
        else:
            for building in buildings:
                path = self.write_building(building)
                paths.append(path)
            logger.info(
                "Wrote %d individual building files to %s",
                len(buildings), self.output_dir,
            )

        return paths


def _wrap_feature_collection(
    features: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Wrap a list of Feature dicts into a GeoJSON FeatureCollection."""
    from datetime import datetime, timezone

    return {
        "type": "FeatureCollection",
        "timeStamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "features": features,
    }
