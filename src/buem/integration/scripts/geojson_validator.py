"""
Comprehensive JSON schema validation for BUEM GeoJSON payloads.

This module provides robust validation and debugging capabilities for incoming
GeoJSON requests, supporting both legacy and new component structures.
Uses marshmallow for schema validation with detailed error reporting.
"""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union, Tuple
from datetime import datetime
from enum import Enum
import json
import jsonschema
from marshmallow import Schema, fields, ValidationError, validates, validates_schema, post_load
from marshmallow_dataclass import dataclass as marsh_dataclass
import logging

logger = logging.getLogger(__name__)


class SmartComponentsField(fields.Field):
    """Custom field that validates components with proper context for element types."""
    
    def _serialize(self, value, attr, obj, **kwargs):
        return value
    
    def _deserialize(self, value, attr, data, **kwargs):
        if not isinstance(value, dict):
            raise ValidationError("Components must be a dictionary")
        
        errors = {}
        result = {}
        
        for component_type, component_data in value.items():
            try:
                # Create schema and set context
                schema = ComponentSchema()
                schema.context = {'component_type': component_type}
                result[component_type] = schema.load(component_data)
            except ValidationError as e:
                errors[component_type] = e.messages
        
        if errors:
            raise ValidationError(errors)
        
        return result


class ComponentType(str, Enum):
    """Component types for building elements."""
    WALL = "wall"
    ROOF = "roof"
    FLOOR = "floor"
    WINDOW = "window"
    DOOR = "door"
    VENTILATION = "ventilation"


class ValidationLevel(str, Enum):
    """Validation severity levels."""
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass
class ValidationIssue:
    """Single validation issue with context."""
    level: ValidationLevel
    message: str
    path: str
    value: Any = None
    suggestion: Optional[str] = None


@dataclass
class ValidationResult:
    """Complete validation result with detailed reporting."""
    is_valid: bool
    issues: List[ValidationIssue] = field(default_factory=list)
    validated_data: Optional[Dict[str, Any]] = None
    
    def add_issue(self, level: ValidationLevel, message: str, path: str, 
                  value: Any = None, suggestion: Optional[str] = None):
        """Add a validation issue."""
        self.issues.append(ValidationIssue(level, message, path, value, suggestion))
        if level == ValidationLevel.ERROR:
            self.is_valid = False
    
    def get_errors(self) -> List[ValidationIssue]:
        """Get only error-level issues."""
        return [issue for issue in self.issues if issue.level == ValidationLevel.ERROR]
    
    def get_warnings(self) -> List[ValidationIssue]:
        """Get warning-level issues."""
        return [issue for issue in self.issues if issue.level == ValidationLevel.WARNING]
    
    def summary(self) -> str:
        """Get a summary of validation results."""
        errors = len(self.get_errors())
        warnings = len(self.get_warnings())
        if errors > 0:
            return f"Validation failed: {errors} errors, {warnings} warnings"
        elif warnings > 0:
            return f"Validation passed with {warnings} warnings"
        else:
            return "Validation passed successfully"


class ComponentElementSchema(Schema):
    """Schema for individual building component elements (walls, roof, floor, windows, doors)."""
    id = fields.Str(required=True, validate=lambda x: len(x.strip()) > 0)
    area = fields.Float(required=True, validate=lambda x: x > 0)
    azimuth = fields.Float(required=True, validate=lambda x: 0 <= x <= 360)
    tilt = fields.Float(required=True, validate=lambda x: 0 <= x <= 90)
    # Optional fields for windows/doors
    surface = fields.Str(required=False, allow_none=True)
    U = fields.Float(validate=lambda x: x > 0, required=False, allow_none=True)  # Allow per-element U-values
    
    @validates('id')
    def validate_id_format(self, value, **kwargs):
        """Validate element ID format."""
        if not value or not value.strip():
            raise ValidationError("Element ID cannot be empty")
        # Add any specific ID format requirements here
    
    @validates('azimuth')
    def validate_azimuth_range(self, value, **kwargs):
        """Validate azimuth is in valid range."""
        if not 0 <= value <= 360:
            raise ValidationError("Azimuth must be between 0 and 360 degrees")


class VentilationElementSchema(Schema):
    """Schema for ventilation system elements."""
    id = fields.Str(required=True, validate=lambda x: len(x.strip()) > 0)
    air_changes = fields.Float(required=True, validate=lambda x: x >= 0)
    
    @validates('id')
    def validate_id_format(self, value, **kwargs):
        """Validate element ID format."""
        if not value or not value.strip():
            raise ValidationError("Element ID cannot be empty")
    
    @validates('air_changes')
    def validate_air_changes_range(self, value, **kwargs):
        """Validate air changes is non-negative."""
        if value < 0:
            raise ValidationError("Air changes must be non-negative")


class ComponentSchema(Schema):
    """Schema for building component (Walls, Roof, etc.)."""
    U = fields.Float(validate=lambda x: x > 0, required=False, allow_none=True)  # Component-level U-value
    g_gl = fields.Float(validate=lambda x: 0 < x < 1, required=False, allow_none=True)  # For windows
    b_transmission = fields.Float(validate=lambda x: x > 0, load_default=1.0)
    elements = fields.Raw(required=True, validate=lambda x: len(x) > 0)
    
    @validates('elements')
    def validate_elements(self, value, **kwargs):
        """
        Validate elements using appropriate schema based on component type.
        
        For Ventilation components, use VentilationElementSchema.
        For other components (Walls, Roof, Floor), use ComponentElementSchema.
        """
        if not isinstance(value, list) or len(value) == 0:
            raise ValidationError("Elements must be a non-empty list")
        
        # Get component type from context
        component_type = self.context.get('component_type')
        
        # Choose appropriate schema based on component type
        if component_type and 'ventilation' in component_type.lower():
            schema_class = VentilationElementSchema
        else:
            schema_class = ComponentElementSchema
        
        # Validate each element
        schema = schema_class()
        errors = {}
        
        for i, element_data in enumerate(value):
            try:
                schema.load(element_data)
            except ValidationError as e:
                errors[i] = e.messages
        
        if errors:
            raise ValidationError(errors)
    
    @validates_schema
    def validate_u_value_requirement(self, data, **kwargs):
        """Ensure either component-level or element-level U-values are provided."""
        # Skip U-value validation for ventilation components
        component_type = self.context.get('component_type')
        if component_type and 'ventilation' in component_type.lower():
            return  # Ventilation components use air_changes, not U-values
            
        component_u = data.get('U')
        elements = data.get('elements', [])
        
        if component_u is None:
            # Check if all elements have U-values
            for i, element in enumerate(elements):
                if element.get('U') is None:
                    raise ValidationError(
                        f"Element {i} missing U-value when no component-level U is provided",
                        field_name=f'elements.{i}.U'
                    )


class ChildComponentSchema(Schema):
    """Schema for child components (external format)."""
    component_id = fields.Str(required=True)
    component_type = fields.Str(required=True, validate=lambda x: x.lower() in [e.value for e in ComponentType])
    area_m2 = fields.Float(required=True, validate=lambda x: x > 0)
    orientation_deg = fields.Float(required=True, validate=lambda x: 0 <= x <= 360)
    tilt_deg = fields.Float(required=True, validate=lambda x: 0 <= x <= 90)
    u_value = fields.Float(validate=lambda x: x > 0, required=False, allow_none=True)
    surface_reference = fields.Str(required=False, allow_none=True)  # For windows/doors


class BuildingAttributesSchema(Schema):
    """Schema for building attributes."""
    # Location
    latitude = fields.Float(required=True, validate=lambda x: -90 <= x <= 90)
    longitude = fields.Float(required=True, validate=lambda x: -180 <= x <= 180)
    
    # Basic building properties
    A_ref = fields.Float(validate=lambda x: x > 0, load_default=100.0)
    h_room = fields.Float(validate=lambda x: x > 0, load_default=2.5)
    
    # Optional external format fields
    country = fields.Str(required=False, allow_none=True)
    building_type = fields.Str(required=False, allow_none=True)
    construction_period = fields.Str(required=False, allow_none=True)
    heated_area_m2 = fields.Float(validate=lambda x: x > 0, required=False, allow_none=True)
    volume_m3 = fields.Float(validate=lambda x: x > 0, required=False, allow_none=True)
    height_m = fields.Float(validate=lambda x: x > 0, required=False, allow_none=True)
    
    # Components (nested structure - preferred)
    components = SmartComponentsField(required=False, allow_none=True)
    
    @validates('latitude')
    def validate_latitude(self, value, **kwargs):
        """Validate latitude range."""
        if not -90 <= value <= 90:
            raise ValidationError("Latitude must be between -90 and 90")
    
    @validates('longitude')  
    def validate_longitude(self, value, **kwargs):
        """Validate longitude range."""
        if not -180 <= value <= 180:
            raise ValidationError("Longitude must be between -180 and 180")


class BuemSchema(Schema):
    """Schema for BUEM section.

    Accepts both v2 format (building_attributes) and v3 format
    (building / envelope / thermal / solver).  The v3 sub-objects are
    validated structurally by the JSON Schema layer, so marshmallow only
    checks presence here.
    """
    # v2 format
    building_attributes = fields.Nested(BuildingAttributesSchema, required=False, allow_none=True)
    child_components = fields.List(fields.Nested(ChildComponentSchema), required=False, allow_none=True)
    use_milp = fields.Bool(load_default=False)

    # v3 format — structure validated by JSON Schema
    building = fields.Dict(required=False, allow_none=True)
    envelope = fields.Dict(required=False, allow_none=True)
    thermal = fields.Dict(required=False, allow_none=True)
    solver = fields.Dict(required=False, allow_none=True)

    @validates_schema
    def require_v2_or_v3(self, data, **kwargs):
        """Ensure either v2 (building_attributes) or v3 (building with envelope) is present."""
        has_v2 = data.get('building_attributes') is not None
        has_v3 = (
            isinstance(data.get('building'), dict)
            and isinstance(data['building'].get('envelope'), dict)
        )
        if not has_v2 and not has_v3:
            raise ValidationError(
                "Provide either 'building_attributes' (v2) or 'building' with 'envelope' (v3)",
                field_name='buem',
            )


class PropertiesSchema(Schema):
    """Schema for feature properties."""
    start_time = fields.DateTime(required=True)
    end_time = fields.DateTime(required=True)
    resolution = fields.Raw(load_default="60")
    resolution_unit = fields.Str(load_default="minutes")
    buem = fields.Nested(BuemSchema, required=True)

    @validates('resolution')
    def coerce_resolution(self, value, **kwargs):
        """Accept both int and str, ensure it's a positive number."""
        try:
            int(value)
        except (TypeError, ValueError):
            raise ValidationError("resolution must be a number or numeric string")


class GeometrySchema(Schema):
    """Schema for GeoJSON geometry."""
    type = fields.Str(required=True, validate=lambda x: x == "Point")
    coordinates = fields.List(fields.Float(), required=True, validate=lambda x: len(x) == 2)


class FeatureSchema(Schema):
    """Schema for GeoJSON feature."""
    type = fields.Str(required=True, validate=lambda x: x == "Feature")
    id = fields.Str(required=True)
    geometry = fields.Nested(GeometrySchema, required=True)
    properties = fields.Nested(PropertiesSchema, required=True)


class GeoJsonRequestSchema(Schema):
    """Main schema for GeoJSON request."""
    type = fields.Str(required=True, validate=lambda x: x in ["FeatureCollection", "Feature"])
    features = fields.List(fields.Nested(FeatureSchema), required=True, validate=lambda x: len(x) > 0)
    timeStamp = fields.DateTime(required=False, allow_none=True)
    numberMatched = fields.Int(required=False, allow_none=True)
    numberReturned = fields.Int(required=False, allow_none=True)
    
    @post_load
    def normalize_single_feature(self, data, **kwargs):
        """Convert single Feature to FeatureCollection if needed."""
        if data.get('type') == 'Feature':
            # Convert single feature to collection
            feature = {k: v for k, v in data.items() if k != 'type'}
            data = {
                'type': 'FeatureCollection',
                'features': [feature]
            }
        return data


class GeoJsonValidator:
    """
    Comprehensive GeoJSON validator with hybrid component support.
    
    Supports both:
    1. Nested components structure (preferred): components.Walls.elements[]
    2. Flat child_components structure (external): child_components[]
    
    Provides detailed validation with debugging information.
    """
    
    def __init__(self, strict_mode: bool = False):
        """
        Initialize validator.
        
        Parameters
        ----------
        strict_mode : bool
            If True, warnings are treated as errors.
        """
        self.strict_mode = strict_mode
        self.schema = GeoJsonRequestSchema()
    
    def validate(self, payload: Dict[str, Any]) -> ValidationResult:
        """
        Validate GeoJSON payload with comprehensive error reporting.
        
        Parameters
        ----------
        payload : Dict[str, Any]
            Raw GeoJSON payload to validate.
            
        Returns
        -------
        ValidationResult
            Detailed validation results with errors, warnings, and suggestions.
        """
        result = ValidationResult(is_valid=True)
        
        try:
            # Basic schema validation
            validated_data = self.schema.load(payload)
            result.validated_data = validated_data
            
            # Additional custom validations
            self._validate_features(validated_data['features'], result)
            self._validate_time_consistency(validated_data['features'], result)
            self._convert_components_format(validated_data, result)
            
        except ValidationError as e:
            result.is_valid = False
            self._process_marshmallow_errors(e.messages, result)
        except Exception as e:
            result.add_issue(
                ValidationLevel.ERROR,
                f"Unexpected validation error: {str(e)}",
                "root",
                suggestion="Check payload format and structure"
            )
        
        return result
    
    def _validate_features(self, features: List[Dict], result: ValidationResult):
        """Validate individual features."""
        for i, feature in enumerate(features):
            self._validate_single_feature(feature, f"features[{i}]", result)
    
    def _validate_single_feature(self, feature: Dict, path: str, result: ValidationResult):
        """Validate a single feature (supports both v2 and v3 layout)."""
        buem_data = feature.get('properties', {}).get('buem', {})

        # Detect schema version by key presence
        is_v3 = 'building' in buem_data and isinstance(buem_data.get('building'), dict)

        if is_v3:
            # v3: building.envelope.elements carries the component data
            building = buem_data.get('building', {})
            envelope = building.get('envelope', buem_data.get('envelope', {}))
            if not envelope or not envelope.get('elements'):
                result.add_issue(
                    ValidationLevel.ERROR,
                    "No envelope elements found",
                    f"{path}.properties.buem.building.envelope",
                    suggestion="Provide 'elements' list inside 'building.envelope'"
                )
        else:
            # v2: building_attributes.components or child_components
            building_attrs = buem_data.get('building_attributes', {})
            child_components = buem_data.get('child_components', [])

            has_nested = 'components' in building_attrs and building_attrs['components']
            has_child = child_components and len(child_components) > 0

            if not has_nested and not has_child:
                result.add_issue(
                    ValidationLevel.ERROR,
                    "No building components found",
                    f"{path}.properties.buem",
                    suggestion="Provide either 'components' in building_attributes or 'child_components'"
                )
            elif has_nested and has_child:
                result.add_issue(
                    ValidationLevel.WARNING,
                    "Both component formats provided, nested 'components' will take precedence",
                    f"{path}.properties.buem",
                    suggestion="Use only one component format for clarity"
                )
    
    def _validate_time_consistency(self, features: List[Dict], result: ValidationResult):
        """Validate time range consistency."""
        for i, feature in enumerate(features):
            props = feature.get('properties', {})
            start_time = props.get('start_time')
            end_time = props.get('end_time')
            
            if start_time and end_time:
                if isinstance(start_time, str):
                    start_time = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
                if isinstance(end_time, str):
                    end_time = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
                
                if start_time >= end_time:
                    result.add_issue(
                        ValidationLevel.ERROR,
                        "end_time must be after start_time",
                        f"features[{i}].properties",
                        suggestion="Check time range validity"
                    )
    
    def _convert_components_format(self, data: Dict, result: ValidationResult):
        """Convert child_components or v3 envelope to nested components format if needed."""
        for i, feature in enumerate(data.get('features', [])):
            buem_data = feature.get('properties', {}).get('buem', {})
            
            # Check for v3 format: building.envelope.elements
            building = buem_data.get('building')
            if isinstance(building, dict) and isinstance(building.get('envelope'), dict):
                try:
                    self._convert_v3_to_v2(feature, result, i)
                except Exception as e:
                    result.add_issue(
                        ValidationLevel.ERROR,
                        f"Failed to convert v3 format to internal format: {str(e)}",
                        f"features[{i}].properties.buem.building"
                    )
                continue
            
            # v2 child_components conversion
            building_attrs = buem_data.get('building_attributes', {})
            child_components = buem_data.get('child_components', [])
            
            # If no nested components but have child_components, convert
            if (not building_attrs.get('components') and child_components):
                try:
                    converted = self._child_to_nested_components(child_components)
                    building_attrs['components'] = converted
                    result.add_issue(
                        ValidationLevel.INFO,
                        "Converted child_components to nested components format",
                        f"features[{i}].properties.buem.building_attributes"
                    )
                except Exception as e:
                    result.add_issue(
                        ValidationLevel.ERROR,
                        f"Failed to convert child_components: {str(e)}",
                        f"features[{i}].properties.buem.child_components"
                    )
    
    def _convert_v3_to_v2(self, feature: Dict, result: ValidationResult, feature_idx: int):
        """
        Convert v3 format (building.envelope.elements with {value,unit} objects) 
        to v2 format (building_attributes.components) for internal processing.
        
        The v3 format uses:
          - buem.building.envelope.elements[] with type-based grouping
          - Explicit {value, unit} measurement objects
          
        This converts to:
          - buem.building_attributes.components.{Walls,Roof,...}.elements[]
          - Plain numeric values
        """
        buem_data = feature['properties']['buem']
        building = buem_data['building']
        envelope = building.get('envelope', {})
        elements = envelope.get('elements', [])
        thermal = building.get('thermal', {})
        
        # Extract scalar values from {value, unit} objects
        def extract_value(obj):
            """Extract numeric value from either {value, unit} dict or plain value."""
            if isinstance(obj, dict) and 'value' in obj:
                return obj['value']
            return obj
        
        # Extract building-level attributes
        latitude = feature.get('geometry', {}).get('coordinates', [0, 0])[1]
        longitude = feature.get('geometry', {}).get('coordinates', [0, 0])[0]
        A_ref = extract_value(building.get('A_ref', 100.0))
        h_room = extract_value(building.get('h_room', 2.5))
        
        # Group elements by type → component categories
        type_map = {
            'wall': 'Walls',
            'roof': 'Roof',
            'floor': 'Floor',
            'window': 'Windows',
            'door': 'Doors',
            'ventilation': 'Ventilation',
        }
        
        components = {}
        for elem in elements:
            elem_type = elem.get('type', '').lower()
            comp_key = type_map.get(elem_type)
            if not comp_key:
                result.add_issue(
                    ValidationLevel.WARNING,
                    f"Unknown element type '{elem_type}' in envelope",
                    f"features[{feature_idx}].properties.buem.building.envelope",
                    suggestion=f"Valid types: {', '.join(type_map.keys())}"
                )
                continue
            
            if comp_key not in components:
                components[comp_key] = {'elements': []}
            
            if elem_type == 'ventilation':
                converted_elem = {
                    'id': elem.get('id', f'Vent_{len(components[comp_key]["elements"])+1}'),
                    'air_changes': extract_value(elem.get('air_changes', 0.5)),
                }
            else:
                converted_elem = {
                    'id': elem.get('id', f'{comp_key}_{len(components[comp_key]["elements"])+1}'),
                    'area': extract_value(elem.get('area', 0)),
                    'azimuth': extract_value(elem.get('azimuth', 0)),
                    'tilt': extract_value(elem.get('tilt', 0)),
                }
                
                # U-value (per-element)
                if 'U' in elem:
                    converted_elem['U'] = extract_value(elem['U'])
                
                # b_transmission
                if 'b_transmission' in elem:
                    converted_elem['b_transmission'] = extract_value(elem['b_transmission'])
                
                # Window-specific: g_gl, parent_id→surface
                if elem_type == 'window':
                    if 'g_gl' in elem:
                        components[comp_key].setdefault('g_gl', extract_value(elem['g_gl']))
                    if 'parent_id' in elem:
                        converted_elem['surface'] = elem['parent_id']
                
                # Door-specific: parent_id→surface
                if elem_type == 'door' and 'parent_id' in elem:
                    converted_elem['surface'] = elem['parent_id']
            
            components[comp_key]['elements'].append(converted_elem)
        
        # Set component-level U-values from first element if all share the same value
        for comp_key, comp_data in components.items():
            if comp_key == 'Ventilation':
                continue
            elems = comp_data['elements']
            u_values = [e.get('U') for e in elems if 'U' in e]
            if u_values and len(u_values) == len(elems) and len(set(u_values)) == 1:
                comp_data['U'] = u_values[0]
                for e in elems:
                    e.pop('U', None)
        
        # Extract thermal parameters
        n_air_infiltration = extract_value(thermal.get('n_air_infiltration', 0.5))
        n_air_use = extract_value(thermal.get('n_air_use', 0.5))
        comfortT_lb = extract_value(thermal.get('comfortT_lb', 21))
        comfortT_ub = extract_value(thermal.get('comfortT_ub', 24))
        
        # Build v2 building_attributes
        building_attributes = {
            'latitude': latitude,
            'longitude': longitude,
            'A_ref': A_ref,
            'h_room': h_room,
            'components': components,
            # Thermal parameters
            'n_air_infiltration': n_air_infiltration,
            'n_air_use': n_air_use,
            'comfortT_lb': comfortT_lb,
            'comfortT_ub': comfortT_ub,
        }
        
        # Optional building metadata
        for key in ('building_type', 'construction_period', 'country', 'n_storeys',
                     'neighbour_status', 'attic_condition', 'cellar_condition'):
            if key in building:
                building_attributes[key] = building[key]
        
        # Extract solver settings
        solver = buem_data.get('solver', {})
        use_milp = solver.get('use_milp', False)
        
        # Replace buem section with v2 format
        buem_data['building_attributes'] = building_attributes
        buem_data['use_milp'] = use_milp
        
        result.add_issue(
            ValidationLevel.INFO,
            "Converted v3 format (building.envelope) to v2 internal format (building_attributes.components)",
            f"features[{feature_idx}].properties.buem"
        )
    
    def _child_to_nested_components(self, child_components: List[Dict]) -> Dict[str, Any]:
        """Convert child_components array to nested components structure."""
        components = {}
        
        # Group by component type
        for child in child_components:
            comp_type = child['component_type'].lower()
            
            # Map component types
            if comp_type == 'wall':
                comp_key = 'Walls'
            elif comp_type == 'roof':
                comp_key = 'Roof'
            elif comp_type == 'floor':
                comp_key = 'Floor'
            elif comp_type == 'window':
                comp_key = 'Windows'
            elif comp_type == 'door':
                comp_key = 'Doors'
            else:
                comp_key = comp_type.title()
            
            if comp_key not in components:
                components[comp_key] = {'elements': []}
            
            # Convert to element format
            element = {
                'id': child['component_id'],
                'area': child['area_m2'],
                'azimuth': child['orientation_deg'],
                'tilt': child['tilt_deg']
            }
            
            if child.get('u_value'):
                element['U'] = child['u_value']
            if child.get('surface_reference'):
                element['surface'] = child['surface_reference']
            
            components[comp_key]['elements'].append(element)
        
        # Set default U-values if not provided per-element
        default_u_values = {
            'Walls': 1.6,
            'Roof': 1.5,
            'Floor': 1.7,
            'Windows': 2.5,
            'Doors': 3.5
        }
        
        for comp_key, comp_data in components.items():
            elements = comp_data['elements']
            has_element_u = any(elem.get('U') for elem in elements)
            
            if not has_element_u and comp_key in default_u_values:
                comp_data['U'] = default_u_values[comp_key]
            
            # Add special properties for windows
            if comp_key == 'Windows':
                comp_data['g_gl'] = 0.5  # Default solar gain
        
        return components
    
    def _process_marshmallow_errors(self, errors: Dict, result: ValidationResult):
        """Process marshmallow validation errors."""
        self._flatten_errors(errors, result, "")
    
    def _flatten_errors(self, errors: Union[Dict, List, str], result: ValidationResult, path: str):
        """Recursively flatten nested error messages with actionable suggestions."""
        if isinstance(errors, dict):
            for key, value in errors.items():
                new_path = f"{path}.{key}" if path else key
                self._flatten_errors(value, result, new_path)
        elif isinstance(errors, list):
            for error in errors:
                result.add_issue(
                    ValidationLevel.ERROR,
                    str(error),
                    path,
                    suggestion=self._suggest_fix(str(error), path)
                )
        else:
            result.add_issue(
                ValidationLevel.ERROR,
                str(errors),
                path,
                suggestion=self._suggest_fix(str(errors), path)
            )

    @staticmethod
    def _suggest_fix(error_msg: str, path: str) -> str:
        """Return an actionable suggestion based on the error text and field path."""
        msg = error_msg.lower()

        if "missing data for required field" in msg:
            field_name = path.rsplit('.', 1)[-1] if '.' in path else path
            if field_name == 'building_attributes':
                return ("v2 format expects 'building_attributes' inside buem. "
                        "If using v3 format, provide 'building' and 'envelope' instead")
            return f"Add the required '{field_name}' field"

        if "unknown field" in msg:
            field_name = path.rsplit('.', 1)[-1] if '.' in path else path
            if field_name in ('building', 'envelope', 'thermal', 'solver'):
                return ("These are v3 schema keys. Ensure the marshmallow domain "
                        "validator and JSON Schema version both target v3")
            return f"'{field_name}' is not recognised at this level — check spelling or nesting"

        if "not a valid" in msg:
            return f"Value at '{path}' has the wrong type — check the expected format"

        if "must be" in msg or "between" in msg:
            return f"Value at '{path}' is out of range — see the constraint in the error"

        if "length" in msg or "empty" in msg:
            return f"'{path}' must not be empty"

        return f"Review the value at '{path}' — see error message above for details"


def validate_geojson_request(payload: Dict[str, Any], strict_mode: bool = False) -> ValidationResult:
    """
    Convenience function to validate GeoJSON request.
    
    Parameters
    ----------
    payload : Dict[str, Any]
        GeoJSON payload to validate.
    strict_mode : bool
        Treat warnings as errors.
        
    Returns
    -------
    ValidationResult
        Validation results with detailed error reporting.
    """
    validator = GeoJsonValidator(strict_mode=strict_mode)
    return validator.validate(payload)


def create_validation_report(result: ValidationResult) -> str:
    """
    Create a detailed validation report.
    
    Parameters
    ----------
    result : ValidationResult
        Validation result to report.
        
    Returns
    -------
    str
        Formatted validation report.
    """
    report = [f"=== VALIDATION REPORT ==="]
    report.append(f"Status: {result.summary()}")
    report.append("")
    
    if result.get_errors():
        report.append("ERRORS:")
        for issue in result.get_errors():
            report.append(f"  ❌ {issue.path}: {issue.message}")
            if issue.suggestion:
                report.append(f"     💡 Suggestion: {issue.suggestion}")
        report.append("")
    
    if result.get_warnings():
        report.append("WARNINGS:")
        for issue in result.get_warnings():
            report.append(f"  ⚠️  {issue.path}: {issue.message}")
            if issue.suggestion:
                report.append(f"     💡 Suggestion: {issue.suggestion}")
        report.append("")
    
    info_issues = [i for i in result.issues if i.level == ValidationLevel.INFO]
    if info_issues:
        report.append("INFO:")
        for issue in info_issues:
            report.append(f"  ℹ️  {issue.path}: {issue.message}")
        report.append("")
    
    return "\n".join(report)