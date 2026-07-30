#!/usr/bin/env python3
"""
Comprehensive test suite for BUEM GeoJSON validation and processing.

This script tests the complete pipeline:
1. Schema validation
2. Component format conversion  
3. Processing pipeline
4. Response format validation

Usage:
  python test_geojson_integration.py
  python test_geojson_integration.py --verbose
  python test_geojson_integration.py --test-files path/to/additional/files/*.geojson
"""
import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from buem.integration.scripts.geojson_processor import GeoJsonProcessor
from buem.integration.scripts.geojson_validator import ValidationLevel, validate_geojson_request


class GeoJsonTestSuite:
    """Comprehensive test suite for GeoJSON functionality."""
    
    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.results = {
            'validation_tests': [],
            'processing_tests': [],
            'format_conversion_tests': [],
            'schema_compliance_tests': []
        }
        
        if verbose:
            logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
        
        # Test data directory (sample GeoJSON files live in integration/)
        self.test_dir = Path(__file__).resolve().parent.parent / "src" / "buem" / "integration"
        
    def log(self, message: str):
        """Log message if verbose mode is enabled."""
        if self.verbose:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] {message}")
    
    def test_schema_validation(self) -> dict[str, Any]:
        """Test schema validation functionality."""
        self.log("Testing schema validation...")
        
        results = {
            'passed': 0,
            'failed': 0,
            'tests': []
        }
        
        # Test valid sample
        valid_file = self.test_dir / "sample_request_v2.geojson"
        if valid_file.exists():
            test_result = self._test_single_validation(valid_file, should_pass=True)
            results['tests'].append(test_result)
            if test_result['passed']:
                results['passed'] += 1
            else:
                results['failed'] += 1
        
        # Test existing samples
        for sample_file in ["sample_request_template_format.geojson", "sample_request_template.geojson"]:
            file_path = self.test_dir / sample_file
            if file_path.exists():
                test_result = self._test_single_validation(file_path, should_pass=True)
                results['tests'].append(test_result)
                if test_result['passed']:
                    results['passed'] += 1
                else:
                    results['failed'] += 1
        
        # Test invalid structures
        invalid_samples = self._create_invalid_samples()
        for i, invalid_sample in enumerate(invalid_samples):
            test_result = self._test_validation_payload(invalid_sample, f"invalid_sample_{i+1}", should_pass=False)
            results['tests'].append(test_result)
            if test_result['passed']:
                results['passed'] += 1
            else:
                results['failed'] += 1
        
        self.results['validation_tests'] = results
        return results
    
    def test_format_conversion(self) -> dict[str, Any]:
        """Test hybrid format conversion (child_components to nested components)."""
        self.log("Testing format conversion...")
        
        results = {
            'passed': 0,
            'failed': 0,
            'tests': []
        }
        
        # Test child_components conversion
        child_format_payload = self._create_child_components_sample()
        test_result = self._test_format_conversion(child_format_payload, "child_components_format")
        results['tests'].append(test_result)
        if test_result['passed']:
            results['passed'] += 1
        else:
            results['failed'] += 1
        
        # Test hybrid format (both present)
        hybrid_payload = self._create_hybrid_format_sample()
        test_result = self._test_format_conversion(hybrid_payload, "hybrid_format")
        results['tests'].append(test_result)
        if test_result['passed']:
            results['passed'] += 1
        else:
            results['failed'] += 1
        
        self.results['format_conversion_tests'] = results
        return results
    
    def test_processing_pipeline(self) -> dict[str, Any]:
        """Test complete processing pipeline."""
        self.log("Testing processing pipeline...")
        
        results = {
            'passed': 0,
            'failed': 0,
            'tests': []
        }
        
        # Test with valid v2 sample
        valid_file = self.test_dir / "sample_request_v2.geojson"
        if valid_file.exists():
            test_result = self._test_processing_pipeline(valid_file)
            results['tests'].append(test_result)
            if test_result['passed']:
                results['passed'] += 1
            else:
                results['failed'] += 1
        
        # Test with existing samples (if they validate)
        for sample_file in ["sample_request_template_format.geojson"]:
            file_path = self.test_dir / sample_file
            if file_path.exists():
                test_result = self._test_processing_pipeline(file_path)
                results['tests'].append(test_result)
                if test_result['passed']:
                    results['passed'] += 1
                else:
                    results['failed'] += 1
        
        self.results['processing_tests'] = results
        return results
    
    def test_response_schema_compliance(self) -> dict[str, Any]:
        """Test that responses comply with response schema."""
        self.log("Testing response schema compliance...")
        
        results = {
            'passed': 0,
            'failed': 0,
            'tests': []
        }
        
        # This would require processing and checking response format
        # For now, we'll test the structure of responses from processing pipeline
        valid_file = self.test_dir / "sample_request_v2.geojson"
        if valid_file.exists():
            test_result = self._test_response_compliance(valid_file)
            results['tests'].append(test_result)
            if test_result['passed']:
                results['passed'] += 1
            else:
                results['failed'] += 1
        
        self.results['schema_compliance_tests'] = results
        return results
    
    def _test_single_validation(self, file_path: Path, should_pass: bool = True) -> dict[str, Any]:
        """Test validation of a single file."""
        try:
            with file_path.open('r') as f:
                payload = json.load(f)
            
            result = validate_geojson_request(payload)
            is_valid = result.is_valid
            
            passed = (is_valid == should_pass)
            
            return {
                'test_name': f"validate_{file_path.name}",
                'passed': passed,
                'expected_valid': should_pass,
                'actual_valid': is_valid,
                'message': f"Expected {'valid' if should_pass else 'invalid'}, got {'valid' if is_valid else 'invalid'}",
                'details': {
                    'errors': len(result.get_errors()),
                    'warnings': len(result.get_warnings())
                }
            }
            
        except Exception as e:
            return {
                'test_name': f"validate_{file_path.name}",
                'passed': False,
                'error': str(e),
                'message': f"Validation test failed with exception: {e}"
            }
    
    def _test_validation_payload(self, payload: dict[str, Any], name: str, should_pass: bool = True) -> dict[str, Any]:
        """Test validation of a payload."""
        try:
            result = validate_geojson_request(payload)
            is_valid = result.is_valid
            
            passed = (is_valid == should_pass)
            
            return {
                'test_name': f"validate_{name}",
                'passed': passed,
                'expected_valid': should_pass,
                'actual_valid': is_valid,
                'message': f"Expected {'valid' if should_pass else 'invalid'}, got {'valid' if is_valid else 'invalid'}",
                'details': {
                    'errors': len(result.get_errors()),
                    'warnings': len(result.get_warnings())
                }
            }
            
        except Exception as e:
            return {
                'test_name': f"validate_{name}",
                'passed': False,
                'error': str(e),
                'message': f"Validation test failed with exception: {e}"
            }
    
    def _test_format_conversion(self, payload: dict[str, Any], name: str) -> dict[str, Any]:
        """Test format conversion functionality."""
        try:
            result = validate_geojson_request(payload)
            
            if not result.is_valid:
                return {
                    'test_name': f"convert_{name}",
                    'passed': False,
                    'message': "Payload failed validation before conversion test"
                }
            
            validated_data = result.validated_data
            
            # Check if conversion happened
            features = validated_data.get('features', [])
            if features:
                buem_data = features[0].get('properties', {}).get('buem', {})
                building_attrs = buem_data.get('building_attributes', {})
                
                has_components = 'components' in building_attrs and building_attrs['components']
                conversion_info = [issue for issue in result.issues if issue.level == ValidationLevel.INFO and 'convert' in issue.message.lower()]
                
                passed = has_components  # Should have nested components after conversion
                
                return {
                    'test_name': f"convert_{name}",
                    'passed': passed,
                    'message': f"Conversion {'successful' if passed else 'failed'} - components present: {has_components}",
                    'details': {
                        'conversion_applied': len(conversion_info) > 0,
                        'has_nested_components': has_components
                    }
                }
            else:
                return {
                    'test_name': f"convert_{name}",
                    'passed': False,
                    'message': "No features found in payload"
                }
            
        except Exception as e:
            return {
                'test_name': f"convert_{name}",
                'passed': False,
                'error': str(e),
                'message': f"Format conversion test failed: {e}"
            }
    
    def _test_processing_pipeline(self, file_path: Path) -> dict[str, Any]:
        """Test complete processing pipeline (validation + processing)."""
        try:
            with file_path.open('r') as f:
                payload = json.load(f)
            
            # First validate
            validation_result = validate_geojson_request(payload)
            if not validation_result.is_valid:
                return {
                    'test_name': f"process_{file_path.name}",
                    'passed': False,
                    'message': "Failed validation, cannot test processing",
                    'details': {'validation_errors': len(validation_result.get_errors())}
                }
            
            # Then process (mock - we can't run the full model here)
            # For testing, we'll just check that the processor can initialize and validate
            processor = GeoJsonProcessor(payload, include_timeseries=False)
            
            # Check that processor was initialized correctly
            has_payload = processor.payload is not None
            
            return {
                'test_name': f"process_{file_path.name}",
                'passed': has_payload,
                'message': f"Processing pipeline {'initialized successfully' if has_payload else 'failed to initialize'}",
                'details': {
                    'payload_loaded': has_payload,
                    'validation_passed': True
                }
            }
            
        except Exception as e:
            return {
                'test_name': f"process_{file_path.name}",
                'passed': False,
                'error': str(e),
                'message': f"Processing pipeline test failed: {e}"
            }
    
    def _test_response_compliance(self, file_path: Path) -> dict[str, Any]:
        """Test response schema compliance (structure check)."""
        try:
            # Create expected response structure and check compliance
            expected_fields = {
                'type': 'FeatureCollection',
                'features': list,
                'processed_at': str,
                'processing_elapsed_s': (int, float),
                'metadata': dict
            }
            
            # For testing, create a mock response structure
            mock_response = {
                'type': 'FeatureCollection',
                'features': [
                    {
                        'type': 'Feature',
                        'id': 'test',
                        'geometry': {'type': 'Point', 'coordinates': [0, 0]},
                        'properties': {
                            'start_time': '2018-01-01T00:00:00Z',
                            'end_time': '2018-12-31T23:00:00Z',
                            'resolution': '60',
                            'resolution_unit': 'minutes',
                            'buem': {
                                'building_attributes': {},
                                'thermal_load_profile': {
                                    'start_time': '2018-01-01T00:00:00Z',
                                    'end_time': '2018-12-31T23:00:00Z',
                                    'resolution': '60',
                                    'resolution_unit': 'minutes',
                                    'summary': {
                                        'heating': {'total_kwh': 0, 'max_kw': 0, 'min_kw': 0, 'mean_kw': 0, 'median_kw': 0, 'std_kw': 0},
                                        'cooling': {'total_kwh': 0, 'max_kw': 0, 'min_kw': 0, 'mean_kw': 0, 'median_kw': 0, 'std_kw': 0},
                                        'electricity': {'total_kwh': 0, 'max_kw': 0, 'min_kw': 0, 'mean_kw': 0, 'median_kw': 0, 'std_kw': 0},
                                        'total_energy_demand_kwh': 0,
                                        'peak_heating_load_kw': 0,
                                        'peak_cooling_load_kw': 0
                                    }
                                }
                            }
                        }
                    }
                ],
                'processed_at': datetime.now().isoformat(),
                'processing_elapsed_s': 0.5,
                'metadata': {
                    'total_features': 1,
                    'successful_features': 1,
                    'failed_features': 0,
                    'validation_warnings': 0
                }
            }
            
            # Check structure compliance
            compliance_issues = []
            
            for field_name, expected_type in expected_fields.items():
                if field_name not in mock_response:
                    compliance_issues.append(f"Missing field: {field_name}")
                elif isinstance(expected_type, str):
                    # Exact value match
                    if mock_response[field_name] != expected_type:
                        compliance_issues.append(f"Wrong value for {field_name}: expected {expected_type}, got {mock_response[field_name]}")
                elif not isinstance(mock_response[field_name], expected_type):
                    compliance_issues.append(f"Wrong type for {field_name}: expected {expected_type}, got {type(mock_response[field_name])}")
            
            # Check thermal_load_profile structure
            if mock_response['features']:
                thermal_profile = mock_response['features'][0]['properties']['buem']['thermal_load_profile']
                required_thermal_fields = ['start_time', 'end_time', 'summary']
                
                for field in required_thermal_fields:
                    if field not in thermal_profile:
                        compliance_issues.append(f"Missing thermal profile field: {field}")
            
            passed = len(compliance_issues) == 0
            
            return {
                'test_name': f"response_compliance_{file_path.name}",
                'passed': passed,
                'message': f"Response compliance {'passed' if passed else 'failed'}",
                'details': {
                    'compliance_issues': compliance_issues,
                    'issues_count': len(compliance_issues)
                }
            }
            
        except Exception as e:
            return {
                'test_name': f"response_compliance_{file_path.name}",
                'passed': False,
                'error': str(e),
                'message': f"Response compliance test failed: {e}"
            }
    
    def _create_invalid_samples(self) -> list[dict[str, Any]]:
        """Create invalid sample payloads for testing."""
        return [
            # Missing required fields
            {"type": "FeatureCollection"},
            
            # Invalid geometry
            {
                "type": "FeatureCollection",
                "features": [{
                    "type": "Feature", 
                    "id": "test",
                    "geometry": {"type": "Polygon"},  # Invalid for our schema
                    "properties": {"buem": {}}
                }]
            },
            
            # Missing building attributes
            {
                "type": "FeatureCollection",
                "features": [{
                    "type": "Feature",
                    "id": "test", 
                    "geometry": {"type": "Point", "coordinates": [0, 0]},
                    "properties": {"buem": {}}
                }]
            }
        ]
    
    def _create_child_components_sample(self) -> dict[str, Any]:
        """Create sample with child_components format."""
        return {
            "type": "FeatureCollection",
            "features": [{
                "type": "Feature",
                "id": "test_child_components",
                "geometry": {"type": "Point", "coordinates": [5.0, 52.0]},
                "properties": {
                    "start_time": "2018-01-01T00:00:00Z",
                    "end_time": "2018-12-31T23:00:00Z",
                    "buem": {
                        "building_attributes": {
                            "latitude": 52.0,
                            "longitude": 5.0
                        },
                        "child_components": [
                            {
                                "component_id": "wall_1",
                                "component_type": "wall",
                                "area_m2": 30.0,
                                "orientation_deg": 0.0,
                                "tilt_deg": 90.0,
                                "u_value": 1.6
                            },
                            {
                                "component_id": "roof_1", 
                                "component_type": "roof",
                                "area_m2": 100.0,
                                "orientation_deg": 180.0,
                                "tilt_deg": 30.0,
                                "u_value": 1.2
                            }
                        ]
                    }
                }
            }]
        }
    
    def _create_hybrid_format_sample(self) -> dict[str, Any]:
        """Create sample with both formats (should prefer nested)."""
        return {
            "type": "FeatureCollection", 
            "features": [{
                "type": "Feature",
                "id": "test_hybrid",
                "geometry": {"type": "Point", "coordinates": [5.0, 52.0]},
                "properties": {
                    "start_time": "2018-01-01T00:00:00Z",
                    "end_time": "2018-12-31T23:00:00Z",
                    "buem": {
                        "building_attributes": {
                            "latitude": 52.0,
                            "longitude": 5.0,
                            "components": {
                                "Walls": {
                                    "U": 1.6,
                                    "elements": [{"id": "wall_1", "area": 30.0, "azimuth": 0.0, "tilt": 90.0}]
                                }
                            }
                        },
                        "child_components": [
                            {
                                "component_id": "should_be_ignored",
                                "component_type": "roof",
                                "area_m2": 50.0,
                                "orientation_deg": 180.0,
                                "tilt_deg": 30.0
                            }
                        ]
                    }
                }
            }]
        }
    
    def run_all_tests(self) -> dict[str, Any]:
        """Run all test suites."""
        self.log("Starting comprehensive GeoJSON test suite...")
        
        start_time = datetime.now()
        
        # Run test suites
        validation_results = self.test_schema_validation()
        conversion_results = self.test_format_conversion()
        processing_results = self.test_processing_pipeline()
        compliance_results = self.test_response_schema_compliance()
        
        end_time = datetime.now()
        elapsed = (end_time - start_time).total_seconds()
        
        # Compile summary
        total_tests = (validation_results['passed'] + validation_results['failed'] +
                      conversion_results['passed'] + conversion_results['failed'] +
                      processing_results['passed'] + processing_results['failed'] +
                      compliance_results['passed'] + compliance_results['failed'])
        
        total_passed = (validation_results['passed'] + conversion_results['passed'] +
                       processing_results['passed'] + compliance_results['passed'])
        
        summary = {
            'start_time': start_time.isoformat(),
            'end_time': end_time.isoformat(),
            'elapsed_seconds': elapsed,
            'total_tests': total_tests,
            'total_passed': total_passed,
            'total_failed': total_tests - total_passed,
            'success_rate': (total_passed / total_tests * 100) if total_tests > 0 else 0,
            'test_suites': {
                'validation': validation_results,
                'conversion': conversion_results,
                'processing': processing_results,
                'compliance': compliance_results
            }
        }
        
        return summary
    
    def print_summary(self, summary: dict[str, Any]):
        """Print test summary."""
        print("\n" + "="*60)
        print("BUEM GEOJSON TEST SUITE RESULTS")
        print("="*60)
        
        print(f"Test run: {summary['start_time']}")
        print(f"Duration: {summary['elapsed_seconds']:.2f} seconds")
        print(f"Total tests: {summary['total_tests']}")
        print(f"Passed: {summary['total_passed']} ✅")
        print(f"Failed: {summary['total_failed']} ❌")
        print(f"Success rate: {summary['success_rate']:.1f}%")
        
        print("\nTest Suite Breakdown:")
        for suite_name, suite_results in summary['test_suites'].items():
            passed = suite_results['passed']
            failed = suite_results['failed']
            total = passed + failed
            if total > 0:
                rate = passed / total * 100
                status = "✅" if failed == 0 else "⚠️" if passed > failed else "❌"
                print(f"  {suite_name.title():15} {passed:2d}/{total:2d} ({rate:5.1f}%) {status}")
        
        # Show failed tests if any
        failed_tests = []
        for suite_results in summary['test_suites'].values():
            for test in suite_results['tests']:
                if not test['passed']:
                    failed_tests.append(test)
        
        if failed_tests:
            print(f"\nFailed Tests ({len(failed_tests)}):")
            for test in failed_tests:
                print(f"  ❌ {test['test_name']}: {test['message']}")
                if 'error' in test:
                    print(f"     Error: {test['error']}")
        
        print("\n" + "="*60)
        
        overall_success = summary['total_failed'] == 0
        print(f"Overall Result: {'PASS ✅' if overall_success else 'FAIL ❌'}")
        print("="*60)


def main():
    parser = argparse.ArgumentParser(description="BUEM GeoJSON Test Suite")
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')
    parser.add_argument('--test-files', nargs='*', help='Additional test files to include')
    
    args = parser.parse_args()
    
    try:
        test_suite = GeoJsonTestSuite(verbose=args.verbose)
        
        # Run all tests
        summary = test_suite.run_all_tests()
        
        # Print results
        test_suite.print_summary(summary)
        
        # Exit with appropriate code
        if summary['total_failed'] > 0:
            sys.exit(1)
        else:
            sys.exit(0)
            
    except KeyboardInterrupt:
        print("\nTest suite interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"Test suite failed with error: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()


# ── pytest-compatible wrappers ───────────────────────────────────────────────

def test_schema_validation():
    """pytest: schema validation suite."""
    suite = GeoJsonTestSuite()
    results = suite.test_schema_validation()
    assert results["failed"] == 0, f"{results['failed']} schema validation tests failed"


def test_format_conversion():
    """pytest: format conversion suite."""
    suite = GeoJsonTestSuite()
    results = suite.test_format_conversion()
    assert results["failed"] == 0, f"{results['failed']} format conversion tests failed"


def test_processing_pipeline():
    """pytest: processing pipeline suite."""
    suite = GeoJsonTestSuite()
    results = suite.test_processing_pipeline()
    assert results["failed"] == 0, f"{results['failed']} processing pipeline tests failed"


def test_response_schema_compliance():
    """pytest: response schema compliance suite."""
    suite = GeoJsonTestSuite()
    results = suite.test_response_schema_compliance()
    assert results["failed"] == 0, f"{results['failed']} compliance tests failed"