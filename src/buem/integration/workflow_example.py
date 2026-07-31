#!/usr/bin/env python3
"""
BUEM Integration Workflow - Complete Example and Tutorial

This comprehensive example demonstrates how to use the BUEM integration module
for building energy model API integration. It shows best practices, error handling,
and the complete workflow from validation to processing.

What This Example Demonstrates:
    1. 📋 Schema Version Management - Working with different API schema versions
    2. ✅ Multi-Level Validation - JSON Schema + BUEM domain validation
    3. ⚙️ Processing Pipeline - Full thermal model processing (when available)
    4. 🐛 Debugging & Testing - Comprehensive error diagnosis  
    5. 🔄 Version Switching - Testing compatibility across schema versions

Features Shown:
    • Quick validation using convenience functions
    • Detailed validation with custom settings
    • Schema management and version detection
    • Graceful handling of missing infrastructure components
    • Comprehensive error reporting and debugging

Usage:
    # Run the complete workflow demonstration
    python workflow_example.py
    
    # Or import functions for custom workflows
    from workflow_example import validate_with_comprehensive_approach
    result = validate_with_comprehensive_approach("my_file.json")

Requirements:
    • Core features work with just the integration module
    • Advanced features require full BUEM infrastructure setup
    • Sample GeoJSON files for testing (provided in module)

Note:
    This example gracefully handles missing infrastructure components,
    so it will run and demonstrate core features even without the full
    BUEM thermal modeling environment.
"""

import json
import sys
from pathlib import Path

from buem.integration import validate_request_file
from buem.integration.scripts.schema_manager import SchemaVersionManager

# Import the enhanced integration system (using lazy imports for infrastructure-dependent modules)
from buem.integration.scripts.schema_validator import BuemSchemaValidator


# Lazy imports for modules that require BUEM infrastructure
def get_geojson_processor():
    """
    Safely import GeoJsonProcessor for full processing pipeline.
    
    This function uses lazy importing to avoid errors when the full BUEM
    infrastructure (thermal modeling components) isn't available.
    
    Returns:
        class or None: GeoJsonProcessor class if available, None otherwise
    
    Note:
        Returns None with a warning if BUEM infrastructure isn't configured.
        This allows the example to run core features without requiring
        the complete thermal modeling environment.
    """
    try:
        from buem.integration.scripts.geojson_processor import GeoJsonProcessor
        return GeoJsonProcessor
    except ImportError as e:
        print(f"⚠️  GeoJsonProcessor not available: {e}")
        return None

def get_buem_debugger():
    """
    Safely import BuemDebugger for comprehensive testing capabilities.
    
    This function uses lazy importing to avoid errors when debugging
    components that depend on full BUEM infrastructure aren't available.
    
    Returns:
        class or None: BuemDebugger class if available, None otherwise
        
    Note:
        Returns None with a warning if required components aren't available.
        Core validation and schema management will still work.
    """
    try:
        from buem.integration.scripts.debug_utils import BuemDebugger
        return BuemDebugger
    except ImportError as e:
        print(f"⚠️  BuemDebugger not available: {e}")
        return None


def demonstrate_schema_management():
    """
    Demonstrate versioned schema management capabilities.
    
    Shows how to:
    - Create a schema manager instance
    - List available schema versions
    - Detect the latest version
    - Get version information and file details
    
    This demonstrates the core schema management functionality that's
    always available regardless of BUEM infrastructure setup.
    """
    print("🔧 Schema Version Management")
    print("=" * 50)
    
    # Create schema manager instance
    schema_manager = SchemaVersionManager()
    
    # List available versions
    versions = schema_manager.get_available_versions()
    latest = schema_manager.get_latest_version()
    
    print(f"Available versions: {versions}")
    print(f"Latest version: {latest}")
    
    # Get schema information
    info = schema_manager.get_version_info()
    print("\nLatest version info:")
    print(f"  Directory: {info['directory']}")
    print("  Files available:")
    for name, file_info in info['files'].items():
        status = "✅" if file_info['exists'] else "❌"
        print(f"    {status} {name}")
    
    print()


def validate_with_comprehensive_approach(file_path: Path):
    """
    Demonstrate comprehensive validation approach with detailed output.
    
    Shows how to:
    - Create a BuemSchemaValidator instance
    - Run full validation (JSON Schema + domain rules)
    - Display detailed validation results
    - Handle validation errors gracefully
    
    Args:
        file_path (Path): Path to the GeoJSON file to validate
        
    Returns:
        bool: True if validation passed, False otherwise
        
    This demonstrates the enhanced validation capabilities that combine
    standard JSON Schema validation with BUEM-specific business rules.
    """
    print("🔍 Comprehensive Validation")
    print("=" * 50)
    
    # Create validator for latest version
    validator = BuemSchemaValidator()
    
    print(f"Validating: {file_path}")
    print(f"Using schema version: {validator.version}")
    
    # Run comprehensive validation
    result = validator.validate_file(file_path)
    
    # Print results with full detail
    validator.print_validation_result(result, verbose=True)
    
    return result["overall_valid"]


def demonstrate_processing_pipeline(file_path: Path):
    """Demonstrate the complete processing pipeline."""
    print("\n⚙️ Processing Pipeline")
    print("=" * 50)
    
    try:
        # Load the payload
        with file_path.open() as f:
            payload = json.load(f)
        
        # Create processor (using lazy import)
        GeoJsonProcessorClass = get_geojson_processor()
        if GeoJsonProcessorClass is None:
            print("❌ Cannot run processing pipeline - GeoJsonProcessor not available")
            return False
            
        processor = GeoJsonProcessorClass()
        
        print("Processing building energy model...")
        
        # Process (this includes validation as first step)
        response = processor.process(payload)
        
        print("✅ Processing completed successfully!")
        print(f"Response features: {len(response.get('features', []))}")
        
        # Show processing metadata if available
        if 'metadata' in response:
            metadata = response['metadata']
            print(f"Processing time: {metadata.get('processing_time_seconds', 'N/A')}s")
            print(f"Model runs: {metadata.get('successful_runs', 'N/A')}")
        
        return True
        
    except (OSError, ValueError, KeyError, TypeError) as e:
        print(f"❌ Processing failed: {e}")
        return False


def demonstrate_debugging_workflow(file_path: Path):
    """Demonstrate debugging and testing capabilities."""
    print("\n🐛 Debugging & Testing")
    print("=" * 50)
    
    # Create debugger (using lazy import)
    BuemDebuggerClass = get_buem_debugger()
    if BuemDebuggerClass is None:
        print("❌ Cannot run debugging workflow - BuemDebugger not available")
        return False
        
    debugger = BuemDebuggerClass(verbose=True)
    
    # Validate file with debugging
    print("Running debugging validation...")
    is_valid = debugger.validate_file(file_path)
    
    if not is_valid:
        print("Validation failed - running detailed diagnostics...")
        
        # Test schema compliance
        compliance = debugger.test_schema_compliance(file_path)
        print(f"Schema compliance: {'✅' if compliance else '❌'}")
        
        # Format diagnostics
        format_report = debugger.diagnose_format_issues(file_path)
        if format_report:
            print("Format Issues Found:")
            print(format_report)


def demonstrate_version_switching():
    """Demonstrate working with different schema versions."""
    print("\n📈 Version Management Workflow") 
    print("=" * 50)
    
    # Create schema manager instance
    schema_manager = SchemaVersionManager()
    
    # Get available versions
    versions = schema_manager.get_available_versions()
    if len(versions) < 2:
        print("Only one version available - cannot demonstrate version switching")
        return
    
    # Test with multiple versions
    for version in versions[-2:]:  # Test latest 2 versions
        print(f"\n🔸 Testing with schema version: {version}")
        
        validator = BuemSchemaValidator(version=version)
        
        # Load example for this version
        try:
            example = schema_manager.load_example("request", version=version)
            
            # Validate example against its own version  
            result = validator.validate_comprehensive(example)
            
            status = "✅ Valid" if result["overall_valid"] else "❌ Invalid"
            print(f"   Example validation: {status}")
            
        except (FileNotFoundError, OSError, ValueError, KeyError) as e:
            print(f"   Could not test version {version}: {e}")


def main():
    """Main workflow demonstration."""
    print("🚀 BUEM Enhanced Integration Workflow Demo")
    print("=" * 50)
    
    # Check if sample file exists
    sample_file = Path("src/buem/integration/sample_request_v2.geojson")
    if not sample_file.exists():
        sample_file = Path("sample_request_v2.geojson")
    
    if not sample_file.exists():
        print("❌ Sample file not found. Please provide a valid GeoJSON request file.")
        print("Expected locations:")
        print("  - src/buem/integration/sample_request_v2.geojson")
        print("  - sample_request_v2.geojson")
        return 1
    
    print(f"Using sample file: {sample_file}")
    print()
    
    # 1. Demonstrate schema management
    demonstrate_schema_management()
    
    # 2. Run comprehensive validation
    validation_passed = validate_with_comprehensive_approach(sample_file)
    
    # 3. If validation passed, run processing pipeline
    if validation_passed:
        processing_passed = demonstrate_processing_pipeline(sample_file)
    else:
        print("\n⚠️ Skipping processing due to validation failures")
        processing_passed = False
    
    # 4. Demonstrate debugging capabilities
    demonstrate_debugging_workflow(sample_file)
    
    # 5. Demonstrate version management
    demonstrate_version_switching()
    
    # Summary
    print("\n📊 Workflow Summary")
    print("=" * 50)
    print(f"Schema validation: {'✅ Passed' if validation_passed else '❌ Failed'}")
    print(f"Processing pipeline: {'✅ Passed' if processing_passed else '❌ Failed/Skipped'}")
    
    # Quick validation function demo
    print(f"\n🔍 Quick validation result: {validate_request_file(sample_file, verbose=False)}")
    
    return 0 if validation_passed else 1


if __name__ == "__main__":
    sys.exit(main())