# -*- coding: UTF-8 -*-
"""
Analysis Module for Revit MCP
Handles element filtering, room data, material quantities, and model statistics
"""

from utils import get_element_name, normalize_string, get_element_id_value
from pyrevit import routes, revit, DB
import json
import traceback
import logging

logger = logging.getLogger(__name__)

MM_TO_FEET = 1.0 / 304.8
SQFT_TO_SQM = 0.0929
CUFT_TO_CUM = 0.0283168


def register_analysis_routes(api):
    """Register all analysis routes with the API"""

    @api.route("/ai_filter/", methods=["POST"])
    def ai_element_filter_handler(doc, request):
        """Filter and find Revit elements by various criteria."""
        try:
            if not doc:
                return routes.make_response(
                    data={"error": "No active Revit document"}, status=503
                )

            data = {}
            if request and request.data:
                data = json.loads(request.data) if isinstance(request.data, str) else request.data

            category = data.get("category")
            type_name = data.get("type_name")
            visible_in_view = data.get("visible_in_view", False)
            bbox_min = data.get("bounding_box_min")
            bbox_max = data.get("bounding_box_max")
            max_elements = data.get("max_elements", 50)

            # Start with collector
            if visible_in_view:
                active_view = doc.ActiveView
                if not active_view:
                    return routes.make_response(
                        data={"error": "No active view for visibility filter"}, status=400
                    )
                # BUG-008: Skip view types that don't support element collection
                skip_types = [DB.ViewType.Schedule, DB.ViewType.Internal, DB.ViewType.DrawingSheet]
                if active_view.ViewType in skip_types:
                    return routes.make_response(
                        data={"error": "Current view type '{}' does not support element filtering — switch to a plan, section, or 3D view".format(active_view.ViewType)},
                        status=400,
                    )
                collector = DB.FilteredElementCollector(doc, active_view.Id)
            else:
                collector = DB.FilteredElementCollector(doc)

            # Apply category filter
            if category:
                try:
                    bic = getattr(DB.BuiltInCategory, category)
                    collector = collector.OfCategory(bic)
                except AttributeError:
                    return routes.make_response(
                        data={"error": "Invalid category: {}. Use BuiltInCategory names like OST_Walls, OST_Doors".format(category)},
                        status=400,
                    )

            collector = collector.WhereElementIsNotElementType()

            # Apply bounding box filter
            if bbox_min and bbox_max:
                try:
                    min_pt = DB.XYZ(
                        float(bbox_min.get("x", 0)) * MM_TO_FEET,
                        float(bbox_min.get("y", 0)) * MM_TO_FEET,
                        float(bbox_min.get("z", 0)) * MM_TO_FEET,
                    )
                    max_pt = DB.XYZ(
                        float(bbox_max.get("x", 0)) * MM_TO_FEET,
                        float(bbox_max.get("y", 0)) * MM_TO_FEET,
                        float(bbox_max.get("z", 0)) * MM_TO_FEET,
                    )
                    outline = DB.Outline(min_pt, max_pt)
                    bb_filter = DB.BoundingBoxIntersectsFilter(outline)
                    collector = collector.WherePasses(bb_filter)
                except Exception as bb_err:
                    logger.warning("Bounding box filter failed: {}".format(str(bb_err)))

            all_elements = collector.ToElements()

            # Apply type name filter (partial match)
            elements = []
            for elem in all_elements:
                if len(elements) >= max_elements:
                    break

                if type_name:
                    try:
                        elem_type_name = get_element_name(elem)
                        if type_name.lower() not in elem_type_name.lower():
                            # Also check the type element
                            type_id = elem.GetTypeId()
                            if type_id and type_id != DB.ElementId.InvalidElementId:
                                type_elem = doc.GetElement(type_id)
                                if type_elem:
                                    full_type = get_element_name(type_elem)
                                    if type_name.lower() not in full_type.lower():
                                        continue
                                else:
                                    continue
                            else:
                                continue
                    except Exception:
                        continue

                # Build element info
                elem_info = {
                    "id": get_element_id_value(elem),
                    "category": elem.Category.Name if elem.Category else "Unknown",
                    "type": get_element_name(elem),
                }

                # Get level
                try:
                    level_id = elem.LevelId
                    if level_id and level_id != DB.ElementId.InvalidElementId:
                        level = doc.GetElement(level_id)
                        if level:
                            elem_info["level"] = get_element_name(level)
                except Exception:
                    pass

                # Get dimensions if available
                try:
                    length_param = elem.LookupParameter("Length")
                    if length_param and length_param.HasValue:
                        elem_info["length_mm"] = round(length_param.AsDouble() / MM_TO_FEET, 0)
                except Exception:
                    pass

                try:
                    height_param = elem.LookupParameter("Height")
                    if not height_param:
                        height_param = elem.LookupParameter("Unconnected Height")
                    if height_param and height_param.HasValue:
                        elem_info["height_mm"] = round(height_param.AsDouble() / MM_TO_FEET, 0)
                except Exception:
                    pass

                elements.append(elem_info)

            total_matched = len(all_elements)
            count = len(elements)

            cat_label = category.replace("OST_", "").lower() if category else "element"
            message = "Found {} {}{} matching filters".format(
                total_matched,
                cat_label,
                "s" if total_matched != 1 else "",
            )

            return routes.make_response(
                data={
                    "status": "success",
                    "elements": elements,
                    "count": count,
                    "total_matched": total_matched,
                    "message": message,
                }
            )

        except Exception as e:
            logger.error("Failed to filter elements: {}".format(str(e)))
            error_trace = traceback.format_exc()
            return routes.make_response(
                data={"error": str(e), "traceback": error_trace}, status=500
            )

    @api.route("/room_data/", methods=["GET"])
    def export_room_data_handler(doc):
        """Export data for all rooms in the model."""
        try:
            if not doc:
                return routes.make_response(
                    data={"error": "No active Revit document"}, status=503
                )

            rooms_collector = (
                DB.FilteredElementCollector(doc)
                .OfCategory(DB.BuiltInCategory.OST_Rooms)
                .WhereElementIsNotElementType()
                .ToElements()
            )

            rooms = []
            for room in rooms_collector:
                try:
                    # Skip unplaced rooms
                    if not room.Location:
                        continue

                    room_info = {
                        "id": get_element_id_value(room),
                        "name": "",
                        "number": "",
                        "level": "",
                        "area_sqm": 0,
                        "perimeter_mm": 0,
                        "department": "",
                    }

                    # Get name
                    try:
                        name_param = room.get_Parameter(DB.BuiltInParameter.ROOM_NAME)
                        if name_param:
                            room_info["name"] = normalize_string(name_param.AsString() or "")
                    except Exception:
                        room_info["name"] = get_element_name(room)

                    # Get number
                    try:
                        number_param = room.get_Parameter(DB.BuiltInParameter.ROOM_NUMBER)
                        if number_param:
                            room_info["number"] = normalize_string(number_param.AsString() or "")
                    except Exception:
                        pass

                    # Get level
                    try:
                        level_id = room.LevelId
                        if level_id and level_id != DB.ElementId.InvalidElementId:
                            level = doc.GetElement(level_id)
                            if level:
                                room_info["level"] = get_element_name(level)
                    except Exception:
                        pass

                    # Get area (convert sq feet to sq meters)
                    try:
                        area_param = room.get_Parameter(DB.BuiltInParameter.ROOM_AREA)
                        if area_param and area_param.HasValue:
                            room_info["area_sqm"] = round(area_param.AsDouble() * SQFT_TO_SQM, 2)
                    except Exception:
                        pass

                    # Get perimeter (convert feet to mm)
                    try:
                        perim_param = room.get_Parameter(DB.BuiltInParameter.ROOM_PERIMETER)
                        if perim_param and perim_param.HasValue:
                            room_info["perimeter_mm"] = round(perim_param.AsDouble() / MM_TO_FEET, 0)
                    except Exception:
                        pass

                    # Get department
                    try:
                        dept_param = room.get_Parameter(DB.BuiltInParameter.ROOM_DEPARTMENT)
                        if dept_param:
                            room_info["department"] = normalize_string(dept_param.AsString() or "")
                    except Exception:
                        pass

                    rooms.append(room_info)

                except Exception as room_err:
                    logger.warning("Could not process room: {}".format(str(room_err)))
                    continue

            count = len(rooms)
            message = "Exported data for {} room{}".format(
                count,
                "s" if count != 1 else ""
            )

            return routes.make_response(
                data={
                    "status": "success",
                    "rooms": rooms,
                    "count": count,
                    "message": message,
                }
            )

        except Exception as e:
            logger.error("Failed to export room data: {}".format(str(e)))
            error_trace = traceback.format_exc()
            return routes.make_response(
                data={"error": str(e), "traceback": error_trace}, status=500
            )

    @api.route("/material_quantities/", methods=["POST"])
    def get_material_quantities_handler(doc, request):
        """Get material quantities from the model."""
        try:
            if not doc:
                return routes.make_response(
                    data={"error": "No active Revit document"}, status=503
                )

            data = {}
            if request and request.data:
                data = json.loads(request.data) if isinstance(request.data, str) else request.data

            categories_filter = data.get("categories")

            # Determine which categories to scan
            target_categories = []
            if categories_filter:
                for cat_str in categories_filter:
                    try:
                        bic = getattr(DB.BuiltInCategory, cat_str)
                        target_categories.append(bic)
                    except AttributeError:
                        logger.warning("Invalid category: {}".format(cat_str))
            else:
                # Default categories with materials
                target_categories = [
                    DB.BuiltInCategory.OST_Walls,
                    DB.BuiltInCategory.OST_Floors,
                    DB.BuiltInCategory.OST_Roofs,
                    DB.BuiltInCategory.OST_Ceilings,
                    DB.BuiltInCategory.OST_StructuralColumns,
                    DB.BuiltInCategory.OST_StructuralFraming,
                ]

            # Aggregate materials
            material_data = {}  # material_name -> {area, volume, count}

            for bic in target_categories:
                try:
                    elements = (
                        DB.FilteredElementCollector(doc)
                        .OfCategory(bic)
                        .WhereElementIsNotElementType()
                        .ToElements()
                    )

                    for elem in elements:
                        try:
                            mat_ids = elem.GetMaterialIds(False)
                            if not mat_ids:
                                continue

                            for mat_id in mat_ids:
                                mat = doc.GetElement(mat_id)
                                if not mat:
                                    continue

                                mat_name = get_element_name(mat)
                                if not mat_name:
                                    mat_name = "Unknown Material"

                                if mat_name not in material_data:
                                    material_data[mat_name] = {
                                        "area_sqft": 0.0,
                                        "volume_cuft": 0.0,
                                        "element_count": 0,
                                    }

                                # Get material area
                                try:
                                    area = elem.GetMaterialArea(mat_id, False)
                                    material_data[mat_name]["area_sqft"] += area
                                except Exception:
                                    pass

                                # Get material volume
                                try:
                                    volume = elem.GetMaterialVolume(mat_id)
                                    material_data[mat_name]["volume_cuft"] += volume
                                except Exception:
                                    pass

                                material_data[mat_name]["element_count"] += 1

                        except Exception:
                            continue

                except Exception as cat_err:
                    logger.warning("Could not process category: {}".format(str(cat_err)))

            # Convert to response format
            materials = []
            for name, data_vals in sorted(material_data.items()):
                materials.append({
                    "name": name,
                    "area_sqm": round(data_vals["area_sqft"] * SQFT_TO_SQM, 2),
                    "volume_cum": round(data_vals["volume_cuft"] * CUFT_TO_CUM, 3),
                    "element_count": data_vals["element_count"],
                })

            total = len(materials)
            message = "Material quantities from {} material{} across all categories".format(
                total,
                "s" if total != 1 else ""
            )

            return routes.make_response(
                data={
                    "status": "success",
                    "materials": materials,
                    "total_materials": total,
                    "message": message,
                }
            )

        except Exception as e:
            logger.error("Failed to get material quantities: {}".format(str(e)))
            error_trace = traceback.format_exc()
            return routes.make_response(
                data={"error": str(e), "traceback": error_trace}, status=500
            )

    @api.route("/model_statistics/", methods=["GET"])
    def analyze_model_statistics_handler(doc):
        """Analyze model and return element counts by category."""
        try:
            if not doc:
                return routes.make_response(
                    data={"error": "No active Revit document"}, status=503
                )

            # Get all model elements (exclude types, views, annotations where possible)
            all_elements = (
                DB.FilteredElementCollector(doc)
                .WhereElementIsNotElementType()
                .ToElements()
            )

            category_counts = {}
            total = 0

            for elem in all_elements:
                try:
                    if not elem.Category:
                        continue

                    cat_name = elem.Category.Name
                    if not cat_name:
                        continue

                    # Skip non-model categories
                    try:
                        cat_type = elem.Category.CategoryType
                        if cat_type != DB.CategoryType.Model:
                            continue
                    except Exception:
                        pass

                    if cat_name not in category_counts:
                        category_counts[cat_name] = 0

                    category_counts[cat_name] += 1
                    total += 1

                except Exception:
                    continue

            # Sort by count descending
            statistics = []
            for name, count in sorted(category_counts.items(), key=lambda x: -x[1]):
                statistics.append({
                    "category": name,
                    "count": count,
                })

            total_categories = len(statistics)
            message = "Model contains {} element{} across {} categor{}".format(
                total,
                "s" if total != 1 else "",
                total_categories,
                "ies" if total_categories != 1 else "y",
            )

            return routes.make_response(
                data={
                    "status": "success",
                    "statistics": statistics,
                    "total_elements": total,
                    "total_categories": total_categories,
                    "message": message,
                }
            )

        except Exception as e:
            logger.error("Failed to analyze model statistics: {}".format(str(e)))
            error_trace = traceback.format_exc()
            return routes.make_response(
                data={"error": str(e), "traceback": error_trace}, status=500
            )

    logger.info("Analysis routes registered successfully")
