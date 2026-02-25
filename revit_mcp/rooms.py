# -*- coding: UTF-8 -*-
"""
Rooms Module for Revit MCP
Handles room creation and room separation lines
"""

from utils import get_element_name, get_element_id_value, make_element_id
from pyrevit import routes, revit, DB
from System.Collections.Generic import List
import json
import traceback
import logging

logger = logging.getLogger(__name__)

MM_TO_FEET = 1.0 / 304.8


def register_room_routes(api):
    """Register all room routes with the API"""

    @api.route("/create_room/", methods=["POST"])
    def create_room_handler(doc, request):
        """Create a room at a specified level."""
        try:
            if not doc:
                return routes.make_response(
                    data={"error": "No active Revit document"}, status=503
                )

            data = json.loads(request.data) if isinstance(request.data, str) else request.data

            level_name = data.get("level_name")
            if not level_name:
                return routes.make_response(
                    data={"error": "level_name is required"}, status=400
                )

            # Find the level
            levels = (
                DB.FilteredElementCollector(doc)
                .OfCategory(DB.BuiltInCategory.OST_Levels)
                .WhereElementIsNotElementType()
                .ToElements()
            )
            target_level = None
            for lv in levels:
                if get_element_name(lv) == level_name:
                    target_level = lv
                    break

            if not target_level:
                available = [get_element_name(lv) for lv in levels]
                return routes.make_response(
                    data={
                        "error": "Level '{}' not found".format(level_name),
                        "available_levels": available,
                    },
                    status=404,
                )

            # Get the phase — rooms require a phase
            phases = doc.Phases
            if not phases or phases.Size == 0:
                return routes.make_response(
                    data={"error": "No phases found in the project"},
                    status=500,
                )
            phase = phases.get_Item(phases.Size - 1)

            t = DB.Transaction(doc, "Create Room via MCP")
            t.Start()

            try:
                location = data.get("location")
                if location:
                    x = float(location.get("x", 0)) * MM_TO_FEET
                    y = float(location.get("y", 0)) * MM_TO_FEET
                    point = DB.UV(x, y)
                    room = doc.Create.NewRoom(target_level, point)
                else:
                    # Create unplaced room first, then Revit associates it
                    room = doc.Create.NewRoom(phase)

                if not room:
                    t.RollBack()
                    return routes.make_response(
                        data={"error": "Failed to create room — no enclosed area found at the specified location. Add walls or room separation lines first."},
                        status=500,
                    )

                # Set name and number if provided
                room_name = data.get("name")
                if room_name:
                    name_param = room.LookupParameter("Name")
                    if name_param and not name_param.IsReadOnly:
                        name_param.Set(room_name)

                room_number = data.get("number")
                if room_number:
                    number_param = room.LookupParameter("Number")
                    if number_param and not number_param.IsReadOnly:
                        number_param.Set(room_number)

                t.Commit()

                # Get area after commit
                area = 0.0
                try:
                    area_param = room.LookupParameter("Area")
                    if area_param and area_param.HasValue:
                        area = round(area_param.AsDouble() * 0.092903, 2)  # sq ft to sq m
                except Exception:
                    pass

                actual_name = ""
                try:
                    name_p = room.LookupParameter("Name")
                    if name_p:
                        actual_name = name_p.AsString() or ""
                except Exception:
                    pass

                actual_number = ""
                try:
                    number_p = room.LookupParameter("Number")
                    if number_p:
                        actual_number = number_p.AsString() or ""
                except Exception:
                    pass

                return routes.make_response(
                    data={
                        "status": "success",
                        "room_id": get_element_id_value(room),
                        "name": actual_name,
                        "number": actual_number,
                        "level": level_name,
                        "area": area,
                        "message": "Room '{}' created on level '{}'".format(
                            actual_name or actual_number or "Unnamed", level_name
                        ),
                    }
                )

            except Exception as tx_error:
                if t.HasStarted() and not t.HasEnded():
                    t.RollBack()
                raise tx_error

        except Exception as e:
            logger.error("Failed to create room: {}".format(str(e)))
            error_trace = traceback.format_exc()
            return routes.make_response(
                data={"error": str(e), "traceback": error_trace}, status=500
            )

    @api.route("/create_room_separation/", methods=["POST"])
    def create_room_separation_handler(doc, request):
        """Create room separation lines."""
        try:
            if not doc:
                return routes.make_response(
                    data={"error": "No active Revit document"}, status=503
                )

            data = json.loads(request.data) if isinstance(request.data, str) else request.data

            lines = data.get("lines", [])
            if not lines:
                return routes.make_response(
                    data={"error": "No lines provided"}, status=400
                )

            # Find the view to create lines in
            view_name = data.get("view_name")
            level_name = data.get("level_name")

            target_view = None
            if view_name:
                views = (
                    DB.FilteredElementCollector(doc)
                    .OfClass(DB.ViewPlan)
                    .WhereElementIsNotElementType()
                    .ToElements()
                )
                for v in views:
                    if get_element_name(v) == view_name:
                        target_view = v
                        break
                if not target_view:
                    return routes.make_response(
                        data={"error": "View '{}' not found".format(view_name)},
                        status=404,
                    )
            else:
                # Use active view if it's a plan view
                active_view = doc.ActiveView
                if hasattr(active_view, "ViewType") and active_view.ViewType in [
                    DB.ViewType.FloorPlan, DB.ViewType.CeilingPlan, DB.ViewType.AreaPlan
                ]:
                    target_view = active_view
                else:
                    return routes.make_response(
                        data={"error": "Active view is not a plan view — specify a view_name or switch to a plan view"},
                        status=400,
                    )

            # Find sketch plane from level
            sketch_plane = None
            if level_name:
                levels = (
                    DB.FilteredElementCollector(doc)
                    .OfCategory(DB.BuiltInCategory.OST_Levels)
                    .WhereElementIsNotElementType()
                    .ToElements()
                )
                for lv in levels:
                    if get_element_name(lv) == level_name:
                        sketch_plane = lv
                        break

            t = DB.Transaction(doc, "Create Room Separation Lines via MCP")
            t.Start()

            try:
                created_ids = []
                curve_array = DB.CurveArray()

                for line_def in lines:
                    sp = line_def.get("start_point", {})
                    ep = line_def.get("end_point", {})

                    start = DB.XYZ(
                        float(sp.get("x", 0)) * MM_TO_FEET,
                        float(sp.get("y", 0)) * MM_TO_FEET,
                        float(sp.get("z", 0)) * MM_TO_FEET,
                    )
                    end = DB.XYZ(
                        float(ep.get("x", 0)) * MM_TO_FEET,
                        float(ep.get("y", 0)) * MM_TO_FEET,
                        float(ep.get("z", 0)) * MM_TO_FEET,
                    )

                    line = DB.Line.CreateBound(start, end)
                    curve_array.Append(line)

                # Create room separation lines
                sp_plane = target_view.SketchPlane
                if not sp_plane:
                    # Create a sketch plane from the view's level
                    level_id = target_view.GenLevel.Id if target_view.GenLevel else None
                    if level_id:
                        level_elem = doc.GetElement(level_id)
                        sp_plane = DB.SketchPlane.Create(doc, level_id)

                separator = doc.Create.NewRoomBoundaryLines(
                    sp_plane, curve_array, target_view
                )

                if separator:
                    for elem in separator:
                        created_ids.append(get_element_id_value(elem))

                t.Commit()

                return routes.make_response(
                    data={
                        "status": "success",
                        "line_count": len(created_ids),
                        "line_ids": created_ids,
                        "message": "Created {} room separation line{}".format(
                            len(created_ids),
                            "s" if len(created_ids) != 1 else ""
                        ),
                    }
                )

            except Exception as tx_error:
                if t.HasStarted() and not t.HasEnded():
                    t.RollBack()
                raise tx_error

        except Exception as e:
            logger.error("Failed to create room separation: {}".format(str(e)))
            error_trace = traceback.format_exc()
            return routes.make_response(
                data={"error": str(e), "traceback": error_trace}, status=500
            )

    logger.info("Room routes registered successfully")
