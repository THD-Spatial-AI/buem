"""
Enhanced JSON Schema Validator for BUEM API Integration.

This module provides comprehensive validation for BUEM (Building Urban Energy Model) 
API payloads by combining standard JSON Schema validation with BUEM-specific 
domain validation rules.

Key Features:
    - JSON Schema validation against versioned schemas from API collaborators
    - BUEM domain-specific validation (building attributes, energy parameters, etc.)
    - Detailed error reporting with line numbers and suggestions  
    - Version-aware validation with automatic latest version detection
    - CLI interface for standalone validation

Classes:
    BuemSchemaValidator: Main validator class combining JSON Schema + domain validation

Usage:
    # Basic validation
    validator = BuemSchemaValidator()
    result = validator.validate_file("request.json")
    
    # Validate against specific version
    validator = BuemSchemaValidator(version="v2")
    result = validator.validate_file("request.json")
    
    # Print detailed results
    validator.print_validation_result(result, verbose=True)
"""
import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any, cast

from jsonschema import Draft202012Validator, ValidationError
from jsonschema.exceptions import SchemaError

from buem.integration.scripts.geojson_validator import create_validation_report, validate_geojson_request
from buem.integration.scripts.schema_manager import SchemaVersionManager

logger = logging.getLogger(__name__)


class BuemSchemaValidator:
    """
    Comprehensive schema validator for BUEM API payloads.
    
    This validator performs two levels of validation:
    1. JSON Schema validation - Ensures structural compliance with API schemas
    2. BUEM domain validation - Validates building energy modeling specific rules
    
    The validator automatically uses the latest available schema version unless
    a specific version is requested.
    
    Attributes:
        version (str): Schema version being used (e.g., 'v2')
        schema_manager (SchemaVersionManager): Manages schema versions
    
    Examples:
        # Create validator with latest schema
        validator = BuemSchemaValidator()
        
        # Create validator with specific version
        validator = BuemSchemaValidator(version="v1")
        
        # Validate a file
        result = validator.validate_file("request.json")
        if result["overall_valid"]:
            print("✅ File is valid!")
        else:
            print("❌ Validation failed")
            validator.print_validation_result(result)
    """
    
    def __init__(self, version: str | None = None, schema_manager_instance: SchemaVersionManager | None = None):
        """
        Initialize the validator.
        
        Args:
            version: Schema version to use. If None, uses latest.
            schema_manager_instance: Custom schema manager instance.
        """
        self.schema_manager = schema_manager_instance or SchemaVersionManager()
        self.version = version or self.schema_manager.get_latest_version()
        self._request_schema: dict[str, Any] | None = None
        self._response_schema: dict[str, Any] | None = None
    
    @property
    def request_schema(self) -> dict[str, Any]:
        """Lazy-load request schema."""
        if self._request_schema is None:
            self._request_schema = self.schema_manager.load_schema("request", self.version)
        return self._request_schema
    
    @property
    def response_schema(self) -> dict[str, Any]:
        """Lazy-load response schema."""
        if self._response_schema is None:
            self._response_schema = self.schema_manager.load_schema("response", self.version)
        return self._response_schema
    
    def validate_json_schema(self, 
                           payload: dict[str, Any], 
                           schema_type: str = "request") -> tuple[bool, str, list[str]]:
        """
        Validate payload against pure JSON Schema.
        
        Args:
            payload: JSON payload to validate
            schema_type: 'request' or 'response'
            
        Returns:
            Tuple of (is_valid, summary_message, error_list)
        """
        try:
            if schema_type == "request":
                schema = self.request_schema
            elif schema_type == "response":
                schema = self.response_schema
            else:
                raise ValueError(f"Invalid schema_type: {schema_type}")
            
            # Validate schema itself first
            Draft202012Validator.check_schema(schema)
            
            # Validate payload
            validator = Draft202012Validator(schema)
            errors = list(validator.iter_errors(payload))
            
            if not errors:
                return True, f"✅ JSON Schema validation passed (version {self.version})", []
            
            error_messages = []
            for error in errors[:10]:  # Limit to first 10 errors
                path = " → ".join(str(p) for p in error.absolute_path) if error.absolute_path else "root"
                error_messages.append(f"  • {path}: {error.message}")
            
            if len(errors) > 10:
                error_messages.append(f"  • ... and {len(errors) - 10} more errors")
            
            summary = f"❌ JSON Schema validation failed ({len(errors)} errors, version {self.version})"
            return False, summary, error_messages
            
        except (OSError, ValueError, SchemaError) as e:
            return False, f"❌ Schema validation error: {e}", [str(e)]
    
    def validate_buem_domain(self, payload: dict[str, Any]) -> tuple[bool, str, list[str]]:
        """
        Validate payload against BUEM domain rules.
        
        Args:
            payload: JSON payload to validate
            
        Returns:
            Tuple of (is_valid, summary_message, detailed_report_lines)
        """
        try:
            result = validate_geojson_request(payload)
            report = create_validation_report(result)
            
            if result.is_valid:
                summary = "✅ BUEM domain validation passed"
                return True, summary, report.split('\n')
            else:
                error_count = len(result.get_errors()) + len(result.get_warnings())
                summary = f"❌ BUEM domain validation failed ({error_count} issues)"
                return False, summary, report.split('\n')
                
        except Exception as e:
            logger.exception("BUEM domain validation failed")
            return False, f"❌ BUEM validation error: {e}", [str(e)]
    
    def validate_comprehensive(self, 
                             payload: dict[str, Any], 
                             schema_type: str = "request",
                             skip_json_schema: bool = False,
                             skip_buem_domain: bool = False) -> dict[str, Any]:
        """
        Run comprehensive validation including both JSON Schema and BUEM domain rules.
        
        Args:
            payload: JSON payload to validate
            schema_type: 'request' or 'response' 
            skip_json_schema: Skip JSON Schema validation
            skip_buem_domain: Skip BUEM domain validation
            
        Returns:
            Validation result dictionary with detailed information
        """
        result: dict[str, Any] = {
            "version": self.version,
            "schema_type": schema_type,
            "overall_valid": True,
            "validations": {}
        }
        
        # JSON Schema Validation
        if not skip_json_schema:
            json_valid, json_summary, json_errors = self.validate_json_schema(payload, schema_type)
            result["validations"]["json_schema"] = {
                "valid": json_valid,
                "summary": json_summary,
                "errors": json_errors
            }
            if not json_valid:
                result["overall_valid"] = False
        
        # BUEM Domain Validation (only for requests)
        if not skip_buem_domain and schema_type == "request":
            buem_valid, buem_summary, buem_report = self.validate_buem_domain(payload)
            result["validations"]["buem_domain"] = {
                "valid": buem_valid,
                "summary": buem_summary,
                "report": buem_report
            }
            if not buem_valid:
                result["overall_valid"] = False
        
        return result
    
    def validate_file(self, 
                     file_path: Path, 
                     schema_type: str = "request",
                     **kwargs) -> dict[str, Any]:
        """
        Validate a JSON file.
        
        Args:
            file_path: Path to JSON file
            schema_type: 'request' or 'response'
            **kwargs: Additional arguments for validate_comprehensive
            
        Returns:
            Validation result dictionary
        """
        try:
            with file_path.open(encoding="utf-8") as f:
                payload = json.load(f)
        except (OSError, ValueError) as e:
            return {
                "version": self.version,
                "schema_type": schema_type,
                "overall_valid": False,
                "file_error": str(e),
                "validations": {}
            }
        
        result = self.validate_comprehensive(payload, schema_type, **kwargs)
        result["file_path"] = str(file_path)
        return result
    
    def print_validation_result(self, result: dict[str, Any], verbose: bool = False) -> None:
        """
        Pretty-print validation results.
        
        Args:
            result: Result from validate_comprehensive or validate_file
            verbose: Show detailed error information
        """
        print("\n🔍 BUEM Schema Validation Results")
        print("=" * 50)
        
        if "file_path" in result:
            print(f"File: {result['file_path']}")
        
        print(f"Schema Version: {result['version']}")
        print(f"Schema Type: {result['schema_type']}")
        
        if "file_error" in result:
            print(f"❌ File Error: {result['file_error']}")
            return
        
        # Show validation results
        validations = result.get("validations", {})
        
        for validation_name, validation_result in validations.items():
            print(f"\n📋 {validation_name.replace('_', ' ').title()}:")
            print(f"   {validation_result['summary']}")
            
            if not validation_result['valid'] and verbose:
                if validation_name == "json_schema":
                    for error in validation_result.get('errors', []):
                        print(f"   {error}")
                elif validation_name == "buem_domain":
                    for line in validation_result.get('report', []):
                        if line.strip():
                            print(f"   {line}")
        
        # Overall summary
        print(f"\n📊 Overall Result: {'✅ PASS' if result['overall_valid'] else '❌ FAIL'}")
        
        if not verbose and not result['overall_valid']:
            print("   (Use --verbose for detailed error information)")


def _validate_payload_legacy(*, 
                           label: str, 
                           schema_path: Path, 
                           instance_path: Path | None, 
                           instance_data: dict[str, Any] | None) -> int:
    """
    Legacy function for compatibility with original schema_validator.py.
    
    This maintains the same interface as the colleague's original validator.
    """
    try:
        schema = cast(Any, json.loads(schema_path.read_text(encoding="utf-8")))
    except FileNotFoundError:
        print(f"❌ Schema file not found: {schema_path}")
        return 2
    except json.JSONDecodeError as e:
        print(f"❌ Invalid JSON in schema {schema_path}: {e}")
        return 2
    
    if instance_data is not None:
        instance = instance_data
        src = "provided payload"
    elif instance_path is not None:
        try:
            instance = json.loads(instance_path.read_text(encoding="utf-8"))
            src = str(instance_path)
        except FileNotFoundError:
            print(f"❌ Instance file not found: {instance_path}")
            return 2
        except json.JSONDecodeError as e:
            print(f"❌ Invalid JSON in {instance_path}: {e}")
            return 2
    else:
        print("❌ Either instance_path or instance_data must be provided")
        return 2
    
    try:
        Draft202012Validator.check_schema(schema)
        Draft202012Validator(schema).validate(instance)
        print(f"✅ VALID {label}: {src} matches {schema_path}")
        return 0
    except (ValidationError, ValueError) as e:
        print(f"❌ INVALID {label}: {src} does not match {schema_path}")
        print(f"   {e}")
        return 2


def main(argv: list[str] | None = None) -> int:
    """
    CLI entry point for BUEM schema validation.
    
    Enhanced version of the colleague's original validator with BUEM integration.
    """
    parser = argparse.ArgumentParser(
        description="Enhanced BUEM Schema Validator with JSON Schema + Domain Validation"
    )
    
    # File or payload to validate
    parser.add_argument("file", type=Path, nargs="?", help="JSON file to validate")
    
    # Schema options
    parser.add_argument("--version", help="Schema version (e.g., v2). Default: latest")
    parser.add_argument("--list-versions", action="store_true", help="List available schema versions")
    parser.add_argument("--schema-info", action="store_true", help="Show schema version information")
    
    # Validation options
    parser.add_argument("--type", choices=["request", "response"], default="request", 
                       help="Schema type to validate against")
    parser.add_argument("--json-only", action="store_true", help="Only JSON schema validation")
    parser.add_argument("--buem-only", action="store_true", help="Only BUEM domain validation")
    
    # Output options
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose error output")
    parser.add_argument("--quiet", "-q", action="store_true", help="Minimal output")
    
    # Legacy compatibility (for colleague's original interface)
    parser.add_argument("--legacy", action="store_true", help="Use legacy validation interface")
    parser.add_argument("--request-schema", type=Path, help="Request schema file (legacy)")
    parser.add_argument("--request-instance", type=Path, help="Request instance file (legacy)")
    parser.add_argument("--response-schema", type=Path, help="Response schema file (legacy)")
    parser.add_argument("--response-instance", type=Path, help="Response instance file (legacy)")
    
    args = parser.parse_args(argv)
    
    try:
        validator = BuemSchemaValidator(version=args.version)
    except (FileNotFoundError, OSError) as e:
        print(f"❌ Failed to initialize validator: {e}")
        return 2
    
    # Handle special commands
    if args.list_versions:
        versions = validator.schema_manager.get_available_versions()
        latest = validator.schema_manager.get_latest_version()
        print("Available schema versions:")
        for version in versions:
            marker = " (latest)" if version == latest else ""
            print(f"  • {version}{marker}")
        return 0
    
    if args.schema_info:
        info = validator.schema_manager.get_version_info(args.version)
        print(f"Schema Version: {info['version']}")
        print(f"Is Latest: {info['is_latest']}")
        print(f"Directory: {info['directory']}")
        print("Files:")
        for name, file_info in info['files'].items():
            status = "✅" if file_info['exists'] else "❌"
            print(f"  {status} {name}: {file_info['path']}")
        return 0
    
    # Legacy compatibility mode
    if args.legacy:
        if not any([args.request_schema, args.response_schema]):
            print("❌ Legacy mode requires --request-schema or --response-schema")
            return 2
        
        codes = []
        if args.request_schema:
            codes.append(_validate_payload_legacy(
                label="request",
                schema_path=args.request_schema,
                instance_path=args.request_instance,
                instance_data=None
            ))
        if args.response_schema:
            codes.append(_validate_payload_legacy(
                label="response", 
                schema_path=args.response_schema,
                instance_path=args.response_instance,
                instance_data=None
            ))
        return 0 if all(c == 0 for c in codes) else 2
    
    # Main validation mode
    if not args.file:
        print("❌ File argument required for validation")
        return 2
    
    if not args.file.exists():
        print(f"❌ File not found: {args.file}")
        return 2
    
    # Determine validation options
    skip_json = args.buem_only
    skip_buem = args.json_only or args.type == "response"
    
    # Run validation
    try:
        result = validator.validate_file(
            args.file,
            schema_type=args.type,
            skip_json_schema=skip_json,
            skip_buem_domain=skip_buem
        )
        
        if not args.quiet:
            validator.print_validation_result(result, verbose=args.verbose)
        
        if args.quiet:
            # Just print final result
            status = "PASS" if result['overall_valid'] else "FAIL"
            print(f"{status}: {args.file}")
        
        return 0 if result['overall_valid'] else 1
        
    except Exception as e:
        logger.exception("Validation failed")
        print(f"❌ Validation error: {e}")
        return 2


if __name__ == "__main__":
    sys.exit(main())