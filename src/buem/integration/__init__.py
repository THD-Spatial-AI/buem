"""
BUEM Integration Module - Complete API integration toolkit for building energy modeling.

This module provides a comprehensive toolkit for integrating with BUEM (Building Urban Energy Model)
APIs, including validation, processing, and debugging capabilities for GeoJSON building data.

Features:
    ✅ Always Available (Core Features):
        - JSON Schema validation against versioned schemas
        - BUEM domain-specific validation rules  
        - Quick file validation utilities
        - Schema version management
        
    ⚙️ Infrastructure-Dependent (Advanced Features):
        - Full thermal model processing pipeline
        - Comprehensive debugging and testing tools
        - Building attribute extraction
        
Key Classes:
    - BuemSchemaValidator: Enhanced validation combining JSON Schema + domain rules
    - SchemaVersionManager: Handles versioned schema management
    - GeoJsonProcessor: Full processing pipeline (requires BUEM infrastructure)

Quick Start:
    # Validate a GeoJSON request file (most common use case)
    from buem.integration import validate_request_file
    is_valid = validate_request_file("my_request.json")
    
    # Create validator for custom validation
    from buem.integration import BuemSchemaValidator
    validator = BuemSchemaValidator()
    result = validator.validate_file("request.json")
    
    # Check available schema versions
    from buem.integration import get_latest_schema_version, list_schema_versions
    latest = get_latest_schema_version()  # e.g., 'v2'
    all_versions = list_schema_versions()  # e.g., ['v1', 'v2']

Infrastructure Setup (for advanced features):
    Advanced features like GeoJsonProcessor require the full BUEM thermal model
    to be properly installed and configured. If these modules aren't available,
    you'll get clear error messages with setup guidance.

Note:
    This module is designed to work with external JSON schemas provided by API
    collaborators. Schemas are organized by version (v1, v2, etc.) in the 
    json_schema/versions/ directory.
"""

# Always available - core validation modules (no full BUEM infrastructure required)
from buem.integration.scripts.geojson_validator import (
    GeoJsonValidator,
    ValidationLevel,
    ValidationResult,
    create_validation_report,
    validate_geojson_request,
)
from buem.integration.scripts.schema_manager import SchemaVersionManager, schema_manager
from buem.integration.scripts.schema_validator import BuemSchemaValidator


# Lazy imports for infrastructure-dependent modules 
def _get_geojson_processor():
    """Lazy import for GeoJsonProcessor - requires full BUEM infrastructure."""
    try:
        from buem.integration.scripts.geojson_processor import GeoJsonProcessor
        return GeoJsonProcessor
    except ImportError:
        return None

def _get_buem_debugger():
    """Lazy import for BuemDebugger - requires full BUEM infrastructure.""" 
    try:
        from buem.integration.scripts.debug_utils import BuemDebugger
        return BuemDebugger
    except ImportError:
        return None

def _get_attribute_builder():
    """Lazy import for AttributeBuilder - requires full BUEM infrastructure."""
    try:
        from buem.integration.scripts.attribute_builder import AttributeBuilder
        return AttributeBuilder
    except ImportError:
        return None

# Create lazy loader classes that give clear error messages
class _LazyGeoJsonProcessor:
    """Lazy loader for GeoJsonProcessor - loads on first instantiation."""
    def __new__(cls, *args, **kwargs):
        GeojsonProcessorClass = _get_geojson_processor()
        if GeojsonProcessorClass is None:
            raise ImportError(
                "GeoJsonProcessor requires full BUEM infrastructure to be properly configured.\n"
                "Please ensure the BUEM thermal model modules are installed and accessible."
            )
        return GeojsonProcessorClass(*args, **kwargs)

class _LazyBuemDebugger:
    """Lazy loader for BuemDebugger - loads on first instantiation."""
    def __new__(cls, *args, **kwargs):
        BuemDebuggerClass = _get_buem_debugger()
        if BuemDebuggerClass is None:
            raise ImportError(
                "BuemDebugger requires full BUEM infrastructure to be properly configured.\n"
                "Please ensure the BUEM thermal model modules are installed and accessible."
            )
        return BuemDebuggerClass(*args, **kwargs)

class _LazyAttributeBuilder:
    """Lazy loader for AttributeBuilder - loads on first instantiation.""" 
    def __new__(cls, *args, **kwargs):
        AttributeBuilderClass = _get_attribute_builder()
        if AttributeBuilderClass is None:
            raise ImportError(
                "AttributeBuilder requires full BUEM infrastructure to be properly configured.\n"
                "Please ensure the BUEM thermal model modules are installed and accessible."
            )
        return AttributeBuilderClass(*args, **kwargs)

# Export the lazy classes with standard names
GeoJsonProcessor = _LazyGeoJsonProcessor
BuemDebugger = _LazyBuemDebugger  
AttributeBuilder = _LazyAttributeBuilder

# Convenience functions 
def validate_request_file(file_path, version=None, verbose=True):
    """
    Validate a GeoJSON request file against BUEM API schemas.
    
    This is the most commonly used function for validating building energy model
    request files. It performs both JSON Schema validation and BUEM-specific
    domain validation to ensure the file is properly formatted and contains
    valid building data.
    
    Args:
        file_path (str or Path): Path to the GeoJSON request file to validate
        version (str, optional): Schema version to validate against (e.g., 'v2').
                               If None, uses the latest available version.
        verbose (bool): If True, prints detailed validation results and errors.
                       If False, only returns the validation status.
    
    Returns:
        bool: True if the file passes all validation checks, False otherwise.
    
    Examples:
        # Basic validation with detailed output
        is_valid = validate_request_file("my_request.json")
        
        # Quiet validation (just get True/False result)
        is_valid = validate_request_file("request.json", verbose=False)
        
        # Validate against specific schema version
        is_valid = validate_request_file("request.json", version="v1")
    
    Note:
        This function validates both the JSON Schema structure and BUEM-specific
        business rules. For schema-only validation, use BuemSchemaValidator directly.
    """
    from pathlib import Path
    
    validator = BuemSchemaValidator(version=version)
    result = validator.validate_file(Path(file_path), schema_type="request")
    
    if verbose:
        validator.print_validation_result(result, verbose=True)
    
    return result["overall_valid"]

def get_latest_schema_version():
    """
    Get the latest available schema version.
    
    Returns:
        str: The latest schema version identifier (e.g., 'v2', 'v3').
    
    Example:
        current_version = get_latest_schema_version()
        print(f"Using schema version: {current_version}")
    """
    return schema_manager.get_latest_version()

def list_schema_versions():
    """
    List all available schema versions.
    
    Returns:
        List[str]: List of available schema versions in order (e.g., ['v1', 'v2']).
    
    Example:
        versions = list_schema_versions()
        print(f"Available versions: {', '.join(versions)}")
    """
    return schema_manager.get_available_versions()

# Public API
__all__ = [
    # Core classes (always available)
    "BuemSchemaValidator", 
    "SchemaVersionManager",
    "GeoJsonValidator",
    
    # Infrastructure-dependent classes (lazy loaded)
    "GeoJsonProcessor",
    "BuemDebugger", 
    "AttributeBuilder",
    
    # Validation functions
    "validate_geojson_request",
    "create_validation_report", 
    "validate_request_file",
    
    # Enums and data classes
    "ValidationLevel",
    "ValidationResult",
    
    # Manager instances
    "schema_manager",
    
    # Utility functions
    "get_latest_schema_version",
    "list_schema_versions",
]