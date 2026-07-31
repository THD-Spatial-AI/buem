"""
Attribute type definitions for the BUEM model configuration system.

This module defines the core types and metadata structures used throughout
the configuration system, including attribute categories, data types, and
attribute specifications.
"""
from dataclasses import dataclass
from enum import Enum
from typing import Any


class AttributeCategory(Enum):
    """Category of attribute used by the API and builder."""
    WEATHER = "weather"
    TABULA = "tabula"
    BOOLEAN = "boolean"
    FIXED = "fixed"
    OTHER = "other"


class AttrType(Enum):
    """Type hints for attribute values to help parsing/validation."""
    DATAFRAME = "dataframe"   # full weather DataFrame
    SERIES = "series"         # time series (pd.Series)
    FLOAT = "float"
    INT = "int"
    BOOL = "bool"
    STR = "str"
    LIST = "list"             # generic list (e.g., roofs)
    OBJECT = "object"         # complex object (dict)
    UNKNOWN = "unknown"


@dataclass
class AttributeSpec:
    """Specification for a configuration attribute."""
    name: str
    category: AttributeCategory
    type: AttrType
    default: Any = None
    doc: str | None = None