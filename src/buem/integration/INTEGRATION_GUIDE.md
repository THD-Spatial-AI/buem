# Enhanced BUEM Integration Module - Setup & Usage Guide

## 🎯 Overview

You now have a comprehensive, versioned schema validation system that integrates seamlessly with your BUEM building energy model API. The system supports:

✅ **Automatic Schema Version Management**: Latest version detection, easy imports from Nextcloud  
✅ **Dual Validation**: JSON Schema compliance + BUEM domain rules  
✅ **Organized Codebase**: Clean separation of scripts, schemas, and tools  
✅ **Extensible Architecture**: Easy to add new versions and validation rules  
✅ **CLI Tools**: Command-line interfaces for validation, testing, and debugging  

## 📁 New Folder Structure

```
src/buem/integration/
├── scripts/                          # Core processing modules
│   ├── __init__.py
│   ├── attribute_builder.py         # Building attribute extraction
│   ├── debug_utils.py               # Debugging and testing utilities
│   ├── geojson_processor.py         # Main processing pipeline
│   ├── geojson_validator.py         # BUEM domain validation  
│   ├── send_geojson.py              # API client CLI
│   └── test_geojson_integration.py  # Integration tests
├── json_schema/                     # Versioned schemas from collaborator
│   └── versions/
│       ├── v1/
│       │   ├── request_schema.json
│       │   ├── response_schema.json
│       │   ├── example_request.json
│       │   └── example_response.json
│       └── v2/                      # Current latest version
│           ├── request_schema.json
│           ├── response_schema.json
│           ├── example_request.json
│           └── example_response.json
├── __init__.py                      # Main module exports
├── schema_manager.py                # Version management system
├── schema_validator.py              # Enhanced schema validator (adapted from colleague)
├── schema_cli.py                    # CLI tool for schema operations
├── workflow_example.py              # Complete workflow demonstration
├── sample_request_v2.geojson       # Sample files
└── sample_request_template.geojson
```

## 🚀 Quick Start

### 1. **Re-sync the pinned contract schema**

The contract is a single pinned copy from `enerplanet/buem-gateway`
(`json_schema/README.md`), not something imported from Nextcloud. When
buem-gateway cuts a new schema tag, follow that README's procedure (fetch
the two files at the new tag, bump `json_schema/contract.txt`), then:

```bash
# Verify the re-sync
python src/buem/integration/schema_cli.py list-versions
python src/buem/integration/schema_cli.py info
```

### 2. **Validate GeoJSON Files**

```bash
# Quick validation (uses latest schema version)
python src/buem/integration/schema_cli.py validate request.json

# Validate with specific version
python src/buem/integration/schema_cli.py validate request.json --version v2

# JSON Schema only (fast)
python src/buem/integration/schema_cli.py validate request.json --json-only

# BUEM domain rules only
python src/buem/integration/schema_cli.py validate request.json --buem-only
```

### 3. **Test All Examples**

```bash
# Test all examples in latest version
python src/buem/integration/schema_cli.py test-all

# Test specific version
python src/buem/integration/schema_cli.py test-all --version v2
```

## 👨‍💻 Python API Usage

### Easy Validation

```python
from buem.integration import validate_request_file

# Quick validation with latest schema
is_valid = validate_request_file("request.json", verbose=True)
if is_valid:
    print("✅ Ready for processing!")
else:
    print("❌ Fix validation errors first")
```

### Comprehensive Validation

```python
from buem.integration import BuemSchemaValidator

# Create validator for specific version
validator = BuemSchemaValidator(version="v2")

# Validate file with detailed results
result = validator.validate_file("request.json")

# Print results
validator.print_validation_result(result, verbose=True)

# Check overall status
if result["overall_valid"]:
    print("All validations passed!")
```

### Processing Pipeline

```python
from buem.integration import GeoJsonProcessor

processor = GeoJsonProcessor()

# Load your payload
import json
with open("request.json") as f:
    payload = json.load(f)

# Process (includes validation)
response = processor.process(payload)
print(f"Processing complete: {len(response['features'])} results")
```

### Schema Management

```python
from buem.integration import schema_manager

# Get latest version
latest = schema_manager.get_latest_version()
print(f"Latest schema: {latest}")

# List all versions
versions = schema_manager.get_available_versions()
print(f"Available: {versions}")

# Get schema info
info = schema_manager.get_version_info("v2")
print(f"Version v2 directory: {info['directory']}")
```

### Advanced Debugging

```python
from buem.integration import BuemDebugger

debugger = BuemDebugger(verbose=True)

# Comprehensive validation and debugging
is_valid = debugger.validate_file("request.json")

if not is_valid:
    # Get detailed diagnostics
    issues = debugger.diagnose_format_issues("request.json")
    print("Detailed issues found:")
    print(issues)
```

## 🔧 Workflow Integration

### For Development (You)

1. **When buem-gateway cuts a new contract tag:**
   ```bash
   # Re-sync (see json_schema/README.md), then:
   python schema_cli.py test-all

   # Validate your existing files against the re-synced contract
   python schema_cli.py validate mytest.json
   ```

2. **For regular validation during development:**
   ```bash
   # Always validate before processing
   python schema_cli.py validate request.json
   
   # If validation fails, debug
   python schema_cli.py debug request.json
   ```

3. **For CI/CD integration:**
   ```bash
   # Quiet mode for automated testing
   python schema_cli.py validate *.json --quiet
   ```

### For API Integration

The new system seamlessly integrates with your existing API:

```python
from flask import Flask, request, jsonify
from buem.integration import validate_request_file, GeoJsonProcessor

app = Flask(__name__)

@app.route('/api/process', methods=['POST'])
def process_building():
    # Save request to temp file for validation
    temp_file = "temp_request.json"
    with open(temp_file, 'w') as f:
        json.dump(request.json, f)
    
    # Validate using latest schema
    if not validate_request_file(temp_file, verbose=False):
        return jsonify({
            "error": "Invalid request format",
            "details": "See validation logs"
        }), 400
    
    # Process using existing pipeline
    processor = GeoJsonProcessor()
    result = processor.process(request.json)
    
    return jsonify(result)
```

## 🎮 Advanced Features

### Version Comparison

```python
# Compare how same data validates against different versions
from buem.integration import BuemSchemaValidator

v1_validator = BuemSchemaValidator(version="v1")
v2_validator = BuemSchemaValidator(version="v2")

v1_result = v1_validator.validate_file("data.json")
v2_result = v2_validator.validate_file("data.json")

print(f"V1 result: {v1_result['overall_valid']}")
print(f"V2 result: {v2_result['overall_valid']}")
```

### Custom Schema Base Directory

```python
# Use custom schema location (e.g., for testing)
from buem.integration.schema_manager import SchemaVersionManager

custom_manager = SchemaVersionManager("/path/to/test/schemas")
validator = BuemSchemaValidator(schema_manager_instance=custom_manager)
```

### Batch Validation

```python
from pathlib import Path
from buem.integration import BuemSchemaValidator

validator = BuemSchemaValidator()

# Validate all JSON files in directory
json_files = Path("test_data").glob("*.json")
results = []

for file_path in json_files:
    result = validator.validate_file(file_path)
    results.append((file_path.name, result["overall_valid"]))

# Summary
passed = sum(1 for _, valid in results if valid)
total = len(results)
print(f"Validation Summary: {passed}/{total} files passed")
```

## ⚠️ Troubleshooting

### Import Issues

If you encounter import errors:

```python
# Test basic imports (requires: pip install -e .)
try:
    from buem.integration.schema_manager import SchemaVersionManager
    print("✅ Schema manager works")
except Exception as e:
    print(f"❌ Issue: {e}")
```

### Schema Directory Issues

```python
# Check schema directory structure
from buem.integration import schema_manager

try:
    versions = schema_manager.get_available_versions()
    print(f"Found versions: {versions}")
except Exception as e:
    print(f"Schema directory issue: {e}")
    print("Make sure json_schema/ contains request_schema.json, response_schema.json, and contract.txt")
```

### Validation Failures

```bash
# Use debug mode for detailed error analysis
python schema_cli.py debug problematic_file.json

# Check specific validation types
python schema_cli.py validate file.json --json-only   # Check JSON Schema compliance
python schema_cli.py validate file.json --buem-only   # Check BUEM domain rules
```

## 🔄 Migration From Old System

Your existing files should work with minimal changes:

1. **Old imports** (update these):
   ```python
   # Old
   from buem.integration.geojson_validator import validate_geojson_request
   
   # New (still works, but better)
   from buem.integration import validate_request_file
   ```

2. **Old validation patterns** (enhanced versions):
   ```python
   # Old approach
   result = validate_geojson_request(payload)
   
   # New approach (backward compatible + enhanced)
   is_valid = validate_request_file("file.json")  # File-based
   # OR
   validator = BuemSchemaValidator()
   result = validator.validate_comprehensive(payload)  # Enhanced
   ```

## 🎯 Benefits of New System

✅ **Version Control**: Easy schema updates from colleague  
✅ **Dual Validation**: Catch more errors with JSON Schema + BUEM rules  
✅ **Better Organization**: Clean folder structure, easier maintenance  
✅ **CLI Tools**: Quick command-line validation and testing  
✅ **Backward Compatibility**: Existing code mostly still works  
✅ **Enhanced Debugging**: Better error messages and diagnostics  
✅ **Extensible**: Easy to add new validation rules and versions  

Your integration workflow is now much more robust and maintainable! 🚀