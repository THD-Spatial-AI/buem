#!/usr/bin/env python3
"""Test the schema_validator CLI (--help exits with code 0)."""
import sys
from pathlib import Path

# Resolve project root (this file lives in tests/)
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root / "src"))


def test_schema_cli():
    """Test the CLI functionality."""
    try:
        from buem.integration.schema_validator import main

        print("Testing schema CLI help...")
        result = main(["--help"])
        print(f"Help command result: {result}")

    except SystemExit as e:
        if e.code == 0:
            print("CLI help command exited with code 0 (expected)")
        else:
            raise RuntimeError(f"CLI help failed with exit code: {e.code}")
    except ImportError as e:
        raise ImportError(f"Import error: {e}")


if __name__ == "__main__":
    test_schema_cli()
