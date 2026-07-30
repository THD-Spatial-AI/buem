#!/usr/bin/env python3
"""
Enhanced CLI to POST GeoJSON files to BUEM API with validation and debugging.

Usage:
  python src/buem/integration/send_geojson.py request_template.geojson \
    --url http://127.0.0.1:5000/api/process --include-timeseries --validate
"""
import argparse
import json
import sys
import time
from pathlib import Path

import requests

# Import validation if available
try:
    from buem.integration.scripts.geojson_validator import create_validation_report, validate_geojson_request
    VALIDATION_AVAILABLE = True
except ImportError:
    VALIDATION_AVAILABLE = False
    print("Warning: Validation module not available. Install requirements for full functionality.")


def validate_file(file_path: Path, verbose: bool = True) -> bool:
    """Validate GeoJSON file before sending."""
    if not VALIDATION_AVAILABLE:
        if verbose:
            print("⚠️ Validation skipped (validation module not available)")
        return True
    
    try:
        with file_path.open("r", encoding="utf-8") as f:
            payload = json.load(f)
        
        if verbose:
            print(f"🔍 Validating {file_path.name}...")
        
        result = validate_geojson_request(payload)
        
        if result.is_valid:
            if verbose:
                print("✅ Validation passed")
                warnings = result.get_warnings()
                if warnings:
                    print(f"⚠️ {len(warnings)} warnings:")
                    for warning in warnings:
                        print(f"   - {warning.path}: {warning.message}")
        else:
            if verbose:
                print("❌ Validation failed")
                report = create_validation_report(result)
                print(report)
            return False
        
        return True
        
    except (OSError, ValueError, TypeError, KeyError, AttributeError) as e:
        if verbose:
            print(f"❌ Validation error: {e}")
        return False


def format_response(response: requests.Response, verbose: bool = True) -> None:
    """Format and display API response."""
    print(f"\n📡 HTTP {response.status_code}")
    
    if response.status_code == 200:
        print("✅ Request successful")
    elif response.status_code >= 400:
        print(f"❌ Request failed ({response.status_code})")
    
    try:
        data = response.json()
        
        if verbose and isinstance(data, dict):
            # Display summary info
            if 'metadata' in data:
                metadata = data['metadata']
                print("\n📊 Processing Summary:")
                print(f"   - Total features: {metadata.get('total_features', 'unknown')}")
                print(f"   - Successful: {metadata.get('successful_features', 'unknown')}")
                print(f"   - Failed: {metadata.get('failed_features', 'unknown')}")
                if 'processing_elapsed_s' in data:
                    print(f"   - Processing time: {data['processing_elapsed_s']:.2f}s")
            
            # Display validation info if present
            if 'validation_report' in data:
                report = data['validation_report']
                warnings = report.get('warnings', [])
                errors = report.get('processing_errors', [])
                
                if warnings:
                    print(f"\n⚠️ Validation Warnings ({len(warnings)}):")
                    for warning in warnings[:3]:  # Show first 3
                        print(f"   - {warning.get('path', 'unknown')}: {warning.get('message', 'no message')}")
                    if len(warnings) > 3:
                        print(f"   ... and {len(warnings) - 3} more")
                
                if errors:
                    print(f"\n❌ Processing Errors ({len(errors)}):")
                    for error in errors[:3]:  # Show first 3
                        print(f"   - {error}")
                    if len(errors) > 3:
                        print(f"   ... and {len(errors) - 3} more")
        
        # Full response output
        if verbose:
            print("\n📄 Full Response:")
            print(json.dumps(data, indent=2))
        else:
            # Just show the JSON without extra formatting
            print(json.dumps(data, indent=2))
            
    except json.JSONDecodeError:
        print("\n📄 Response (not JSON):")
        print(response.text)
    except (TypeError, KeyError, AttributeError) as e:
        print(f"\n❌ Error processing response: {e}")
        print(response.text)


def main():
    parser = argparse.ArgumentParser(
        description="Send GeoJSON to BUEM API with validation and enhanced output",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic usage
  python send_geojson.py sample_request.geojson
  
  # With validation and timeseries
  python send_geojson.py sample_request.geojson --validate --include-timeseries
  
  # Custom endpoint
  python send_geojson.py sample_request.geojson --url http://localhost:8080/api/process
  
  # Quiet mode (just JSON output)
  python send_geojson.py sample_request.geojson --quiet
        """
    )
    
    parser.add_argument("file", type=Path, help="Path to GeoJSON file")
    parser.add_argument("--url", default="http://127.0.0.1:5000/api/process", 
                       help="API endpoint URL (default: %(default)s)")
    parser.add_argument("--include-timeseries", action="store_true", 
                       help="Request full timeseries in response")
    parser.add_argument("--validate", action="store_true",
                       help="Validate GeoJSON before sending")
    parser.add_argument("--timeout", type=int, default=120, 
                       help="Request timeout in seconds (default: %(default)s)")
    parser.add_argument("--quiet", "-q", action="store_true",
                       help="Quiet mode - minimal output")
    parser.add_argument("--save-response", "-o", type=Path,
                       help="Save response to file")
    
    args = parser.parse_args()
    
    # Check file exists
    if not args.file.exists():
        print(f"❌ Error: File not found: {args.file}", file=sys.stderr)
        sys.exit(2)
    
    verbose = not args.quiet
    
    if verbose:
        print("🚀 BUEM API Client")
        print(f"📁 File: {args.file}")
        print(f"🌐 URL: {args.url}")
    
    # Validate file if requested
    if args.validate and not validate_file(args.file, verbose):
        if verbose:
            print("\n❌ Aborting due to validation errors")
        sys.exit(3)
    
    # Load and send file
    try:
        with args.file.open("r", encoding="utf-8") as f:
            payload = json.load(f)
    except (OSError, ValueError) as e:
        print(f"❌ Error loading JSON file: {e}", file=sys.stderr)
        sys.exit(3)
    
    # Prepare request parameters
    params = {}
    if args.include_timeseries:
        params["include_timeseries"] = "true"
    
    # Send request
    try:
        if verbose:
            print("\n📡 Sending request...")
            start_time = time.monotonic()

        response = requests.post(
            args.url,
            json=payload,
            params=params,
            timeout=args.timeout
        )

        if verbose:
            elapsed = time.monotonic() - start_time
            print(f"⏱️ Request completed in {elapsed:.2f}s")

    except requests.exceptions.Timeout:
        print(f"❌ Request timed out after {args.timeout} seconds", file=sys.stderr)
        sys.exit(4)
    except requests.exceptions.ConnectionError:
        print(f"❌ Connection error - is the API running at {args.url}?", file=sys.stderr)
        sys.exit(4)
    except requests.exceptions.RequestException as e:
        print(f"❌ Request failed: {e}", file=sys.stderr)
        sys.exit(4)
    
    # Format and display response
    format_response(response, verbose)
    
    # Save response if requested
    if args.save_response:
        try:
            response_data = response.json() if response.headers.get('content-type', '').startswith('application/json') else response.text
            with args.save_response.open('w', encoding='utf-8') as f:
                if isinstance(response_data, dict):
                    json.dump(response_data, f, indent=2)
                else:
                    f.write(response_data)
            
            if verbose:
                print(f"\n💾 Response saved to {args.save_response}")
                
        except (OSError, ValueError, TypeError) as e:
            print(f"⚠️ Warning: Failed to save response: {e}", file=sys.stderr)
    
    # Exit with appropriate code
    if response.status_code >= 400:
        sys.exit(1)
    else:
        if verbose:
            print("\n✅ All done!")


if __name__ == "__main__":
    main()