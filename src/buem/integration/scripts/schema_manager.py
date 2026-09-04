"""Loads the pinned BUEM-EnerPlanET contract schema.

The contract is buem-gateway's (`json_schema/README.md`, `contract.txt`),
pinned here as a verbatim copy -- see json_schema/README.md for the
re-sync procedure. There is exactly one live contract, not a version tree
to scan, so this module has no directory-discovery logic: the "version"
below is the pinned contract_version from contract.txt, kept only so
callers written against the old versions/vN/ layout (schema_cli.py,
workflow_example.py) don't need their own rewrite.
"""
import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_SCHEMA_FILENAMES = {
    "request_schema": "request_schema.json",
    "response_schema": "response_schema.json",
    "request_example": "example_request.json",
    "response_example": "example_response.json",
}


def _parse_contract_txt(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    fields: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or "=" not in line:
            continue
        key, _, value = line.partition("=")
        fields[key.strip()] = value.strip()
    return fields


class SchemaVersionManager:
    """Serves the single pinned contract schema.

    Kept as a class (rather than module-level functions) only for
    compatibility with existing callers (schema_cli.py, workflow_example.py,
    schema_validator.py) built against the old multi-version manager.
    `version` arguments are accepted and, if given, must match the pinned
    contract_version -- there is nothing else to select.
    """

    def __init__(self, base_dir: Path | None = None):
        """
        Parameters
        ----------
        base_dir : Path, optional
            Directory containing the pinned schema/example files and
            contract.txt. Defaults to json_schema/ (this module's sibling).
        """
        self.base_dir = Path(base_dir) if base_dir is not None else Path(__file__).parent.parent / "json_schema"
        contract = _parse_contract_txt(self.base_dir / "contract.txt")
        self.pinned_version = contract.get("contract_version", "unknown")
        self.pinned_source_repo = contract.get("repo", "unknown")
        self.pinned_source_tag = contract.get("tag", "unknown")

    def get_available_versions(self, force_refresh: bool = False) -> list[str]:  # noqa: ARG002 -- kept for API compat
        """Return the single pinned version (there is only ever one)."""
        return [self.pinned_version]

    def get_latest_version(self) -> str:
        """Return the pinned contract version."""
        return self.pinned_version

    def _check_version(self, version: str | None) -> None:
        if version is not None and version != self.pinned_version:
            raise FileNotFoundError(
                f"Schema version {version!r} not available; this repo carries a single "
                f"pinned contract, {self.pinned_version!r} "
                f"(from {self.pinned_source_repo}@{self.pinned_source_tag}). "
                "Re-sync json_schema/ (see its README.md) to change it."
            )

    def get_schema_paths(self, version: str | None = None) -> dict[str, Path]:
        """Return paths to the pinned schema/example files.

        Raises
        ------
        FileNotFoundError
            If `version` is given and doesn't match the pinned contract
            version.
        """
        self._check_version(version)
        return {name: self.base_dir / filename for name, filename in _SCHEMA_FILENAMES.items()}

    def load_schema(self, schema_type: str, version: str | None = None) -> dict[str, Any]:
        """Load `request_schema.json` or `response_schema.json`."""
        if schema_type not in ("request", "response"):
            raise ValueError(f"Invalid schema_type: {schema_type}. Must be 'request' or 'response'")
        paths = self.get_schema_paths(version)
        schema_path = paths[f"{schema_type}_schema"]
        if not schema_path.exists():
            raise FileNotFoundError(f"Schema file not found: {schema_path}")
        try:
            with schema_path.open(encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in schema file {schema_path}: {e}") from e

    def load_example(self, example_type: str, version: str | None = None) -> dict[str, Any]:
        """Load `example_request.json` or `example_response.json`."""
        if example_type not in ("request", "response"):
            raise ValueError(f"Invalid example_type: {example_type}. Must be 'request' or 'response'")
        paths = self.get_schema_paths(version)
        example_path = paths[f"{example_type}_example"]
        if not example_path.exists():
            raise FileNotFoundError(f"Example file not found: {example_path}")
        try:
            with example_path.open(encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in example file {example_path}: {e}") from e

    def version_exists(self, version: str) -> bool:
        """Check whether `version` is the pinned contract version."""
        return version == self.pinned_version

    def get_version_info(self, version: str | None = None) -> dict[str, Any]:
        """Return metadata about the pinned contract for the CLI/debug tools."""
        self._check_version(version)
        paths = self.get_schema_paths()
        info: dict[str, Any] = {
            "version": self.pinned_version,
            "is_latest": True,
            "source": f"{self.pinned_source_repo}@{self.pinned_source_tag}",
            "directory": str(self.base_dir),
            "files": {},
        }
        for name, path in paths.items():
            if path.exists():
                stat = path.stat()
                info["files"][name] = {
                    "path": str(path), "exists": True,
                    "size_bytes": stat.st_size, "modified": stat.st_mtime,
                }
            else:
                info["files"][name] = {"path": str(path), "exists": False}
        return info


# Convenience instance for the integration module
schema_manager = SchemaVersionManager()
