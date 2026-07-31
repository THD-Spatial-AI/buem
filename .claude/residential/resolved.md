# Resolved issues / decisions — household / dwelling types

Fixed bugs and settled/BY-DESIGN decisions land here once closed out.
Nothing resolved yet under this new log (started 2026-07-31) — see
`open.md` for active items.

## BY-DESIGN

- [envelope] TABULA `building_type` (`SFH`/`MFH`/`TH`/`AB`) and
  `neighbour_status` (`B_Alone`/`B_N1`/`B_N2`) are carried as
  `BuildingIdentity` classification metadata (`src/buem/buildings/
  building.py`); the one place dwelling form currently feeds the physics
  directly is `F_red_htr` (intermittent-heating reduction, ISO 13790
  §13.2.2), which TABULA sets to 0.95 for AB/MFH vs. 0.90 for SFH/TH.
  This is intentional — see `open.md` for where more differentiation is
  still missing.
