"""
Debugging and testing utilities for BUEM GeoJSON processing.

This module provides utilities for testing, debugging, and validating
GeoJSON payloads and processing results.
"""
import json
import logging
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from marshmallow import ValidationError

from buem.integration.scripts.geojson_processor import GeoJsonProcessor
from buem.integration.scripts.geojson_validator import create_validation_report, validate_geojson_request

logger = logging.getLogger(__name__)


class BuemDebugger:
    """
    Comprehensive debugging utility for BUEM GeoJSON processing.
    
    Provides validation, testing, and diagnostic capabilities for
    development and troubleshooting.
    """
    
    def __init__(self, verbose: bool = True):
        """
        Initialize debugger.
        
        Parameters
        ----------
        verbose : bool
            Enable verbose output.
        """
        self.verbose = verbose
        if verbose:
            logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
    
    def validate_file(self, file_path: str) -> tuple[bool, str]:
        """
        Validate a GeoJSON file.
        
        Parameters
        ----------
        file_path : str
            Path to GeoJSON file.
            
        Returns
        -------
        Tuple[bool, str]
            (is_valid, report) validation result and detailed report.
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                payload = json.load(f)
        except (OSError, ValueError) as e:
            return False, f"Failed to load file {file_path}: {e}"
        
        return self.validate_payload(payload, source=file_path)
    
    def validate_payload(self, payload: dict[str, Any], source: str = "payload") -> tuple[bool, str]:
        """
        Validate a GeoJSON payload.
        
        Parameters
        ----------
        payload : Dict[str, Any]
            GeoJSON payload to validate.
        source : str
            Source description for logging.
            
        Returns
        -------
        Tuple[bool, str]
            (is_valid, report) validation result and detailed report.
        """
        if self.verbose:
            logger.info(f"Validating {source}...")
        
        try:
            result = validate_geojson_request(payload)
            report = create_validation_report(result)
            
            if self.verbose:
                if result.is_valid:
                    logger.info("✅ Validation successful")
                else:
                    logger.error("❌ Validation failed")
                print(report)
            
            return result.is_valid, report

        except (TypeError, KeyError, AttributeError, ValueError, ValidationError) as e:
            error_msg = f"Validation error: {e}"
            if self.verbose:
                logger.error(error_msg)
            return False, error_msg
    
    def test_processing(self, file_path: str, include_timeseries: bool = False) -> dict[str, Any] | None:
        """
        Test complete GeoJSON processing pipeline.
        
        Parameters
        ----------
        file_path : str
            Path to GeoJSON file.
        include_timeseries : bool
            Include timeseries in processing.
            
        Returns
        -------
        Optional[Dict[str, Any]]
            Processing result or None if failed.
        """
        if self.verbose:
            logger.info(f"Testing processing pipeline for {file_path}")
        
        try:
            # Load file
            with open(file_path, 'r', encoding='utf-8') as f:
                payload = json.load(f)
            
            # Validate first
            is_valid, _report = self.validate_payload(payload, source=file_path)
            if not is_valid:
                logger.error("Validation failed, aborting processing test")
                return None

            # Process
            processor = GeoJsonProcessor(payload, include_timeseries=include_timeseries)
            start_time = time.monotonic()
            result = processor.process()
            end_time = time.monotonic()

            # Report results
            total_time = end_time - start_time
            features = result.get('features', [])
            successful = len([f for f in features if 'error' not in f.get('properties', {}).get('buem', {})])
            
            if self.verbose:
                logger.info(f"✅ Processing completed in {total_time:.2f}s")
                logger.info(f"📊 Results: {successful}/{len(features)} features processed successfully")
                
                if 'validation_report' in result:
                    warnings = result['validation_report'].get('warnings', [])
                    errors = result['validation_report'].get('processing_errors', [])
                    if warnings:
                        logger.warning(f"⚠️ {len(warnings)} validation warnings")
                    if errors:
                        logger.error(f"❌ {len(errors)} processing errors")
            
            return result

        except (OSError, ValueError, KeyError, TypeError) as e:
            error_msg = f"Processing test failed: {e}"
            if self.verbose:
                logger.error(error_msg)
            return None
    
    def compare_schemas(self, request_file: str, expected_response_file: str) -> str:
        """
        Compare request and expected response structures.
        
        Parameters
        ----------
        request_file : str
            Path to request GeoJSON file.
        expected_response_file : str
            Path to expected response GeoJSON file.
            
        Returns
        -------
        str
            Comparison report.
        """
        try:
            # Load files
            with open(request_file, 'r') as f:
                request = json.load(f)
            with open(expected_response_file, 'r') as f:
                expected = json.load(f)
            
            # Process request
            result = self.test_processing(request_file)
            if not result:
                return "❌ Processing failed, cannot compare"
            
            # Compare structures
            report = ["=== SCHEMA COMPARISON ===\n"]
            
            # Check basic structure
            req_features = len(request.get('features', []))
            exp_features = len(expected.get('features', []))
            res_features = len(result.get('features', []))
            
            report.append(f"Feature count: Request={req_features}, Expected={exp_features}, Result={res_features}")
            
            # Check response structure
            if res_features > 0:
                result_feature = result['features'][0]
                expected_feature = expected['features'][0] if exp_features > 0 else {}
                
                # Check for thermal_load_profile
                res_buem = result_feature.get('properties', {}).get('buem', {})
                exp_buem = expected_feature.get('properties', {}).get('buem', {})
                
                has_thermal = 'thermal_load_profile' in res_buem
                exp_thermal = 'thermal_load_profile' in exp_buem
                
                report.append(f"Thermal load profile: Result={has_thermal}, Expected={exp_thermal}")
                
                if has_thermal:
                    thermal = res_buem['thermal_load_profile']
                    required_fields = ['start_time', 'end_time', 'summary']
                    missing = [f for f in required_fields if f not in thermal]
                    if missing:
                        report.append(f"❌ Missing required fields in thermal profile: {missing}")
                    else:
                        report.append("✅ All required thermal profile fields present")
            
            return "\n".join(report)

        except (OSError, ValueError, KeyError, IndexError, TypeError) as e:
            return f"❌ Comparison failed: {e}"
    
    def create_test_summary(self, test_files: list[str]) -> str:
        """
        Create a comprehensive test summary for multiple files.
        
        Parameters
        ----------
        test_files : List[str]
            List of GeoJSON file paths to test.
            
        Returns
        -------
        str
            Test summary report.
        """
        report = ["=== BUEM GEOJSON TEST SUMMARY ===\n"]
        report.append(f"Test run: {datetime.now(UTC).isoformat()}\n")
        
        total_files = len(test_files)
        validation_passed = 0
        processing_passed = 0
        
        for i, file_path in enumerate(test_files, 1):
            report.append(f"[{i}/{total_files}] Testing {Path(file_path).name}")
            
            # Validation test
            try:
                is_valid, val_report = self.validate_file(file_path)
                if is_valid:
                    validation_passed += 1
                    report.append("  ✅ Validation: PASS")
                else:
                    report.append("  ❌ Validation: FAIL")
                    report.append(f"     {val_report.split('Status: ')[1].split()[0]}")
            except (IndexError, AttributeError) as e:
                report.append(f"  ❌ Validation: ERROR - {e}")
            
            # Processing test
            try:
                result = self.test_processing(file_path)
                if result:
                    processing_passed += 1
                    report.append("  ✅ Processing: PASS")
                    
                    # Quick stats
                    metadata = result.get('metadata', {})
                    if metadata:
                        successful = metadata.get('successful_features', 0)
                        total = metadata.get('total_features', 0)
                        report.append(f"     Features: {successful}/{total} successful")
                else:
                    report.append("  ❌ Processing: FAIL")
            except (AttributeError, TypeError) as e:
                report.append(f"  ❌ Processing: ERROR - {e}")
            
            report.append("")
        
        # Summary
        report.append("=== SUMMARY ===")
        report.append(f"Files tested: {total_files}")
        report.append(f"Validation passed: {validation_passed}/{total_files} ({validation_passed/total_files*100:.1f}%)")
        report.append(f"Processing passed: {processing_passed}/{total_files} ({processing_passed/total_files*100:.1f}%)")
        
        return "\n".join(report)


def main():
    """CLI interface for debugging utilities."""
    import argparse
    
    parser = argparse.ArgumentParser(description="BUEM GeoJSON Debugging Utilities")
    parser.add_argument('command', choices=['validate', 'test', 'compare', 'summary'], 
                       help='Debug command to run')
    parser.add_argument('files', nargs='+', help='GeoJSON file(s) to process')
    parser.add_argument('--timeseries', action='store_true', help='Include timeseries in processing')
    parser.add_argument('--quiet', action='store_true', help='Suppress verbose output')
    parser.add_argument('--output', '-o', help='Output file for report')
    
    args = parser.parse_args()
    
    debugger = BuemDebugger(verbose=not args.quiet)
    result = ""
    
    try:
        if args.command == 'validate':
            for file_path in args.files:
                _is_valid, report = debugger.validate_file(file_path)
                result += f"=== {file_path} ===\n{report}\n\n"
        
        elif args.command == 'test':
            for file_path in args.files:
                test_result = debugger.test_processing(file_path, args.timeseries)
                success = "SUCCESS" if test_result else "FAILED"
                result += f"=== {file_path}: {success} ===\n"
                if test_result:
                    result += f"Features processed: {len(test_result.get('features', []))}\n"
                result += "\n"
        
        elif args.command == 'compare':
            if len(args.files) != 2:
                print("Compare command requires exactly 2 files: request and expected response")
                sys.exit(1)
            result = debugger.compare_schemas(args.files[0], args.files[1])
        
        elif args.command == 'summary':
            result = debugger.create_test_summary(args.files)
        
        # Output result
        if args.output:
            with open(args.output, 'w') as f:
                f.write(result)
            print(f"Report saved to {args.output}")
        else:
            print(result)
    
    except OSError as e:
        # All BuemDebugger methods above already catch their own errors and
        # return normally; an OSError here can only come from the output
        # file write below.
        logger.error(f"Command failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()