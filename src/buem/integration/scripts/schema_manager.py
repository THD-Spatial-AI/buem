"""
Schema Version Management for BUEM Integration.

This module handles versioned JSON schemas provided by external API collaborators
and provides automatic version detection, schema loading, and path management.

Key Features:
    - Automatic discovery of latest schema versions
    - Version-aware schema and example file loading  
    - Robust path resolution for different deployment scenarios
    - Caching for improved performance
    - Fallback mechanisms for missing files

Schema Organization:
    The schemas are organized in a versioned directory structure:
    integration/json_schema/versions/
    ├── v1/
    │   ├── request_schema.json
    │   ├── response_schema.json  
    │   ├── request_example.json
    │   └── response_example.json
    ├── v2/
    │   └── (same structure)
    └── v3/
        └── (same structure)

Classes:
    SchemaVersionManager: Main manager for schema versions and file access

Usage:
    # Create manager (auto-detects schema location)
    manager = SchemaVersionManager()
    
    # Get latest version
    latest = manager.get_latest_version()  # e.g., 'v2'
    
    # Load a schema
    schema = manager.load_schema("request", version="v2")
    
    # Get file paths  
    paths = manager.get_schema_paths("v2")
"""
import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class SchemaVersionManager:
    """
    Manages versioned JSON schemas for BUEM API validation.
    
    This class handles the discovery, loading, and management of versioned
    JSON schemas provided by external API collaborators. It automatically
    detects the latest available version and provides access to schemas,
    examples, and metadata.
    
    Key Methods:
        - get_latest_version(): Get the most recent schema version
        - get_available_versions(): List all available versions  
        - load_schema(): Load a specific schema file
        - get_schema_paths(): Get file paths for a version
        - get_version_info(): Get detailed information about a version
    
    Attributes:
        base_dir (Path): Base directory containing versioned schemas
        version_format (str): Regex pattern for valid version names (e.g., 'v1', 'v2')
    
    Examples:
        # Basic usage
        manager = SchemaVersionManager()
        latest = manager.get_latest_version()
        
        # Load specific schema
        request_schema = manager.load_schema("request", version="v2")
        
        # Get all file paths for a version
        paths = manager.get_schema_paths("v2")
        request_schema_path = paths["request_schema"]
    """
    
    def __init__(self, base_dir: Path | None = None):
        """
        Initialize schema manager.
        
        Args:
            base_dir: Base directory containing versioned schemas.
                     Defaults to integration/json_schema/versions/
        """
        if base_dir is None:
            try:
                # Schema manager is in scripts/, but json_schema/ is in integration/
                # So we need to go up one level: scripts/../json_schema/versions
                self.base_dir = Path(__file__).parent.parent / "json_schema" / "versions"
            except NameError:
                # Fallback if __file__ is not available (e.g., when imported in some contexts)
                import os
                current_dir = Path(os.getcwd())
                # Look for the integration directory structure
                if (current_dir / "src" / "buem" / "integration").exists():
                    self.base_dir = current_dir / "src" / "buem" / "integration" / "json_schema" / "versions"
                elif (current_dir / "buem" / "integration").exists():
                    self.base_dir = current_dir / "buem" / "integration" / "json_schema" / "versions"
                else:
                    # Last resort - assume we're in the integration directory
                    self.base_dir = Path("json_schema") / "versions"
        else:
            self.base_dir = Path(base_dir)
        
        self._version_cache: list[str] | None = None
    
    def _parse_version(self, version_str: str) -> tuple[int, ...]:
        """
        Parse version string into tuple for comparison.
        
        Examples:
            "v2" -> (2,)
            "v2_1" -> (2, 1) 
            "v3_0_1" -> (3, 0, 1)
        """
        if not version_str.startswith("v"):
            raise ValueError(f"Invalid version format: {version_str}")
        
        # Remove 'v' prefix and split on underscores or dots
        version_part = version_str[1:]
        # Handle both underscore and dot separators
        version_part = version_part.replace("_", ".")
        
        try:
            return tuple(int(part) for part in version_part.split(".") if part)
        except ValueError as e:
            raise ValueError(f"Invalid version format: {version_str}") from e
    
    def get_available_versions(self, force_refresh: bool = False) -> list[str]:
        """
        Get list of available schema versions, sorted oldest to newest.
        
        Args:
            force_refresh: Force re-scan of directory
            
        Returns:
            List of version strings (e.g., ['v1', 'v2', 'v2_1'])
        """
        if self._version_cache is not None and not force_refresh:
            return self._version_cache
        
        if not self.base_dir.exists():
            logger.warning(f"Schema directory not found: {self.base_dir}")
            return []
        
        versions_with_tuples = []
        for child in self.base_dir.iterdir():
            if child.is_dir() and child.name.startswith("v"):
                try:
                    version_tuple = self._parse_version(child.name)
                    versions_with_tuples.append((version_tuple, child.name))
                except ValueError:
                    logger.warning(f"Skipping invalid version directory: {child.name}")
                    continue
        
        # Sort by version tuple
        versions_with_tuples.sort(key=lambda x: x[0])
        
        self._version_cache = [version[1] for version in versions_with_tuples]
        return self._version_cache
    
    def get_latest_version(self) -> str:
        """
        Get the latest available schema version.
        
        Returns:
            Latest version string (e.g., 'v2')
            
        Raises:
            FileNotFoundError: If no valid versions found
        """
        versions = self.get_available_versions()
        if not versions:
            raise FileNotFoundError(f"No schema versions found in {self.base_dir}")
        
        return versions[-1]  # Last item is newest after sorting
    
    def get_schema_paths(self, version: str | None = None) -> dict[str, Path]:
        """
        Get file paths for a schema version.
        
        Args:
            version: Version string. If None, uses latest.
            
        Returns:
            Dictionary with paths to schema files:
            {
                "request_schema": Path,
                "response_schema": Path,
                "request_example": Path,
                "response_example": Path
            }
            
        Raises:
            FileNotFoundError: If version directory doesn't exist
        """
        if version is None:
            version = self.get_latest_version()
        
        version_dir = self.base_dir / version
        if not version_dir.exists():
            available = self.get_available_versions()
            raise FileNotFoundError(
                f"Schema version '{version}' not found. "
                f"Available versions: {available}"
            )
        
        return {
            "request_schema": version_dir / "request_schema.json",
            "response_schema": version_dir / "response_schema.json",
            "request_example": version_dir / "example_request.json",
            "response_example": version_dir / "example_response.json"
        }
    
    def load_schema(self, schema_type: str, version: str | None = None) -> dict[str, Any]:
        """
        Load a specific schema file.
        
        Args:
            schema_type: Type of schema ('request' or 'response')
            version: Version string. If None, uses latest.
            
        Returns:
            Loaded JSON schema as dictionary
            
        Raises:
            FileNotFoundError: If schema file doesn't exist
            ValueError: If schema_type is invalid or JSON is malformed
        """
        if schema_type not in ["request", "response"]:
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
        """
        Load an example payload file.
        
        Args:
            example_type: Type of example ('request' or 'response')
            version: Version string. If None, uses latest.
            
        Returns:
            Loaded example payload as dictionary
        """
        if example_type not in ["request", "response"]:
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
        """Check if a specific version exists."""
        return version in self.get_available_versions()
    
    def get_version_info(self, version: str | None = None) -> dict[str, Any]:
        """
        Get information about a schema version.
        
        Returns:
            Dictionary with version metadata including file sizes,
            modification dates, and availability status.
        """
        if version is None:
            version = self.get_latest_version()
        
        paths = self.get_schema_paths(version)
        info: dict[str, Any] = {
            "version": version,
            "is_latest": version == self.get_latest_version(),
            "directory": str(self.base_dir / version),
            "files": {}
        }
        
        for name, path in paths.items():
            if path.exists():
                stat = path.stat()
                info["files"][name] = {
                    "path": str(path),
                    "exists": True,
                    "size_bytes": stat.st_size,
                    "modified": stat.st_mtime
                }
            else:
                info["files"][name] = {
                    "path": str(path),
                    "exists": False
                }
        
        return info


# Convenience instance for the integration module
schema_manager = SchemaVersionManager()