"""
Shared-wall (party-wall) detection.

A wall surface is *shared* when its ``surface_feature_id`` appears under
multiple ``building_feature_id`` values in the child-surface table.
Shared walls transfer heat to an adjacent heated space, so their effective
U-value should be set to 0 and b_transmission to 0.

Usage
-----
>>> detector = SharedWallDetector(source.surfaces)
>>> detector.is_shared(surface_feature_id=12345)
True
"""

from __future__ import annotations

import logging

import pandas as pd

logger = logging.getLogger(__name__)

# Only wall surfaces can be shared (objectclass_id 709).
_OBJECTCLASS_WALL = 709


class SharedWallDetector:
    """Pre-compute the set of shared wall ``surface_feature_id`` values.

    The computation runs once at construction time and is O(n) in the number
    of wall surfaces.  Lookups are O(1) frozenset membership tests.

    Parameters
    ----------
    surfaces_df : pd.DataFrame
        The full child-surface table (all buildings).  Must contain columns
        ``surface_feature_id``, ``building_feature_id``, and ``objectclass_id``.
    """

    def __init__(self, surfaces_df: pd.DataFrame) -> None:
        self._shared_sfids: frozenset[int] = self._detect(surfaces_df)
        logger.info(
            "SharedWallDetector: %d shared surface_feature_ids detected",
            len(self._shared_sfids),
        )

    # ── public API ───────────────────────────────────────────────────────────

    def is_shared(self, surface_feature_id: int) -> bool:
        """Return ``True`` if the surface is shared between 2+ buildings."""
        return surface_feature_id in self._shared_sfids

    @property
    def shared_count(self) -> int:
        """Number of distinct shared surface_feature_ids."""
        return len(self._shared_sfids)

    # ── internals ────────────────────────────────────────────────────────────

    @staticmethod
    def _detect(surfaces_df: pd.DataFrame) -> frozenset[int]:
        """Identify wall surface_feature_ids that belong to >1 building."""
        walls = surfaces_df[surfaces_df["objectclass_id"] == _OBJECTCLASS_WALL]
        counts = (
            walls.groupby("surface_feature_id")["building_feature_id"]
            .nunique()
        )
        shared = counts[counts > 1].index
        return frozenset(int(s) for s in shared)
