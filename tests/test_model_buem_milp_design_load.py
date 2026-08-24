"""
Regression test for the 2026-08-16 fix to
``ModelBUEM._addConstraints_sequential()``'s MILP big-M design-load
computation (see CHANGELOG.md / .claude/residential/resolved.md).

Previously, any exception from ``calcDesignHeatLoad()`` while building
MILP big-M bounds was silently replaced with a made-up ``design=1000.0``
-- no log, no error, found during an audit prompted by wanting to rule
out other silent-fallback patterns after the Bug 1/Bug 2 solar-gain
fixes. Now it must be logged and re-raised as a clear ``ValueError``.

Uses the real default cfg (``cfg_attribute.cfg``, the same fixture
``test_building_types.py`` relies on) rather than hand-building a
complete valid cfg from scratch -- constructing one that reaches this
deep into ``sim_model()`` (past ``validate_cfg``/``_initEnvelop``/
``_init5R1C``/``_addVariables``) needs the same real inputs any working
simulation needs.
"""
from __future__ import annotations

import copy
import os
from pathlib import Path
from unittest.mock import patch

import pytest

project_root = Path(__file__).resolve().parent.parent
os.environ.setdefault("BUEM_WEATHER_DIR", str(project_root / "src" / "buem" / "data" / "weather"))

from buem.config.cfg_attribute import cfg as DEFAULT_CFG
from buem.thermal.model_buem import ModelBUEM


def test_calc_design_heat_load_failure_is_logged_and_reraised_not_swallowed():
    cfg = copy.deepcopy(DEFAULT_CFG)
    model = ModelBUEM(cfg)

    with patch.object(
        model, "calcDesignHeatLoad", side_effect=ValueError("synthetic failure for regression test"),
    ), pytest.raises(ValueError, match="Could not compute design heat load"):
        model.sim_model(use_milp=False)
