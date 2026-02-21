# -*- coding: UTF-8 -*-
"""
Building Module for Revit MCP
Handles creation of line-based elements (walls, beams), surface-based
elements (floors, roofs, ceilings), and levels.
"""

from utils import get_element_name, get_element_id_value
from pyrevit import routes, revit, DB
from System.Collections.Generic import List
import json
import traceback
import logging

logger = logging.getLogger(__name__)


def register_building_routes(api):
    """Register all building creation routes with the API"""

    @api.route("/create_line/", methods=["POST"])
    def create_line_based(doc, request):
        """
        Create line-based elements (walls, beams) in the Revit model.
        Supports batch creation via elements array.
        """
        try:
            if not doc:
                return routes.make_response(
                    data={"error": "No active Revit document — open a project in Revit 2026"},
                    status=503,
                )

            data = json.loads(request.data) if isinstance(request.data, str) else request.data
            elements = data.get("elements", [])

            if not elements:
                return routes.make_response(
                    data={"error": "No elements provided — pass an array of element definitions"},
                    status=400,
                )

            # Collect all levels and wall/beam types once for performance
            all_levels = (
                DB.FilteredElementCollector(doc)
                .OfCategory(DB.BuiltInCategory.OST_Levels)
                .WhereElementIsNotElementType()
                .ToElements()
            )
            level_map = {}
            for lv in all_levels:
                try:
                    level_map[get_element_name(lv)] = lv
                except Exception:
                    continue

            if not level_map:
                return routes.make_response(
                    data={"error": "No levels found in the project — create levels first"},
                    status=404,
                )

            wall_types = (
                DB.FilteredElementCollector(doc)
                .OfClass(DB.WallType)
                .ToElements()
            )
            wall_type_map = {}
            for wt in wall_types:
                try:
                    wall_type_map[get_element_name(wt)] = wt
                except Exception:
                    continue

            beam_types = (
                DB.FilteredElementCollector(doc)
                .OfCategory(DB.BuiltInCategory.OST_StructuralFraming)
                .OfClass(DB.FamilySymbol)
                .ToElements()
            )
            beam_type_map = {}
            for bt in beam_types:
                try:
                    beam_type_map[get_element_name(bt)] = bt
                except Exception:
                    continue

            created = []
            errors = []

            t = DB.Transaction(doc, "Create Line-Based Elements")
            t.Start()

            try:
                for idx, elem in enumerate(elements):
                    try:
                        element_type = elem.get("element_type")
                        if not element_type:
                            errors.append("Element {}: element_type is required".format(idx))
                            continue

                        start = elem.get("start_point")
                        end = elem.get("end_point")
                        if not start or not end:
                            errors.append("Element {}: start_point and end_point are required".format(idx))
                            continue

                        # Convert mm to feet
                        sp = DB.XYZ(
                            float(start["x"]) / 304.8,
                            float(start["y"]) / 304.8,
                            float(start.get("z", 0)) / 304.8,
                        )
                        ep = DB.XYZ(
                            float(end["x"]) / 304.8,
                            float(end["y"]) / 304.8,
                            float(end.get("z", 0)) / 304.8,
                        )

                        # Validate non-zero length
                        if sp.DistanceTo(ep) < 0.001:
                            errors.append(
                                "Element {}: Start and end points must be different (zero-length element)".format(idx)
                            )
                            continue

                        line = DB.Line.CreateBound(sp, ep)

                        # Find level
                        level_name = elem.get("level_name")
                        level = None
                        if level_name:
                            level = level_map.get(level_name)
                            if not level:
                                available = ", ".join(sorted(level_map.keys()))
                                errors.append(
                                    "Element {}: Level '{}' not found. Available levels: {}".format(
                                        idx, level_name, available
                                    )
                                )
                                continue
                        else:
                            # Use first level (lowest elevation)
                            sorted_levels = sorted(level_map.values(), key=lambda x: x.Elevation)
                            level = sorted_levels[0]

                        if element_type == "wall":
                            type_name = elem.get("type_name")
                            wall_type = None
                            if type_name:
                                wall_type = wall_type_map.get(type_name)
                                if not wall_type:
                                    available = ", ".join(sorted(wall_type_map.keys())[:10])
                                    errors.append(
                                        "Element {}: Wall type '{}' not found. Available types: {}".format(
                                            idx, type_name, available
                                        )
                                    )
                                    continue
                            else:
                                if wall_type_map:
                                    wall_type = list(wall_type_map.values())[0]
                                else:
                                    errors.append(
                                        "Element {}: No wall types available — load wall families into the project".format(idx)
                                    )
                                    continue

                            height_mm = float(elem.get("height", 3000))
                            height_feet = height_mm / 304.8
                            offset_mm = float(elem.get("offset", 0))
                            offset_feet = offset_mm / 304.8
                            is_structural = bool(elem.get("structural", False))

                            wall = DB.Wall.Create(
                                doc,
                                line,
                                wall_type.Id,
                                level.Id,
                                height_feet,
                                offset_feet,
                                False,
                                is_structural,
                            )

                            created.append({
                                "id": get_element_id_value(wall),
                                "name": elem.get("name", ""),
                                "type": get_element_name(wall_type),
                                "level": get_element_name(level),
                                "element_type": "wall",
                            })

                        elif element_type == "beam":
                            type_name = elem.get("type_name")
                            beam_type = None
                            if type_name:
                                beam_type = beam_type_map.get(type_name)
                                if not beam_type:
                                    available = ", ".join(sorted(beam_type_map.keys())[:10])
                                    errors.append(
                                        "Element {}: Beam type '{}' not found. Available types: {}".format(
                                            idx, type_name, available
                                        )
                                    )
                                    continue
                            else:
                                if beam_type_map:
                                    beam_type = list(beam_type_map.values())[0]
                                else:
                                    errors.append(
                                        "Element {}: No beam types available — load structural framing families".format(idx)
                                    )
                                    continue

                            if not beam_type.IsActive:
                                beam_type.Activate()
                                doc.Regenerate()

                            beam = doc.Create.NewFamilyInstance(
                                line,
                                beam_type,
                                level,
                                DB.Structure.StructuralType.Beam,
                            )

                            created.append({
                                "id": get_element_id_value(beam),
                                "name": elem.get("name", ""),
                                "type": get_element_name(beam_type),
                                "level": get_element_name(level),
                                "element_type": "beam",
                            })

                        else:
                            errors.append(
                                "Element {}: element_type '{}' not supported — use 'wall' or 'beam'".format(
                                    idx, element_type
                                )
                            )
                            continue

                    except Exception as elem_err:
                        errors.append("Element {}: {}".format(idx, str(elem_err)))
                        continue

                t.Commit()

            except Exception as tx_err:
                if t.HasStarted() and not t.HasEnded():
                    t.RollBack()
                return routes.make_response(
                    data={"error": "Transaction failed: {}".format(str(tx_err))},
                    status=500,
                )

            response_data = {
                "status": "success",
                "created": created,
                "count": len(created),
                "message": "Created {} element(s)".format(len(created)),
            }
            if errors:
                response_data["errors"] = errors

            return routes.make_response(data=response_data)

        except Exception as e:
            logger.error("Failed to create line-based elements: {}".format(str(e)))
            return routes.make_response(
                data={"error": str(e), "traceback": traceback.format_exc()},
                status=500,
            )

    @api.route("/create_surface/", methods=["POST"])
    def create_surface_based(doc, request):
        """
        Create surface-based elements (floors, roofs, ceilings) in the Revit model.
        Supports batch creation via elements array.
        """
        try:
            if not doc:
                return routes.make_response(
                    data={"error": "No active Revit document — open a project in Revit 2026"},
                    status=503,
                )

            data = json.loads(request.data) if isinstance(request.data, str) else request.data
            elements = data.get("elements", [])

            if not elements:
                return routes.make_response(
                    data={"error": "No elements provided — pass an array of element definitions"},
                    status=400,
                )

            # Collect levels
            all_levels = (
                DB.FilteredElementCollector(doc)
                .OfCategory(DB.BuiltInCategory.OST_Levels)
                .WhereElementIsNotElementType()
                .ToElements()
            )
            level_map = {}
            for lv in all_levels:
                try:
                    level_map[get_element_name(lv)] = lv
                except Exception:
                    continue

            if not level_map:
                return routes.make_response(
                    data={"error": "No levels found — create levels first"},
                    status=404,
                )

            # Collect floor types
            floor_types = DB.FilteredElementCollector(doc).OfClass(DB.FloorType).ToElements()
            floor_type_map = {}
            for ft in floor_types:
                try:
                    floor_type_map[get_element_name(ft)] = ft
                except Exception:
                    continue

            # Collect roof types
            roof_types = DB.FilteredElementCollector(doc).OfClass(DB.RoofType).ToElements()
            roof_type_map = {}
            for rt in roof_types:
                try:
                    roof_type_map[get_element_name(rt)] = rt
                except Exception:
                    continue

            created = []
            errors = []

            t = DB.Transaction(doc, "Create Surface-Based Elements")
            t.Start()

            try:
                for idx, elem in enumerate(elements):
                    try:
                        element_type = elem.get("element_type")
                        if not element_type:
                            errors.append("Element {}: element_type is required".format(idx))
                            continue

                        if element_type not in ("floor", "roof", "ceiling"):
                            errors.append(
                                "Element {}: element_type must be 'floor', 'roof', or 'ceiling'".format(idx)
                            )
                            continue

                        boundary = elem.get("boundary", [])
                        if len(boundary) < 3:
                            errors.append(
                                "Element {}: Boundary requires at least 3 points/segments, got {}".format(
                                    idx, len(boundary)
                                )
                            )
                            continue

                        # BUG-007: Auto-detect point format vs segment format
                        # Point format: [{"x":0,"y":0,"z":0}, ...]
                        # Segment format: [{"p0":{"x":0,...},"p1":{"x":0,...}}, ...]
                        if "x" in boundary[0] or "y" in boundary[0]:
                            # Point array format — convert to segment format
                            points = boundary
                            boundary = []
                            for pi in range(len(points)):
                                p0 = points[pi]
                                p1 = points[(pi + 1) % len(points)]
                                boundary.append({"p0": p0, "p1": p1})

                        # Validate closed polygon
                        first_p0 = boundary[0].get("p0", {})
                        last_p1 = boundary[-1].get("p1", {})
                        fp = (float(first_p0.get("x", 0)), float(first_p0.get("y", 0)), float(first_p0.get("z", 0)))
                        lp = (float(last_p1.get("x", 0)), float(last_p1.get("y", 0)), float(last_p1.get("z", 0)))
                        dist = ((fp[0] - lp[0]) ** 2 + (fp[1] - lp[1]) ** 2 + (fp[2] - lp[2]) ** 2) ** 0.5
                        if dist > 1.0:  # tolerance of 1mm
                            errors.append(
                                "Element {}: Boundary must form a closed polygon — last point ({}, {}, {}) does not match first point ({}, {}, {})".format(
                                    idx, lp[0], lp[1], lp[2], fp[0], fp[1], fp[2]
                                )
                            )
                            continue

                        # Find level
                        level_name = elem.get("level_name")
                        level = None
                        if level_name:
                            level = level_map.get(level_name)
                            if not level:
                                available = ", ".join(sorted(level_map.keys()))
                                errors.append(
                                    "Element {}: Level '{}' not found. Available levels: {}".format(
                                        idx, level_name, available
                                    )
                                )
                                continue
                        else:
                            sorted_levels = sorted(level_map.values(), key=lambda x: x.Elevation)
                            level = sorted_levels[0]

                        if element_type == "floor" or element_type == "ceiling":
                            type_name = elem.get("type_name")
                            floor_type = None
                            if type_name:
                                floor_type = floor_type_map.get(type_name)
                                if not floor_type:
                                    available = ", ".join(sorted(floor_type_map.keys())[:10])
                                    errors.append(
                                        "Element {}: Floor type '{}' not found. Available: {}".format(
                                            idx, type_name, available
                                        )
                                    )
                                    continue
                            else:
                                if floor_type_map:
                                    floor_type = list(floor_type_map.values())[0]
                                else:
                                    errors.append(
                                        "Element {}: No floor types available — load floor families".format(idx)
                                    )
                                    continue

                            # Build curve loop
                            curve_loop = DB.CurveLoop()
                            for seg in boundary:
                                p0 = seg.get("p0", {})
                                p1 = seg.get("p1", {})
                                s = DB.XYZ(
                                    float(p0.get("x", 0)) / 304.8,
                                    float(p0.get("y", 0)) / 304.8,
                                    float(p0.get("z", 0)) / 304.8,
                                )
                                e = DB.XYZ(
                                    float(p1.get("x", 0)) / 304.8,
                                    float(p1.get("y", 0)) / 304.8,
                                    float(p1.get("z", 0)) / 304.8,
                                )
                                curve_loop.Append(DB.Line.CreateBound(s, e))

                            curve_loops = List[DB.CurveLoop]()
                            curve_loops.Add(curve_loop)

                            floor = DB.Floor.Create(doc, curve_loops, floor_type.Id, level.Id)

                            # Apply offset if specified
                            offset_mm = float(elem.get("offset", 0))
                            if offset_mm != 0:
                                offset_param = floor.get_Parameter(
                                    DB.BuiltInParameter.FLOOR_HEIGHTABOVELEVEL_PARAM
                                )
                                if offset_param and not offset_param.IsReadOnly:
                                    offset_param.Set(offset_mm / 304.8)

                            created.append({
                                "id": get_element_id_value(floor),
                                "name": elem.get("name", ""),
                                "type": get_element_name(floor_type),
                                "level": get_element_name(level),
                                "element_type": element_type,
                            })

                        elif element_type == "roof":
                            type_name = elem.get("type_name")
                            roof_type = None
                            if type_name:
                                roof_type = roof_type_map.get(type_name)
                                if not roof_type:
                                    available = ", ".join(sorted(roof_type_map.keys())[:10])
                                    errors.append(
                                        "Element {}: Roof type '{}' not found. Available: {}".format(
                                            idx, type_name, available
                                        )
                                    )
                                    continue
                            else:
                                if roof_type_map:
                                    roof_type = list(roof_type_map.values())[0]
                                else:
                                    errors.append(
                                        "Element {}: No roof types available — load roof families".format(idx)
                                    )
                                    continue

                            # Build CurveArray for legacy NewFootPrintRoof API
                            curve_array = DB.CurveArray()
                            for seg in boundary:
                                p0 = seg.get("p0", {})
                                p1 = seg.get("p1", {})
                                s = DB.XYZ(
                                    float(p0.get("x", 0)) / 304.8,
                                    float(p0.get("y", 0)) / 304.8,
                                    float(p0.get("z", 0)) / 304.8,
                                )
                                e = DB.XYZ(
                                    float(p1.get("x", 0)) / 304.8,
                                    float(p1.get("y", 0)) / 304.8,
                                    float(p1.get("z", 0)) / 304.8,
                                )
                                curve_array.Append(DB.Line.CreateBound(s, e))

                            import clr
                            model_curves = clr.Reference[DB.ModelCurveArray]()
                            roof = doc.Create.NewFootPrintRoof(
                                curve_array, level, roof_type, model_curves
                            )

                            created.append({
                                "id": get_element_id_value(roof),
                                "name": elem.get("name", ""),
                                "type": get_element_name(roof_type),
                                "level": get_element_name(level),
                                "element_type": "roof",
                            })

                    except Exception as elem_err:
                        errors.append("Element {}: {}".format(idx, str(elem_err)))
                        continue

                t.Commit()

            except Exception as tx_err:
                if t.HasStarted() and not t.HasEnded():
                    t.RollBack()
                return routes.make_response(
                    data={"error": "Transaction failed: {}".format(str(tx_err))},
                    status=500,
                )

            response_data = {
                "status": "success",
                "created": created,
                "count": len(created),
                "message": "Created {} element(s)".format(len(created)),
            }
            if errors:
                response_data["errors"] = errors

            return routes.make_response(data=response_data)

        except Exception as e:
            logger.error("Failed to create surface-based elements: {}".format(str(e)))
            return routes.make_response(
                data={"error": str(e), "traceback": traceback.format_exc()},
                status=500,
            )

    @api.route("/create_level/", methods=["POST"])
    def create_level_handler(doc, request):
        """
        Create building levels at specified elevations.
        Supports batch creation via levels array.
        """
        try:
            if not doc:
                return routes.make_response(
                    data={"error": "No active Revit document — open a project in Revit 2026"},
                    status=503,
                )

            data = json.loads(request.data) if isinstance(request.data, str) else request.data
            levels = data.get("levels", [])

            if not levels:
                return routes.make_response(
                    data={"error": "No levels provided — pass an array of level definitions"},
                    status=400,
                )

            created = []
            errors = []

            t = DB.Transaction(doc, "Create Levels")
            t.Start()

            try:
                for idx, lv in enumerate(levels):
                    try:
                        elevation_mm = lv.get("elevation")
                        if elevation_mm is None:
                            errors.append("Level {}: elevation is required".format(idx))
                            continue

                        elevation_feet = float(elevation_mm) / 304.8
                        new_level = DB.Level.Create(doc, elevation_feet)

                        name = lv.get("name")
                        if name:
                            new_level.Name = str(name)

                        created.append({
                            "id": get_element_id_value(new_level),
                            "name": get_element_name(new_level),
                            "elevation_mm": float(elevation_mm),
                        })

                    except Exception as lv_err:
                        errors.append("Level {}: {}".format(idx, str(lv_err)))
                        continue

                t.Commit()

            except Exception as tx_err:
                if t.HasStarted() and not t.HasEnded():
                    t.RollBack()
                return routes.make_response(
                    data={"error": "Transaction failed: {}".format(str(tx_err))},
                    status=500,
                )

            response_data = {
                "status": "success",
                "created": created,
                "count": len(created),
                "message": "Created {} level(s)".format(len(created)),
            }
            if errors:
                response_data["errors"] = errors

            return routes.make_response(data=response_data)

        except Exception as e:
            logger.error("Failed to create levels: {}".format(str(e)))
            return routes.make_response(
                data={"error": str(e), "traceback": traceback.format_exc()},
                status=500,
            )

    logger.info("Building routes registered successfully")
