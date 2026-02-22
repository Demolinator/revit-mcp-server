# -*- coding: utf-8 -*-
from pyrevit import DB
import traceback
import logging

logger = logging.getLogger(__name__)


def normalize_string(text):
    """Safely normalize string values to ASCII-safe output."""
    if text is None:
        return "Unnamed"
    try:
        return str(text).strip().encode('ascii', 'replace').decode('ascii')
    except Exception:
        return "Unnamed"


def sanitize_string(text):
    """Sanitize a string to be ASCII-safe for JSON serialization."""
    if text is None:
        return "Unnamed"
    try:
        return str(text).encode('ascii', 'replace').decode('ascii')
    except Exception:
        return "Unnamed"


def get_element_name(element):
    """
    Get the name of a Revit element.
    Useful for both FamilySymbol and other elements.
    Returns ASCII-safe string for JSON serialization.
    """
    try:
        name = element.Name
    except AttributeError:
        name = DB.Element.Name.__get__(element)
    return sanitize_string(name)


def get_element_id_value(element_or_id):
    """
    Extract an integer element ID from an Element or ElementId.
    Accepts both a full Revit Element and a raw ElementId (duck typing).
    Compatible with Revit 2024, 2025, and 2026.
    Returns a plain Python int for JSON serialization.
    Raises ValueError if the ID cannot be extracted or input is None.
    """
    if element_or_id is None:
        raise ValueError("Cannot extract ElementId from None")
    try:
        eid = element_or_id.Id if hasattr(element_or_id, "Id") else element_or_id
    except Exception:
        raise ValueError("Cannot extract ElementId from input: {}".format(
            type(element_or_id).__name__))
    try:
        return int(eid.Value)
    except (AttributeError, TypeError):
        pass
    try:
        return int(eid.IntegerValue)
    except (AttributeError, TypeError):
        raise ValueError("Cannot read ID value from: {}".format(
            type(element_or_id).__name__))


def make_element_id(id_value):
    """
    Create a DB.ElementId from an integer value.
    Compatible with Revit 2024, 2025, and 2026.
    Tries System.Int64 constructor first (2024+), falls back to int.
    Raises ValueError if the ElementId cannot be created or input is invalid.
    """
    if id_value is None:
        raise ValueError("Cannot create ElementId from None")
    try:
        int_val = int(id_value)
    except (TypeError, ValueError):
        raise ValueError("Cannot create ElementId from {}: not a valid integer".format(
            repr(id_value)))
    try:
        import System
        return DB.ElementId(System.Int64(int_val))
    except (TypeError, OverflowError, ImportError):
        pass
    try:
        return DB.ElementId(int_val)
    except Exception as e:
        raise ValueError("Cannot create ElementId from {}: {}".format(
            id_value, str(e)))


def find_family_symbol_safely(doc, target_family_name, target_type_name=None):
    """
    Safely find a family symbol by name.
    Uses get_element_name() for consistent string handling in IronPython.
    """
    try:
        collector = DB.FilteredElementCollector(doc).OfClass(DB.FamilySymbol)

        for symbol in collector:
            try:
                fam_name = sanitize_string(symbol.Family.Name)
            except Exception:
                continue
            if fam_name == target_family_name:
                if not target_type_name or get_element_name(symbol) == target_type_name:
                    return symbol
        return None
    except Exception as e:
        logger.error("Error finding family symbol: %s", str(e))
        return None
