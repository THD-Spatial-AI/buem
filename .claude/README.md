# .claude/ — known issues & decisions log

Git-tracked log so recurring items don't need re-explaining each session.
Pattern ported from `UU-BUEM/occupancy` (itself ported from
`UU-BUEM/weather`), split by domain to mirror the household/dwelling-type
vs. services-building distinction in buem's own building-typing and
defaults work — not a mirror of buem's module layout.

## For Claude Code

- **Check the relevant `open.md` before starting** work on building-type
  handling, defaults, or standards choices — top-level for core 5R1C
  model/config/integration/cross-repo items, `residential/` for
  household/dwelling-type differentiation (SFH/MFH/TH/AB, party walls,
  shading, occupancy linkage), `services/` for non-residential building
  types. Respect RESOLVED/BY-DESIGN entries so you don't re-raise settled
  points.
- When you hit or fix something, UPDATE the matching file in the same
  change. Cross-cutting items (touch both domains, core model, or
  occupancy/weather integration) go top-level; domain-specific items go
  in the matching subfolder.
- One-liners; newest at top. Keep markdownlint-clean.

## Files

- `open.md` / `resolved.md` — cross-cutting (5R1C core model, standards
  choice, config/schema, occupancy/weather integration, cross-repo).
- `residential/open.md` / `residential/resolved.md` — household/dwelling-
  type-specific (SFH/MFH/TH/AB differentiation, party walls, shading,
  archetype defaults, occupancy linkage).
- `services/open.md` / `services/resolved.md` — non-residential
  building-type-specific (building-use taxonomy, floor-area-normalized
  gains, multi-use buildings, setback/setpoint profiles).
- `release-workflow.md` — the "push to github" runbook. User-triggered
  only — see `CLAUDE.md` "Guardrails".

## See also

- `/CLAUDE.md` — architecture, layout, conventions, cross-repo context.
- `occupancy/.claude/` and `weather/.claude/` — sibling repos' own logs,
  same convention.
