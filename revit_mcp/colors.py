# -*- coding: UTF-8 -*-
"""
Color management functionality for Revit elements
Provides tools for color splashing elements based on parameter values
"""

from utils import get_element_id_value
from pyrevit import routes, DB
import json
import logging
import random
from collections import defaultdict
from .utils import normalize_string

logger = logging.getLogger(__name__)


def generate_distinct_colors(count):
    """
    Generate visually distinct colors using predefined RGB values

    Args:
        count (int): Number of distinct colors needed

    Returns:
        list: List of DB.Color objects with distinct colors
    """
    if count == 0:
        return []

    # Predefined RGB colors that are visually distinct
    base_colors = [
        (255, 0, 0),  # Red
        (0, 255, 0),  # Green
        (0, 0, 255),  # Blue
        (255, 255, 0),  # Yellow
        (255, 0, 255),  # Magenta
        (0, 255, 255),  # Cyan
        (255, 128, 0),  # Orange
        (128, 0, 255),  # Purple
        (255, 128, 128),  # Pink
        (128, 255, 128),  # Light Green
        (128, 128, 255),  # Light Blue
        (255, 255, 128),  # Light Yellow
        (128, 0, 0),  # Dark Red
        (0, 128, 0),  # Dark Green
        (0, 0, 128),  # Dark Blue
        (128, 128, 0),  # Olive
        (128, 0, 128),  # Dark Magenta
        (0, 128, 128),  # Teal
        (192, 192, 192),  # Silver
        (128, 128, 128),  # Gray
        (255, 192, 203),  # Light Pink
        (255, 165, 0),  # Orange Red
        (255, 20, 147),  # Deep Pink
        (50, 205, 50),  # Lime Green
        (30, 144, 255),  # Dodger Blue
    ]

    colors = []
    for i in range(count):
        if i < len(base_colors):
            # Use predefined colors
            r, g, b = base_colors[i]
        else:
            # Generate additional colors by cycling and modifying
            base_idx = i % len(base_colors)
            cycle = i // len(base_colors)
            r, g, b = base_colors[base_idx]

            # Modify brightness to create variations
            factor = 1.0 - (cycle * 0.15)  # Reduce brightness by 15% each cycle
            factor = max(0.3, factor)  # Don't go too dark

            r = int(r * factor)
            g = int(g * factor)
            b = int(b * factor)

        color = DB.Color(r, g, b)
        colors.append(color)

    return colors


def generate_gradient_colors(count):
    """
    Generate gradient colors from blue to red with better distribution
    Args:
        count (int): Number of gradient colors needed
    Returns:
        list: List of DB.Color objects representing the gradient
    """
    if count <= 1:
        return [DB.Color(255, 0, 0)]

    colors = []
    for i in range(count):
        # Create more distinct gradient from blue to red
        ratio = float(i) / (count - 1)

        # Use HSV color space for better distribution
        red = int(255 * ratio)
        green = int(255 * (1 - abs(2 * ratio - 1)))  # Peak at middle
        blue = int(255 * (1 - ratio))

        colors.append(DB.Color(red, green, blue))

    return colors


def interpolate_color(position):
    """
    Interpolate color based on position (0.0 to 1.0) for smooth gradients

    Args:
        position (float): Position in gradient (0.0 to 1.0)

    Returns:
        DB.Color: Interpolated color
    """
    # Clamp position to valid range
    position = max(0.0, min(1.0, position))

    # Blue to Red gradient with green in middle
    red = int(255 * position)
    green = int(255 * (1 - abs(2 * position - 1)))  # Peak at middle
    blue = int(255 * (1 - position))

    return DB.Color(red, green, blue)


def check_view_compatibility(doc):
    """
    Check if current view is compatible with color overrides

    Args:
        doc: Revit document

    Returns:
        dict: Compatibility status and recommendations
    """
    try:
        active_view = doc.ActiveView

        # Check visual style
        visual_style_param = active_view.get_Parameter(
            DB.BuiltInParameter.MODEL_GRAPHICS_STYLE
        )
        if visual_style_param:
            style_id = visual_style_param.AsInteger()

            # Recommend better visual styles for color visibility
            if style_id in [0, 4]:  # Wireframe or certain realistic modes
                return {
                    "warning": "Current visual style may not show colors well",
                    "recommendation": "Try switching to 'Hidden Line' or 'Shaded' visual style",
                    "current_style_id": style_id,
                }

        return {"status": "ok"}
    except Exception as e:
        logger.debug("Error checking view compatibility: %s", e)
        return {"status": "unknown"}


def hex_to_rgb(hex_color):
    """
    Convert hex color string to RGB tuple

    Args:
        hex_color (str): Hex color string (e.g., "#FF0000" or "FF0000")

    Returns:
        tuple: RGB tuple (r, g, b)
    """
    # Remove # if present
    hex_color = hex_color.lstrip("#")

    # Convert to RGB
    try:
        return tuple(int(hex_color[i : i + 2], 16) for i in (0, 2, 4))
    except (ValueError, IndexError):
        logger.warning("Invalid hex color: %s. Using red as fallback.", hex_color)
        return (255, 0, 0)


def get_parameter_value_safe(element, parameter_name):
    """
    Safely get parameter value from element

    Args:
        element: Revit element
        parameter_name (str): Name of the parameter

    Returns:
        str: Parameter value as string, or "No Value" if not found
    """
    try:
        # Try to get parameter by name
        param = element.LookupParameter(parameter_name)
        if param and param.HasValue:
            if param.StorageType == DB.StorageType.String:
                value = param.AsString()
            elif param.StorageType == DB.StorageType.Integer:
                value = str(param.AsInteger())
            elif param.StorageType == DB.StorageType.Double:
                value = str(round(param.AsDouble(), 2))
            elif param.StorageType == DB.StorageType.ElementId:
                elem_id = param.AsElementId()
                if elem_id and elem_id != DB.ElementId.InvalidElementId:
                    value = str(int(elem_id.Value))
                else:
                    value = "No Value"
            else:
                value = (
                    str(param.AsValueString()) if param.AsValueString() else "No Value"
                )

            return normalize_string(value) if value else "No Value"

        return "No Value"

    except Exception as e:
        logger.debug(
            "Error getting parameter %s from element %s: %s",
            parameter_name,
            get_element_id_value(element),
            e,
        )
        return "No Value"


def get_parameter_value_improved(element, parameter_name):
    """
    Improved parameter value extraction based on the baseline code

    Args:
        element: Revit element
        parameter_name (str): Name of the parameter

    Returns:
        str: Parameter value as string, or "None" if not found
    """
    try:
        # Try to get parameter by name from element
        for param in element.Parameters:
            if param.Definition.Name == parameter_name:
                if not param.HasValue:
                    return "None"

                if param.StorageType == DB.StorageType.Double:
                    return param.AsValueString() or "None"
                elif param.StorageType == DB.StorageType.ElementId:
                    id_val = param.AsElementId()
                    if id_val and id_val != DB.ElementId.InvalidElementId:
                        try:
                            elem = element.Document.GetElement(id_val)
                            if elem and hasattr(elem, "Name"):
                                return elem.Name or "None"
                        except:
                            pass
                    return "None"
                elif param.StorageType == DB.StorageType.Integer:
                    # Handle Yes/No parameters
                    try:
                        if hasattr(param.Definition, "GetDataType"):
                            param_type = param.Definition.GetDataType()
                            if hasattr(DB, "SpecTypeId") and hasattr(
                                DB.SpecTypeId, "Boolean"
                            ):
                                if param_type == DB.SpecTypeId.Boolean.YesNo:
                                    return "True" if param.AsInteger() == 1 else "False"
                        elif hasattr(param.Definition, "ParameterType"):
                            param_type = param.Definition.ParameterType
                            if param_type == DB.ParameterType.YesNo:
                                return "True" if param.AsInteger() == 1 else "False"

                        return param.AsValueString() or str(param.AsInteger())
                    except:
                        return str(param.AsInteger())
                elif param.StorageType == DB.StorageType.String:
                    return param.AsString() or "None"
                else:
                    return param.AsValueString() or "None"

        # Try type parameters if not found in instance
        try:
            element_type = element.Document.GetElement(element.GetTypeId())
            if element_type:
                for param in element_type.Parameters:
                    if param.Definition.Name == parameter_name:
                        if not param.HasValue:
                            return "None"

                        if param.StorageType == DB.StorageType.Double:
                            return param.AsValueString() or "None"
                        elif param.StorageType == DB.StorageType.ElementId:
                            id_val = param.AsElementId()
                            if id_val and id_val != DB.ElementId.InvalidElementId:
                                try:
                                    elem = element.Document.GetElement(id_val)
                                    if elem and hasattr(elem, "Name"):
                                        return elem.Name or "None"
                                except:
                                    pass
                        elif param.StorageType == DB.StorageType.Integer:
                            return param.AsValueString() or str(param.AsInteger())
                        elif param.StorageType == DB.StorageType.String:
                            return param.AsString() or "None"
                        else:
                            return param.AsValueString() or "None"
        except:
            pass

        return "None"

    except Exception as e:
        logger.debug("Error getting parameter %s from element: %s", parameter_name, e)
        return "None"


def clean_parameter_value_for_json(param_value):
    """
    Clean parameter values to be JSON-safe by removing special characters

    Args:
        param_value (str): Raw parameter value

    Returns:
        str: Cleaned parameter value safe for JSON serialization
    """
    if not param_value or param_value == "None":
        return "None"

    try:
        value_str = str(param_value)
        try:
            if value_str.replace(".", "").replace("-", "").replace("+", "").isdigit():
                float_val = float(value_str)
                return "{:.2f}".format(float_val)
        except (ValueError, TypeError):
            pass
        import re

        cleaned = re.sub(r"[^\x20-\x7E]", "", value_str)

        cleaned = re.sub(r"[^\w\s\.\-\(\)\/\+\=\:\,]", "", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        return cleaned if cleaned else "None"
    except Exception as e:
        logger.debug("Error cleaning parameter value: %s", e)
        return "None"


def get_parameter_value_json_safe(element, parameter_name):
    """
    JSON-safe parameter value extraction - updated to use sorting-optimized method

    Args:
        element: Revit element
        parameter_name (str): Name of the parameter

    Returns:
        str: JSON-safe parameter value as string, or "None" if not found
    """
    try:
        raw_value, display_value = get_parameter_value_for_sorting(
            element, parameter_name
        )
        return clean_parameter_value_for_json(display_value)
    except Exception as e:
        logger.error("Error getting parameter %s from element: %s", parameter_name, e)
        return "None"


def safe_color_to_hex(color):
    try:
        r = max(0, min(255, int(color.Red)))
        g = max(0, min(255, int(color.Green)))
        b = max(0, min(255, int(color.Blue)))
        return "#{:02x}{:02x}{:02x}".format(r, g, b)
    except Exception:
        return "#FF0000"


def solid_fill_pattern_id(doc):
    """
    Get the solid fill pattern ID for the document

    Args:
        doc: Revit document

    Returns:
        DB.ElementId: Solid fill pattern ID, or None if not found
    """
    try:
        # Get all fill patterns
        collector = DB.FilteredElementCollector(doc).OfClass(DB.FillPatternElement)

        for pattern_elem in collector:
            pattern = pattern_elem.GetFillPattern()
            if pattern.IsSolidFill:
                return pattern_elem.Id

        return None
    except Exception:
        return None


def generate_random_color():
    """
    Generate a random RGB color

    Returns:
        tuple: RGB tuple (r, g, b)
    """
    return (random.randint(0, 255), random.randint(0, 255), random.randint(0, 255))


def safe_float_conversion(value_str):
    """
    Safely convert a string value to float for sorting, based on script.py approach

    Args:
        value_str (str): String value to convert

    Returns:
        float: Converted value or infinity for non-numeric values
    """
    if not value_str or value_str == "None":
        return float("inf")  # Put "None" values at the end

    try:
        # Handle unit suffixes like in script.py
        clean_value = str(value_str).strip()

        # Check if it has unit suffix (non-digit characters at the end)
        suffix_index = 0
        for char in reversed(clean_value):
            if char.isdigit() or char == "." or char == "-" or char == "+":
                break
            suffix_index += 1

        if suffix_index > 0:
            # Remove unit suffix
            numeric_part = clean_value[:-suffix_index]
        else:
            numeric_part = clean_value

        return float(numeric_part)
    except (ValueError, TypeError):
        return float("inf")  # Non-numeric values go to end


def get_parameter_value_for_sorting(element, parameter_name):
    """
    Get parameter value optimized for numeric sorting, following script.py pattern

    Args:
        element: Revit element
        parameter_name (str): Name of the parameter

    Returns:
        tuple: (raw_value, display_value) for sorting and display
    """
    try:
        # Try instance parameters first
        for param in element.Parameters:
            if param.Definition.Name == parameter_name:
                if not param.HasValue:
                    return ("None", "None")

                if param.StorageType == DB.StorageType.Double:
                    # Get both raw and display values
                    raw_value = param.AsDouble()
                    display_value = param.AsValueString() or str(raw_value)
                    return (raw_value, display_value)

                elif param.StorageType == DB.StorageType.Integer:
                    # Handle Yes/No and regular integers
                    try:
                        if hasattr(param.Definition, "GetDataType"):
                            param_type = param.Definition.GetDataType()
                            if hasattr(DB, "SpecTypeId") and hasattr(
                                DB.SpecTypeId, "Boolean"
                            ):
                                if param_type == DB.SpecTypeId.Boolean.YesNo:
                                    bool_val = (
                                        "True" if param.AsInteger() == 1 else "False"
                                    )
                                    return (bool_val, bool_val)
                        elif hasattr(param.Definition, "ParameterType"):
                            param_type = param.Definition.ParameterType
                            if param_type == DB.ParameterType.YesNo:
                                bool_val = "True" if param.AsInteger() == 1 else "False"
                                return (bool_val, bool_val)

                        int_value = param.AsInteger()
                        display_value = param.AsValueString() or str(int_value)
                        return (int_value, display_value)
                    except:
                        int_value = param.AsInteger()
                        return (int_value, str(int_value))

                elif param.StorageType == DB.StorageType.String:
                    string_value = param.AsString() or "None"
                    return (string_value, string_value)

                elif param.StorageType == DB.StorageType.ElementId:
                    id_val = param.AsElementId()
                    if id_val and id_val != DB.ElementId.InvalidElementId:
                        try:
                            elem = element.Document.GetElement(id_val)
                            if elem and hasattr(elem, "Name"):
                                elem_name = elem.Name or "None"
                                return (elem_name, elem_name)
                        except:
                            pass
                    return ("None", "None")
                else:
                    value_str = param.AsValueString() or "None"
                    return (value_str, value_str)

        # Try type parameters if not found in instance
        try:
            element_type = element.Document.GetElement(element.GetTypeId())
            if element_type:
                for param in element_type.Parameters:
                    if param.Definition.Name == parameter_name:
                        if not param.HasValue:
                            return ("None", "None")

                        if param.StorageType == DB.StorageType.Double:
                            raw_value = param.AsDouble()
                            display_value = param.AsValueString() or str(raw_value)
                            return (raw_value, display_value)

                        elif param.StorageType == DB.StorageType.Integer:
                            try:
                                if hasattr(param.Definition, "GetDataType"):
                                    param_type = param.Definition.GetDataType()
                                    if hasattr(DB, "SpecTypeId") and hasattr(
                                        DB.SpecTypeId, "Boolean"
                                    ):
                                        if param_type == DB.SpecTypeId.Boolean.YesNo:
                                            bool_val = (
                                                "True"
                                                if param.AsInteger() == 1
                                                else "False"
                                            )
                                            return (bool_val, bool_val)
                                elif hasattr(param.Definition, "ParameterType"):
                                    param_type = param.Definition.ParameterType
                                    if param_type == DB.ParameterType.YesNo:
                                        bool_val = (
                                            "True"
                                            if param.AsInteger() == 1
                                            else "False"
                                        )
                                        return (bool_val, bool_val)

                                int_value = param.AsInteger()
                                display_value = param.AsValueString() or str(int_value)
                                return (int_value, display_value)
                            except:
                                int_value = param.AsInteger()
                                return (int_value, str(int_value))

                        elif param.StorageType == DB.StorageType.String:
                            string_value = param.AsString() or "None"
                            return (string_value, string_value)

                        elif param.StorageType == DB.StorageType.ElementId:
                            id_val = param.AsElementId()
                            if id_val and id_val != DB.ElementId.InvalidElementId:
                                try:
                                    elem = element.Document.GetElement(id_val)
                                    if elem and hasattr(elem, "Name"):
                                        elem_name = elem.Name or "None"
                                        return (elem_name, elem_name)
                                except:
                                    pass
                            return ("None", "None")
                        else:
                            value_str = param.AsValueString() or "None"
                            return (value_str, value_str)
        except:
            pass

        return ("None", "None")

    except Exception as e:
        logger.debug("Error getting parameter %s from element: %s", parameter_name, e)
        return ("None", "None")


def color_elements_by_parameter(
    doc, category_name, parameter_name, use_gradient=False, custom_colors=None
):
    """
    Color elements in a category based on parameter values with proper gradient support

    Args:
        doc: Revit document
        category_name (str): Name of the category to color
        parameter_name (str): Name of the parameter to use for coloring
        use_gradient (bool): Whether to use gradient coloring
        custom_colors (list): Optional list of custom hex colors

    Returns:
        dict: Results of the coloring operation
    """
    try:
        # Find the category
        categories = doc.Settings.Categories
        target_category = None

        for cat in categories:
            if cat.Name == category_name:
                target_category = cat
                break

        if not target_category:
            return {
                "status": "error",
                "message": "Category '{}' not found".format(category_name),
            }

        # Get elements from the category
        collector = (
            DB.FilteredElementCollector(doc)
            .OfCategoryId(target_category.Id)
            .WhereElementIsNotElementType()
        )
        elements = collector.ToElements()

        if not elements:
            return {
                "status": "error",
                "message": "No elements found in category '{}'".format(category_name),
            }

        # Group elements by parameter value using improved method
        parameter_groups = defaultdict(list)
        value_data = {}  # Store both raw and display values

        for element in elements:
            raw_value, display_value = get_parameter_value_for_sorting(
                element, parameter_name
            )

            # Sanitize display_value for JSON safety
            display_value = normalize_string(display_value)

            # Use display value as key for grouping
            parameter_groups[display_value].append(element)

            # Store raw value for sorting
            if display_value not in value_data:
                value_data[display_value] = raw_value

        # Sort values properly based on their type and content
        def sort_key(display_value):
            """Advanced sorting key that handles different data types"""
            raw_value = value_data[display_value]

            # Handle None values
            if display_value == "None" or raw_value == "None":
                return (2, 0)  # Put None at the end

            # Handle boolean values
            if display_value in ["True", "False"]:
                return (1, 0 if display_value == "False" else 1)

            # Handle numeric values (int or float)
            if isinstance(raw_value, (int, float)):
                return (0, raw_value)

            # Handle string values that might contain numbers
            try:
                numeric_sort_value = safe_float_conversion(display_value)
                if numeric_sort_value != float("inf"):
                    return (0, numeric_sort_value)
            except:
                pass

            # Fallback to string sorting
            return (1.5, str(display_value).lower())

        # Check for numeric gradient mode
        is_numeric_gradient = use_gradient and any(
            param_name.lower() in parameter_name.lower()
            for param_name in [
                "length",
                "longueur",
                "area",
                "volume",
                "height",
                "width",
                "thickness",
            ]
        )

        if is_numeric_gradient:
            # For numeric parameters in gradient mode, treat each unique value individually
            # but still group elements with identical values
            unique_values = sorted(parameter_groups.keys(), key=sort_key)
            value_count = len(unique_values)

            # Create mapping from value to position in gradient
            value_positions = {}
            numeric_values = []

            for display_value in unique_values:
                raw_value = value_data[display_value]
                if isinstance(raw_value, (int, float)):
                    numeric_values.append(raw_value)

            if numeric_values:
                min_val = min(numeric_values)
                max_val = max(numeric_values)

                for display_value in unique_values:
                    raw_value = value_data[display_value]
                    if isinstance(raw_value, (int, float)) and max_val != min_val:
                        position = (raw_value - min_val) / (max_val - min_val)
                        value_positions[display_value] = position
                    else:
                        value_positions[display_value] = 0.5
            else:
                # Fallback if no numeric values
                for i, display_value in enumerate(unique_values):
                    value_positions[display_value] = float(i) / max(
                        1, len(unique_values) - 1
                    )
        else:
            unique_values = sorted(parameter_groups.keys(), key=sort_key)
            value_count = len(unique_values)

        logger.info(
            "Sorted values for gradient: %s", unique_values[:10]
        )  # Log first 10 for debugging

        # Generate colors based on the sorted order
        if custom_colors:
            # Use custom colors
            colors = []
            for i, hex_color in enumerate(custom_colors):
                if i >= value_count:
                    break
                rgb = hex_to_rgb(hex_color)
                colors.append(DB.Color(rgb[0], rgb[1], rgb[2]))

            # Fill remaining with distinct colors if needed
            if len(colors) < value_count:
                remaining_count = value_count - len(colors)
                additional_colors = generate_distinct_colors(remaining_count)
                colors.extend(additional_colors)

        elif use_gradient and is_numeric_gradient:
            # Use interpolated colors for numeric gradients
            colors = []
            for param_value in unique_values:
                position = value_positions.get(param_value, 0.5)
                color = interpolate_color(position)
                colors.append(color)
        elif use_gradient:
            # Generate proper gradient colors for non-numeric
            colors = generate_gradient_colors(value_count)
        else:
            # Use distinct colors
            colors = generate_distinct_colors(value_count)

        # Apply colors to elements
        color_assignments = {}
        elements_colored = 0
        solid_fill_id = solid_fill_pattern_id(doc)

        with DB.Transaction(doc, "Color Elements by Parameter") as t:
            t.Start()

            # Ensure we have enough colors
            if len(colors) < value_count:
                logger.warning(
                    "Not enough colors generated. Expected %d, got %d",
                    value_count,
                    len(colors),
                )
                additional_needed = value_count - len(colors)
                additional_colors = generate_distinct_colors(additional_needed)
                colors.extend(additional_colors)

            for i, param_value in enumerate(unique_values):
                group_elements = parameter_groups[param_value]

                # Get color for this group
                if i < len(colors):
                    color = colors[i]
                else:
                    logger.warning(
                        "Color index out of bounds for value %s at index %d",
                        param_value,
                        i,
                    )
                    rgb = generate_random_color()
                    color = DB.Color(rgb[0], rgb[1], rgb[2])

                color_assignments[param_value] = {
                    "color": safe_color_to_hex(color),
                    "element_count": len(group_elements),
                    "sort_index": i,  # Add sort index for debugging
                }

                # Apply color override to each element with improved settings
                override_settings = DB.OverrideGraphicSettings()
                override_settings.SetProjectionLineColor(color)
                override_settings.SetSurfaceForegroundPatternColor(color)
                override_settings.SetCutForegroundPatternColor(color)
                override_settings.SetCutLineColor(color)
                override_settings.SetProjectionLineWeight(3)  # Make lines more visible

                if solid_fill_id is not None:
                    override_settings.SetSurfaceForegroundPatternId(solid_fill_id)
                    override_settings.SetCutForegroundPatternId(solid_fill_id)

                for element in group_elements:
                    try:
                        # Apply to active view first (CRITICAL FIX!)
                        active_view = doc.ActiveView
                        active_view.SetElementOverrides(element.Id, override_settings)
                        elements_colored += 1

                        # Optionally apply to other views of same type
                        try:
                            if hasattr(active_view, "ViewType"):
                                view_type = active_view.ViewType
                                other_views = (
                                    DB.FilteredElementCollector(doc)
                                    .OfClass(DB.View)
                                    .WhereElementIsNotElementType()
                                )
                                for view in other_views:
                                    if (
                                        not view.IsTemplate
                                        and hasattr(view, "ViewType")
                                        and view.ViewType == view_type
                                        and view.Id != active_view.Id
                                    ):
                                        view.SetElementOverrides(
                                            element.Id, override_settings
                                        )
                        except Exception:
                            pass  # Don't fail if we can't apply to other views

                    except Exception as e:
                        logger.warning(
                            "Failed to color element %s: %s",
                            get_element_id_value(element),
                            e,
                        )

            t.Commit()

        result = {
            "status": "success",
            "message": "Successfully colored {} elements in {} color groups".format(
                elements_colored, value_count
            ),
            "category": category_name,
            "parameter": parameter_name,
            "color_assignments": color_assignments,
            "statistics": {
                "total_elements": len(elements),
                "elements_colored": elements_colored,
                "unique_parameter_values": value_count,
                "use_gradient": use_gradient,
                "sorted_values": unique_values,  # Include sorted values for debugging
            },
        }

        # Add view compatibility warning if needed
        view_check = check_view_compatibility(doc)
        if view_check.get("warning"):
            result["view_warning"] = view_check

        return result

    except Exception as e:
        logger.error("Error in color_elements_by_parameter: %s", e)
        return {
            "status": "error",
            "message": "Failed to color elements: {}".format(str(e)),
        }


def clear_element_colors(doc, category_name):
    """
    Clear color overrides for elements in a category

    Args:
        doc: Revit document
        category_name (str): Name of the category to clear colors from

    Returns:
        dict: Results of the clear operation
    """
    try:
        # Find the category
        categories = doc.Settings.Categories
        target_category = None

        for cat in categories:
            if cat.Name == category_name:
                target_category = cat
                break

        if not target_category:
            return {
                "status": "error",
                "message": "Category '{}' not found".format(category_name),
            }

        # Get elements from the category
        collector = (
            DB.FilteredElementCollector(doc)
            .OfCategoryId(target_category.Id)
            .WhereElementIsNotElementType()
        )
        elements = collector.ToElements()

        if not elements:
            return {
                "status": "warning",
                "message": "No elements found in category '{}'".format(category_name),
            }

        elements_cleared = 0

        # Get active view for clearing overrides
        active_view = doc.ActiveView

        with DB.Transaction(doc, "Clear Element Colors") as t:
            t.Start()

            # Clear overrides for each element in active view
            for element in elements:
                try:
                    empty_override = DB.OverrideGraphicSettings()
                    active_view.SetElementOverrides(element.Id, empty_override)
                    elements_cleared += 1

                    # Optionally clear from other views of same type
                    try:
                        if hasattr(active_view, "ViewType"):
                            view_type = active_view.ViewType
                            other_views = (
                                DB.FilteredElementCollector(doc)
                                .OfClass(DB.View)
                                .WhereElementIsNotElementType()
                            )
                            for view in other_views:
                                if (
                                    not view.IsTemplate
                                    and hasattr(view, "ViewType")
                                    and view.ViewType == view_type
                                    and view.Id != active_view.Id
                                ):
                                    view.SetElementOverrides(element.Id, empty_override)
                    except Exception:
                        pass  # Don't fail if we can't clear from other views

                except Exception as e:
                    logger.warning(
                        "Failed to clear colors for element %s: %s",
                        get_element_id_value(element),
                        e,
                    )

            t.Commit()

        return {
            "status": "success",
            "message": "Successfully cleared color overrides for {} elements".format(
                elements_cleared
            ),
            "category": category_name,
            "elements_processed": elements_cleared,
        }

    except Exception as e:
        logger.error("Error in clear_element_colors: %s", e)
        return {
            "status": "error",
            "message": "Failed to clear colors: {}".format(str(e)),
        }


def list_category_parameters(doc, category_name):
    """
    Get available parameters for elements in a category

    Args:
        doc: Revit document
        category_name (str): Name of the category to check parameters for

    Returns:
        dict: List of available parameters with their types
    """
    try:
        # Find the category
        categories = doc.Settings.Categories
        target_category = None

        for cat in categories:
            if cat.Name == category_name:
                target_category = cat
                break

        if not target_category:
            return {
                "status": "error",
                "message": "Category '{}' not found".format(category_name),
            }

        # Get a sample element from the category to check parameters
        collector = (
            DB.FilteredElementCollector(doc)
            .OfCategoryId(target_category.Id)
            .WhereElementIsNotElementType()
        )
        elements = collector.ToElements()

        if not elements:
            return {
                "status": "error",
                "message": "No elements found in category '{}'".format(category_name),
            }

        # Get parameters from the first element
        sample_element = elements[0]
        parameters = []

        # Get all parameters
        for param in sample_element.Parameters:
            try:
                param_name = normalize_string(param.Definition.Name)
                storage_type = str(param.StorageType)
                has_value = param.HasValue

                # Get a sample value if available (JSON-safe)
                sample_value = "N/A"
                if has_value:
                    sample_value = get_parameter_value_json_safe(
                        sample_element, param_name
                    )

                parameters.append(
                    {
                        "name": param_name,
                        "storage_type": storage_type,
                        "has_value": has_value,
                        "sample_value": sample_value,
                    }
                )

            except Exception as e:
                logger.debug("Error processing parameter: %s", e)
                continue

        # Sort parameters by name for easier reading
        parameters.sort(key=lambda x: x["name"])

        return {
            "status": "success",
            "category": category_name,
            "parameter_count": len(parameters),
            "parameters": parameters,
        }

    except Exception as e:
        logger.error("Error in list_category_parameters: %s", e)
        return {
            "status": "error",
            "message": "Failed to list parameters: {}".format(str(e)),
        }


def register_color_routes(api):
    """Register color-related routes with the API"""

    @api.route("/color_splash/", methods=["POST"])
    def color_splash(doc, request):
        """
        Color elements in a category based on parameter values

        Expected JSON payload:
        {
            "category_name": "Walls",
            "parameter_name": "Mark",
            "use_gradient": false,
            "custom_colors": ["#FF0000", "#00FF00", "#0000FF"]  // optional
        }
        """
        try:
            data = (
                json.loads(request.data)
                if isinstance(request.data, str)
                else request.data
            )

            category_name = data.get("category_name")
            parameter_name = data.get("parameter_name")
            use_gradient = data.get("use_gradient", False)
            custom_colors = data.get("custom_colors", None)

            if not category_name or not parameter_name:
                return routes.make_response(
                    data={"error": "category_name and parameter_name are required"},
                    status=400,
                )

            result = color_elements_by_parameter(
                doc, category_name, parameter_name, use_gradient, custom_colors
            )

            return routes.make_response(data=result)

        except Exception as e:
            logger.error("Error in color_splash route: %s", e)
            return routes.make_response(data={"error": str(e)}, status=500)

    @api.route("/clear_colors/", methods=["POST"])
    def clear_colors(doc, request):
        """
        Clear color overrides for elements in a category

        Expected JSON payload:
        {
            "category_name": "Walls"
        }
        """
        try:
            data = (
                json.loads(request.data)
                if isinstance(request.data, str)
                else request.data
            )

            category_name = data.get("category_name")

            if not category_name:
                return routes.make_response(
                    data={"error": "category_name is required"}, status=400
                )

            result = clear_element_colors(doc, category_name)

            return routes.make_response(data=result)

        except Exception as e:
            logger.error("Error in clear_colors route: %s", e)
            return routes.make_response(data={"error": str(e)}, status=500)

    @api.route("/list_category_parameters/", methods=["POST"])
    def list_parameters(doc, request):
        """
        Get available parameters for elements in a category

        Expected JSON payload:
        {
            "category_name": "Walls"
        }
        """
        try:
            data = (
                json.loads(request.data)
                if isinstance(request.data, str)
                else request.data
            )

            category_name = data.get("category_name")

            if not category_name:
                return routes.make_response(
                    data={"error": "category_name is required"}, status=400
                )

            result = list_category_parameters(doc, category_name)

            return routes.make_response(data=result)

        except Exception as e:
            logger.error("Error in list_category_parameters route: %s", e)
            return routes.make_response(data={"error": str(e)}, status=500)


def get_numeric_parameter_raw_value(param):
    """
    Get the raw numeric value from a parameter, bypassing display formatting

    Args:
        param: Revit parameter object

    Returns:
        float: Raw numeric value, or None if not available
    """
    try:
        if param.StorageType == DB.StorageType.Double:
            return param.AsDouble()
        elif param.StorageType == DB.StorageType.Integer:
            return float(param.AsInteger())
        else:
            return None
    except Exception:
        return None


def format_numeric_for_json(value):
    """
    Format a numeric value for JSON-safe serialization

    Args:
        value (float): Numeric value to format

    Returns:
        str: JSON-safe string representation
    """
    try:
        if value is None:
            return "None"

        # Handle very small values as zero
        if abs(value) < 1e-10:
            return "0.000"

        # Handle very large values
        if abs(value) > 1e10:
            return "{:.2e}".format(value)

        # Normal values - use reasonable precision
        return "{:.3f}".format(value)

    except Exception:
        return "None"
