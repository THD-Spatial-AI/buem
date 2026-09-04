#!/usr/bin/env python3
"""
BUEM Schema Management CLI Tool

Convenient command-line interface for managing versioned schemas,
validation, and integration workflow tasks.

There is a single pinned contract schema (see
src/buem/integration/json_schema/README.md), not a version tree to import
into -- re-sync it by following that README's procedure, not with this
tool.

Usage Examples:
    # Show the pinned contract version
    python schema_cli.py list-versions

    # Validate a request file
    python schema_cli.py validate request.json

    # Show schema information
    python schema_cli.py info

    # Run comprehensive tests
    python schema_cli.py test-all

    # Comprehensive debugging
    python schema_cli.py debug request.json
"""

import argparse
import sys
from pathlib import Path

from jsonschema import ValidationError

from buem.integration.scripts.debug_utils import BuemDebugger
from buem.integration.scripts.schema_manager import SchemaVersionManager
from buem.integration.scripts.schema_validator import BuemSchemaValidator


class SchemaCLI:
    """Command-line interface for BuEM schema management."""
    
    def __init__(self):
        self.schema_manager = SchemaVersionManager()
    
    def list_versions(self) -> int:
        """List all available schema versions."""
        try:
            versions = self.schema_manager.get_available_versions()
            latest = self.schema_manager.get_latest_version()
            
            if not versions:
                print("No schema versions found.")
                return 1
            
            print("Available Schema Versions:")
            print("-" * 30)
            for version in versions:
                marker = " (latest)" if version == latest else ""
                print(f"  • {version}{marker}")
            
            print(f"\nTotal: {len(versions)} versions")
            return 0
            
        except (OSError, ValueError, KeyError, ValidationError) as e:
            print(f"❌ Error listing versions: {e}")
            return 1
    
    def show_info(self, version: str | None = None) -> int:
        """Show detailed information about a schema version."""
        try:
            info = self.schema_manager.get_version_info(version)
            
            print(f"Schema Version: {info['version']}")
            print(f"Is Latest: {'Yes' if info['is_latest'] else 'No'}")
            print(f"Directory: {info['directory']}")
            print()
            print("Files:")
            print("-" * 30)
            
            for name, file_info in info['files'].items():
                status = "✅" if file_info['exists'] else "❌"
                size = file_info.get('size_bytes', 0) if file_info['exists'] else 0
                size_str = f"({size_bytes_format(size)})" if size > 0 else ""
                
                print(f"  {status} {name}: {size_str}")
                if file_info['exists']:
                    print(f"      {file_info['path']}")
            
            return 0
            
        except (OSError, ValueError, KeyError, ValidationError) as e:
            print(f"❌ Error getting version info: {e}")
            return 1
    
    def validate_file(self, file_path: Path, version: str | None = None, 
                     json_only: bool = False, buem_only: bool = False,
                     quiet: bool = False) -> int:
        """Validate a JSON file against schemas."""
        try:
            if not file_path.exists():
                print(f"❌ File not found: {file_path}")
                return 1
            
            validator = BuemSchemaValidator(version=version)
            
            result = validator.validate_file(
                file_path,
                schema_type="request",
                skip_json_schema=buem_only,
                skip_buem_domain=json_only
            )
            
            if not quiet:
                validator.print_validation_result(result, verbose=True)
            else:
                status = "PASS" if result['overall_valid'] else "FAIL"
                print(f"{status}: {file_path}")
            
            return 0 if result['overall_valid'] else 1
            
        except (OSError, ValueError, KeyError, ValidationError) as e:
            print(f"❌ Validation error: {e}")
            return 1
    
    def test_all_examples(self, version: str | None = None) -> int:
        """Test all example files for a version."""
        try:
            target_version = version or self.schema_manager.get_latest_version()
            validator = BuemSchemaValidator(version=target_version)
            
            print(f"🧪 Testing all examples for version {target_version}")
            print("=" * 50)
            
            paths = self.schema_manager.get_schema_paths(target_version)
            
            results = []
            
            # Test request example
            if paths["request_example"].exists():
                print("\n📄 Testing Request Example:")
                result = validator.validate_file(paths["request_example"])
                validator.print_validation_result(result, verbose=False)
                results.append(("request", result["overall_valid"]))
            else:
                print("❌ Request example not found")
                results.append(("request", False))
            
            # Test response example  
            if paths["response_example"].exists():
                print("\n📄 Testing Response Example:")
                result = validator.validate_file(paths["response_example"], schema_type="response")
                validator.print_validation_result(result, verbose=False)
                results.append(("response", result["overall_valid"]))
            else:
                print("❌ Response example not found")
                results.append(("response", False))
            
            # Summary
            print("\n📊 Test Summary:")
            print("-" * 30)
            all_passed = True
            for test_type, passed in results:
                status = "✅ PASS" if passed else "❌ FAIL"
                print(f"  {test_type.title()} Example: {status}")
                if not passed:
                    all_passed = False
            
            print(f"\nOverall: {'✅ ALL TESTS PASSED' if all_passed else '❌ SOME TESTS FAILED'}")
            
            return 0 if all_passed else 1
            
        except (OSError, ValueError, KeyError, ValidationError) as e:
            print(f"❌ Testing error: {e}")
            return 1
    
    def debug_file(self, file_path: Path) -> int:
        """Run comprehensive debugging on a file."""
        try:
            debugger = BuemDebugger(verbose=True)
            
            print(f"🐛 Debugging: {file_path}")
            print("=" * 50)
            
            # Comprehensive validation and debugging
            is_valid, _report = debugger.validate_file(str(file_path))

            if not is_valid:
                print("\n🔍 Running additional diagnostics...")
                
                # Test processing
                try:
                    debugger.test_processing(str(file_path))
                except (OSError, ValueError, KeyError, ValidationError) as e:
                    print(f"Processing test failed: {e}")
            
            return 0 if is_valid else 1
            
        except (OSError, ValueError, KeyError, ValidationError) as e:
            print(f"❌ Debug error: {e}")
            return 1


def size_bytes_format(size_bytes: int) -> str:
    """Format bytes into human readable string."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.1f} MB"


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="BuEM Schema Management CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s list-versions                    # Show the pinned contract version
  %(prog)s info                             # Show pinned schema file info
  %(prog)s validate request.json            # Validate file against the pinned schema
  %(prog)s test-all                         # Test all examples
  %(prog)s debug request.json               # Comprehensive debugging
        """
    )

    subparsers = parser.add_subparsers(dest='command', help='Available commands')

    # list-versions command
    subparsers.add_parser('list-versions', help='Show the pinned contract version')

    # info command
    info_parser = subparsers.add_parser('info', help='Show schema version information')
    info_parser.add_argument('--version', help='Must match the pinned contract version, if given')

    # validate command
    validate_parser = subparsers.add_parser('validate', help='Validate a file')
    validate_parser.add_argument('file', type=Path, help='File to validate')
    validate_parser.add_argument('--version', help='Must match the pinned contract version, if given')
    validate_parser.add_argument('--json-only', action='store_true', help='Only JSON schema validation')
    validate_parser.add_argument('--buem-only', action='store_true', help='Only BUEM domain validation')
    validate_parser.add_argument('--quiet', '-q', action='store_true', help='Minimal output')

    # test-all command
    test_parser = subparsers.add_parser('test-all', help='Test all example files')
    test_parser.add_argument('--version', help='Must match the pinned contract version, if given')

    # debug command
    debug_parser = subparsers.add_parser('debug', help='Debug a file comprehensively')
    debug_parser.add_argument('file', type=Path, help='File to debug')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    cli = SchemaCLI()
    
    if args.command == 'list-versions':
        return cli.list_versions()
    elif args.command == 'info':
        return cli.show_info(args.version)
    elif args.command == 'validate':
        return cli.validate_file(args.file, args.version, args.json_only, args.buem_only, args.quiet)
    elif args.command == 'test-all':
        return cli.test_all_examples(args.version)
    elif args.command == 'debug':
        return cli.debug_file(args.file)
    else:
        print(f"Unknown command: {args.command}")
        return 1


if __name__ == "__main__":
    sys.exit(main())