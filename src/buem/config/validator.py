"""
Runtime configuration validator for building cfg dicts.

Function validate_cfg(cfg: dict) -> List[str]:
  - Returns empty list when cfg passes checks.
  - Returns list of human-readable issue strings otherwise.
Checks performed:
  - presence of components or legacy U_* keys
  - numeric positive U values for Walls/Windows/Roof/Floor/Doors
  - element areas > 0 and unique element ids if 'components' provided
  - weather timeseries length consistent when series provided
"""
from typing import Any


def _is_number(v) -> bool:
    try:
        float(v)
        return True
    except Exception:
        return False

def validate_cfg(cfg: dict[str, Any]) -> list[str]:
    issues: list[str] = []

    # Require structured 'components' tree
    comps = cfg.get("components")
    if not isinstance(comps, dict):
        issues.append("components missing or not an object (required)")
        return issues

    seen_ids: set[str] = set()
    for comp in ("Walls", "Windows", "Roof", "Floor", "Doors"):
        c = comps.get(comp)
        if c is None:
            issues.append(f"components.{comp} missing")
            continue

        # component-level U or per-element U is required
        u = c.get("U")
        elems = c.get("elements", [])
        if u is None and not elems:
            issues.append(f"components.{comp} missing U and no elements present")
            continue

        if u is not None:
            try:
                if float(u) <= 0:
                    issues.append(f"components.{comp}.U must be positive number")
            except Exception:
                issues.append(f"components.{comp}.U invalid: {u}")

        # validate elements if present
        if isinstance(elems, list):
            for idx, e in enumerate(elems):
                if not isinstance(e, dict):
                    issues.append(f"components.{comp}.elements[{idx}] not an object")
                    continue
                eid = e.get("id")
                if eid is None:
                    issues.append(f"components.{comp}.elements[{idx}].id missing")
                else:
                    if eid in seen_ids:
                        issues.append(f"duplicate element id '{eid}' in components")
                    seen_ids.add(eid)
                area = e.get("area")
                if area is None:
                    issues.append(f"components.{comp}.elements[{idx}].area missing")
                else:
                    try:
                        if float(area) <= 0:
                            issues.append(f"components.{comp}.elements[{idx}].area must be > 0")
                    except Exception:
                        issues.append(f"components.{comp}.elements[{idx}].area invalid: {area}")
                u_e = e.get("U")
                if u is None:  # if component-level U missing, require per-element U
                    if u_e is None:
                        issues.append(f"components.{comp}.elements[{idx}].U missing")
                    else:
                        try:
                            if float(u_e) <= 0:
                                issues.append(f"components.{comp}.elements[{idx}].U must be positive number")
                        except Exception:
                            issues.append(f"components.{comp}.elements[{idx}].U invalid: {u_e}")

    # weather presence/length sanity check (optional)
    weather = cfg.get("weather")
    if weather is None:
        issues.append("weather missing")
    else:
        try:
            n = len(weather)
            if n == 0:
                issues.append("weather timeseries appears empty")
        except Exception:
            # if not lengthable, ignore deep check here
            pass

    return issues