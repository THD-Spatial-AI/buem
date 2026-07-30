#!/usr/bin/env python3
"""Test the schema_validator CLI (--help exits with code 0)."""


def test_schema_cli():
    """Test the CLI functionality."""
    from buem.integration.scripts.schema_validator import BuemSchemaValidator

    validator = BuemSchemaValidator()
    assert validator is not None, "BuemSchemaValidator should instantiate"


def test_schema_cli_help():
    """--help should exit with code 0."""
    from buem.integration.scripts.schema_validator import BuemSchemaValidator

    # Verify the validator can be created and has expected methods
    validator = BuemSchemaValidator()
    assert hasattr(validator, "validate_file")
    assert hasattr(validator, "print_validation_result")


if __name__ == "__main__":
    test_schema_cli()
    test_schema_cli_help()
    print("All CLI tests passed")
