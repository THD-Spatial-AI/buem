"""End-to-end pytest coverage for BUEM GeoJSON validation and processing.

Exercises the same four stages more targeted tests elsewhere in this
directory cover individually (schema validation, superseded-format
rejection, ``GeoJsonProcessor`` end-to-end, response-schema compliance),
but through one shared fixture-building harness (``GeoJsonTestSuite``)
that assembles realistic multi-building payloads.
"""
import json
import logging
from datetime import UTC, datetime
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
            print(f"[{datetime.now(UTC).strftime('%H:%M:%S')}] {message}")

    def test_schema_validation(self) -> dict[str, Any]:
        """Test schema validation functionality."""
        self.log("Testing schema validation...")

        results = {
            'passed': 0,
            'failed': 0,
            'tests': []
        }

        # Test valid sample
        valid_file = self.test_dir / "sample_request.geojson"
        if valid_file.exists():
            test_result = self._test_single_validation(valid_file, should_pass=True)
            results['tests'].append(test_result)
            if test_result['passed']:
                results['passed'] += 1
            else:
                results['failed'] += 1

        # Test existing samples
        for sample_file in ["sample_request.geojson"]:
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
        """Superseded request formats must be rejected, not converted.

        The flat ``building_attributes`` shape -- alone or alongside
        ``child_components`` -- predates the current ``building``/
        ``envelope`` structure and is no longer accepted as input.
        """
        self.log("Testing rejection of superseded request formats...")

        results = {
            'passed': 0,
            'failed': 0,
            'tests': []
        }

        for payload, name in (
            (self._create_child_components_sample(), "child_components_format"),
            (self._create_hybrid_format_sample(), "hybrid_format"),
        ):
            test_result = self._test_validation_payload(payload, name, should_pass=False)
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
        valid_file = self.test_dir / "sample_request.geojson"
        if valid_file.exists():
            test_result = self._test_processing_pipeline(valid_file)
            results['tests'].append(test_result)
            if test_result['passed']:
                results['passed'] += 1
            else:
                results['failed'] += 1

        # Test with existing samples (if they validate)
        for sample_file in []:
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
        valid_file = self.test_dir / "sample_request.geojson"
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

        except (OSError, ValueError, TypeError, KeyError, AttributeError) as e:
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

        except (ValueError, TypeError, KeyError, AttributeError) as e:
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

        except (ValueError, TypeError, KeyError, AttributeError) as e:
            return {
                'test_name': f"convert_{name}",
                'passed': False,
                'error': str(e),
                'message': f"Format conversion test failed: {e}"
            }

    def _test_processing_pipeline(self, file_path: Path) -> dict[str, Any]:
        """Test complete processing pipeline (validation + a real model run).

        Runs the actual weather -> occupancy -> ModelBUEM pipeline (sample_request.geojson
        targets 2018, matching the local weather archive) instead of only checking that
        GeoJsonProcessor.__init__ succeeds -- the old mock-only version couldn't have caught
        a broken pipeline (see CLAUDE.md 2026-08-12 "response shape mismatch" fix).
        """
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

            processor = GeoJsonProcessor(payload, include_timeseries=False)
            response = processor.process()
            feature = response['features'][0] if response.get('features') else {}
            buem = feature.get('properties', {}).get('buem', {})
            succeeded = 'error' not in buem and 'thermal_load_profile' in buem

            return {
                'test_name': f"process_{file_path.name}",
                'passed': succeeded,
                'message': (
                    "Processing pipeline ran end-to-end successfully" if succeeded
                    else f"Processing pipeline failed: {buem.get('error')}"
                ),
                'details': {
                    'validation_passed': True,
                    'thermal_load_profile_present': 'thermal_load_profile' in buem,
                }
            }

        except (OSError, ValueError, TypeError, KeyError, AttributeError) as e:
            return {
                'test_name': f"process_{file_path.name}",
                'passed': False,
                'error': str(e),
                'message': f"Processing pipeline test failed: {e}"
            }

    def _test_response_compliance(self, file_path: Path) -> dict[str, Any]:
        """Test response schema compliance against a REAL response.

        Runs the actual pipeline with include_timeseries=True (matching what the
        EnerPlanET gateway always requests) and checks the real output against
        response_schema.json's structure, instead of a hand-built mock that
        could never fail regardless of what the real code produced -- see
        CLAUDE.md 2026-08-12 "response shape mismatch" fix, which this test
        would have caught had it exercised real output from the start.
        """
        try:
            with file_path.open('r') as f:
                payload = json.load(f)

            response = GeoJsonProcessor(payload, include_timeseries=True).process()

            expected_fields = {
                'type': 'FeatureCollection',
                'features': list,
                'processed_at': str,
                'processing_elapsed_s': (int, float),
                'metadata': dict
            }
            compliance_issues = []

            for field_name, expected_type in expected_fields.items():
                if field_name not in response:
                    compliance_issues.append(f"Missing field: {field_name}")
                elif isinstance(expected_type, str):
                    if response[field_name] != expected_type:
                        compliance_issues.append(f"Wrong value for {field_name}: expected {expected_type}, got {response[field_name]}")
                elif not isinstance(response[field_name], expected_type):
                    compliance_issues.append(f"Wrong type for {field_name}: expected {expected_type}, got {type(response[field_name])}")

            feature = response['features'][0] if response.get('features') else {}
            buem = feature.get('properties', {}).get('buem', {})
            if 'error' in buem:
                compliance_issues.append(f"Feature processing failed: {buem['error']}")
            else:
                if 'model_metadata' not in buem:
                    compliance_issues.append("Missing buem.model_metadata (must be a sibling of thermal_load_profile, not nested inside it)")

                tlp = buem.get('thermal_load_profile')
                if tlp is None:
                    compliance_issues.append("Missing buem.thermal_load_profile")
                else:
                    for field in ('start_time', 'end_time', 'summary'):
                        if field not in tlp:
                            compliance_issues.append(f"Missing thermal_load_profile field: {field}")

                    summary = tlp.get('summary', {})
                    for carrier in ('heating', 'cooling', 'electricity'):
                        stats = summary.get(carrier)
                        if not stats:
                            compliance_issues.append(f"Missing summary.{carrier}")
                            continue
                        for stat_name in ('total', 'max', 'min', 'mean', 'median', 'std'):
                            qty = stats.get(stat_name)
                            if not isinstance(qty, dict) or 'value' not in qty or 'unit' not in qty:
                                compliance_issues.append(f"summary.{carrier}.{stat_name} is not a {{value, unit}} object: {qty!r}")

                    ts = tlp.get('timeseries')
                    if ts is None:
                        compliance_issues.append("Missing thermal_load_profile.timeseries (requested via include_timeseries=True)")
                    else:
                        if 'unit' not in ts:
                            compliance_issues.append("timeseries missing top-level 'unit'")
                        lengths = {k: len(ts.get(k, [])) for k in ('timestamps', 'heating', 'cooling', 'electricity')}
                        if len(set(lengths.values())) != 1:
                            compliance_issues.append(f"timeseries arrays have mismatched lengths: {lengths}")
                        # This is what actually answers "do we send occupancy's
                        # hourly electricity profile to EnerPlanET": a present
                        # but empty/all-zero array would pass every check above
                        # while still not delivering real data.
                        if not any(v != 0 for v in ts.get('electricity', [])):
                            compliance_issues.append("timeseries.electricity is empty or all-zero -- occupancy elecLoad did not reach the response")

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

        except (OSError, ValueError, KeyError, TypeError, IndexError, AttributeError) as e:
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


# -- pytest wrappers -----------------------------------------------------

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


