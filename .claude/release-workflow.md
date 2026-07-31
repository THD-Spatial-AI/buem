# Release workflow — "push to github"

Runbook for when the user explicitly says something like "push to github" /
"release this" / "push origin main". Not run automatically, not implied by
finishing an unrelated task — see `CLAUDE.md`'s "Guardrails" section.

**Never as part of this workflow**: edit anything under
`src/buem/integration/json_schema/` or tighten
`geojson_validator.py`'s `BuildingAttributesSchema` validation — that's the
EnerPlanET API contract, a separate agreed-change process (see `CLAUDE.md`
"Guardrails" and `src/buem/integration/json_schema/VERSIONING.md`). If the
diff being released touches those files, stop and confirm with the user
before continuing — don't silently include them in a routine push.

## Steps

1. **Survey the diff since the last release.**
   - `git status`, `git diff`, `git log <last-tag>..HEAD --oneline` (last
     tag: `git describe --tags --abbrev=0`).
   - Decide whether `CHANGELOG.md`'s `[Unreleased]` section already covers
     everything, or needs updating — this repo follows [Keep a
     Changelog](https://keepachangelog.com/en/1.1.0/) +
     [SemVer](https://semver.org/); see existing entries for the
     Added/Changed/Fixed/Deprecated style.
   - Decide whether `CLAUDE.md` or `.claude/*.md` need updating for
     anything durable the diff introduced (new gotcha, new convention, a
     resolved open-item) — same judgment as any other session, not a
     mechanical step.

2. **Determine the version bump.** This repo uses `setuptools_scm`
   (`pyproject.toml`: `version_file = "src/buem/_version.py"`) — the git
   tag *is* the version, no version string to hand-edit elsewhere. Existing
   tags mostly follow `vMAJOR.MINOR.PATCH` (see `git tag --list`; most
   recent: `v1.2.1`). Pick the bump per CHANGELOG's SemVer convention
   (breaking → MAJOR, backward-compatible addition → MINOR, fix-only →
   PATCH) based on the actual diff — don't default to PATCH without
   checking.

3. **Move `[Unreleased]` → the new version heading** in `CHANGELOG.md`
   (`## [X.Y.Z] - YYYY-MM-DD`, today's date), leaving a fresh empty
   `[Unreleased]` above it. Commit doc changes (CHANGELOG + any CLAUDE.md/
   `.claude/` updates from step 1) as their own commit before tagging.

4. **Run the local CI mirror** (exact steps from
   `.github/workflows/ci.yml`, in the `buem_env` conda env — this repo has
   no plain `python`/`conda` on PATH by default in this environment; use
   the full interpreter path, e.g.
   `C:\Users\sahoo002\.conda\envs\buem_env\python.exe`, or resolve
   `conda.bat` under the anaconda install first):
   ```
   ruff check src/ tests/
   mypy src
   pytest -q --cov=buem --cov-report=xml
   buem validate
   ```
   Fix or clearly report any failure before proceeding — don't tag/push on
   a red local CI mirror. Note the 4 pre-existing broken-collection test
   files (`test_energy.py`, `test_geojson_integration.py`,
   `test_scaling.py`, `test_worker_debug.py` — see `CLAUDE.md` "Open
   follow-ups") as a known baseline, not a new regression, unless that's
   since been fixed.

5. **Show the user a summary before pushing**: the version chosen and why,
   the CHANGELOG diff, and the local CI mirror result. This is the last
   checkpoint before an action that touches the shared remote — confirm
   before continuing unless the user has said to run this workflow fully
   autonomously.

6. **Tag and push.**
   ```
   git tag vX.Y.Z -m "vX.Y.Z"
   git push origin main
   git push origin vX.Y.Z
   ```

7. **Monitor CI on GitHub** (`gh run list --branch main --limit 1`, then
   `gh run watch <run-id>`, or `gh run watch` on the latest run) until it
   completes. Report the result (pass/fail, and which step if it failed) —
   don't just fire-and-forget the push.
