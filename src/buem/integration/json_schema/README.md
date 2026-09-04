# BUEM-EnerPlanET contract

The BUEM-EnerPlanET request/response contract is owned by
`enerplanet/buem-gateway` (`schemas/v5/`, `docs/versioning.md`). The files
in this folder are a pinned copy of **API contract v5** (`contract.txt`
names the exact tag) — do not edit them here. Re-sync from buem-gateway to
update:

```bash
git -C ../buem-gateway show v6.0.0:schemas/v5/request_schema.json  > request_schema.json
git -C ../buem-gateway show v6.0.0:schemas/v5/response_schema.json > response_schema.json
```

then update `contract.txt` and re-add each pinned file's leading
`"$comment"` field naming the new tag.

`schema_manager.py` loads `request_schema.json` / `response_schema.json`
from this folder directly (no version subdirectories — there is exactly
one live contract). `geojson_validator.py` validates incoming requests
against `request_schema.json` with `jsonschema`; it does not re-define the
contract's structure.

CI fails if this folder drifts from `contract.txt`'s pinned tag (see
`.github/workflows/ci.yml`'s "Contract drift" step).

To propose a contract change, open a PR against buem-gateway's
`schemas/v6-draft/`, not against these files.
