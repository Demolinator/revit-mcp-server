# -*- coding: UTF-8 -*-
"""
Annotation Module for Revit MCP
Handles dimensions and wall tagging
"""

from utils import get_element_name, get_element_id_value, make_element_id
from pyrevit import routes, revit, DB
import json
import traceback
import logging

logger = logging.getLogger(__name__)

MM_TO_FEET = 1.0 / 304.8


def register_annotation_routes(api):
    """Register all annotation routes with the API"""

    @api.route("/create_dimensions/", methods=["POST"])
    def create_dimensions_handler(doc, request):
        """Create dimension annotations in the current view."""
        try:
            if not doc:
                return routes.make_response(
                    data={"error": "No active Revit document"}, status=503
                )

            if not request or not request.data:
                return routes.make_response(
                    data={"error": "No data provided"}, status=400
                )

            data = json.loads(request.data) if isinstance(request.data, str) else request.data

            element_ids = data.get("element_ids", [])
            dimension_type = data.get("dimension_type", "linear")

            if not element_ids:
                return routes.make_response(
                    data={"error": "No element_ids provided"}, status=400
                )

            # Get active view
            active_view = doc.ActiveView
            if not active_view:
                return routes.make_response(
                    data={"error": "No active view"}, status=400
                )

            # Check view type supports dimensions
            view_type = active_view.ViewType
            supported_types = [
                DB.ViewType.FloorPlan,
                DB.ViewType.CeilingPlan,
                DB.ViewType.Section,
                DB.ViewType.Elevation,
                DB.ViewType.Detail,
                DB.ViewType.EngineeringPlan,
                DB.ViewType.AreaPlan,
            ]
            if view_type not in supported_types:
                return routes.make_response(
                    data={"error": "Current view does not support dimensions — switch to a plan, section, or elevation view"},
                    status=400,
                )

            # Collect elements and their references
            ref_array = DB.ReferenceArray()
            element_points = []

            for eid in element_ids:
                elem_id = make_element_id(eid)
                elem = doc.GetElement(elem_id)
                if not elem:
                    return routes.make_response(
                        data={"error": "Element {} not found or not visible in the current view".format(eid)},
                        status=404,
                    )

                # Try to get a reference from the element
                try:
                    # For walls, get the location line reference
                    if hasattr(elem, "Location") and elem.Location:
                        loc = elem.Location
                        if hasattr(loc, "Curve"):
                            curve = loc.Curve
                            ref = elem.GetReferenceByName("Center")
                            if not ref:
                                # Try getting reference from geometry
                                options = DB.Options()
                                options.ComputeReferences = True
                                options.View = active_view
                                geom = elem.get_Geometry(options)
                                if geom:
                                    for geom_obj in geom:
                                        if hasattr(geom_obj, "Reference") and geom_obj.Reference:
                                            ref = geom_obj.Reference
                                            break
                                        if hasattr(geom_obj, "GetInstanceGeometry"):
                                            inst_geom = geom_obj.GetInstanceGeometry()
                                            if inst_geom:
                                                for ig in inst_geom:
                                                    if hasattr(ig, "Reference") and ig.Reference:
                                                        ref = ig.Reference
                                                        break
                            if ref:
                                ref_array.Append(ref)
                                # Track midpoint for dimension line placement
                                mid = curve.Evaluate(0.5, True)
                                element_points.append(mid)
                        elif hasattr(loc, "Point"):
                            point = loc.Point
                            element_points.append(point)
                except Exception as ref_err:
                    logger.warning("Could not get reference for element {}: {}".format(
                        eid, str(ref_err)
                    ))

            if ref_array.Size < 2:
                return routes.make_response(
                    data={"error": "Need at least 2 elements with valid geometry references to create a dimension"},
                    status=400,
                )

            t = DB.Transaction(doc, "Create Dimensions via MCP")
            t.Start()

            try:
                created = []

                # Calculate dimension line position (offset from midpoint)
                if len(element_points) >= 2:
                    p1 = element_points[0]
                    p2 = element_points[-1]
                    mid = DB.XYZ(
                        (p1.X + p2.X) / 2.0,
                        (p1.Y + p2.Y) / 2.0,
                        (p1.Z + p2.Z) / 2.0,
                    )

                    # Direction perpendicular to element line
                    dx = p2.X - p1.X
                    dy = p2.Y - p1.Y
                    length = (dx * dx + dy * dy) ** 0.5

                    if length > 0.001:
                        # Offset perpendicular to the line
                        offset_dist = 3.0  # 3 feet offset
                        nx = -dy / length
                        ny = dx / length
                        offset_pt = DB.XYZ(mid.X + nx * offset_dist, mid.Y + ny * offset_dist, mid.Z)
                        dim_line = DB.Line.CreateBound(
                            DB.XYZ(p1.X + nx * offset_dist, p1.Y + ny * offset_dist, p1.Z),
                            DB.XYZ(p2.X + nx * offset_dist, p2.Y + ny * offset_dist, p2.Z),
                        )
                    else:
                        dim_line = DB.Line.CreateBound(p1, p2)
                else:
                    # Fallback: create a horizontal line
                    dim_line = DB.Line.CreateBound(
                        DB.XYZ(0, 10, 0),
                        DB.XYZ(100, 10, 0),
                    )

                dim = doc.Create.NewDimension(active_view, dim_line, ref_array)

                if dim:
                    # Get dimension value
                    dim_value = ""
                    try:
                        dim_value = dim.ValueString
                    except Exception:
                        pass

                    created.append({
                        "id": get_element_id_value(dim),
                        "elements_dimensioned": element_ids,
                        "value": dim_value or "N/A",
                    })

                t.Commit()

                message = "Created {} dimension annotation{} in the current view".format(
                    len(created),
                    "s" if len(created) != 1 else ""
                )

                return routes.make_response(
                    data={
                        "status": "success",
                        "created": created,
                        "count": len(created),
                        "message": message,
                    }
                )

            except Exception as tx_error:
                if t.HasStarted() and not t.HasEnded():
                    t.RollBack()
                raise tx_error

        except Exception as e:
            logger.error("Failed to create dimensions: {}".format(str(e)))
            error_trace = traceback.format_exc()
            return routes.make_response(
                data={"error": str(e), "traceback": error_trace}, status=500
            )

    @api.route("/tag_walls/", methods=["POST"])
    def tag_walls_handler(doc, request):
        """Tag all untagged walls in the current view."""
        try:
            if not doc:
                return routes.make_response(
                    data={"error": "No active Revit document"}, status=503
                )

            data = {}
            if request and request.data:
                data = json.loads(request.data) if isinstance(request.data, str) else request.data

            use_leader = data.get("use_leader", False)
            tag_type_name = data.get("tag_type_name")

            active_view = doc.ActiveView
            if not active_view:
                return routes.make_response(
                    data={"error": "No active view"}, status=400
                )

            # Find wall tag types
            tag_symbols = (
                DB.FilteredElementCollector(doc)
                .OfCategory(DB.BuiltInCategory.OST_WallTags)
                .OfClass(DB.FamilySymbol)
                .ToElements()
            )

            if not tag_symbols or len(tag_symbols) == 0:
                return routes.make_response(
                    data={"error": "No wall tag types found — load wall tag families into the project"},
                    status=400,
                )

            # Find specific tag type or use first
            target_tag = None
            if tag_type_name:
                for sym in tag_symbols:
                    try:
                        if get_element_name(sym) == tag_type_name:
                            target_tag = sym
                            break
                    except Exception:
                        continue

            if not target_tag:
                target_tag = tag_symbols[0]

            # Get walls visible in the current view
            walls = (
                DB.FilteredElementCollector(doc, active_view.Id)
                .OfCategory(DB.BuiltInCategory.OST_Walls)
                .WhereElementIsNotElementType()
                .ToElements()
            )

            if not walls or len(walls) == 0:
                return routes.make_response(
                    data={"error": "Current view has no walls to tag"},
                    status=400,
                )

            # Find already-tagged walls
            existing_tags = (
                DB.FilteredElementCollector(doc, active_view.Id)
                .OfCategory(DB.BuiltInCategory.OST_WallTags)
                .WhereElementIsNotElementType()
                .ToElements()
            )

            tagged_wall_ids = set()
            for tag in existing_tags:
                try:
                    if hasattr(tag, "TaggedLocalElementId"):
                        tagged_wall_ids.add(get_element_id_value(tag.TaggedLocalElementId))
                except Exception:
                    continue

            t = DB.Transaction(doc, "Tag Walls via MCP")
            t.Start()

            try:
                tags_placed = 0
                walls_already_tagged = 0

                # Activate tag symbol
                if not target_tag.IsActive:
                    target_tag.Activate()
                    doc.Regenerate()

                for wall in walls:
                    wall_id_val = get_element_id_value(wall)
                    if wall_id_val in tagged_wall_ids:
                        walls_already_tagged += 1
                        continue

                    # Get wall midpoint for tag placement
                    try:
                        loc = wall.Location
                        if not loc or not hasattr(loc, "Curve"):
                            continue

                        curve = loc.Curve
                        mid = curve.Evaluate(0.5, True)
                        tag_point = DB.UV(mid.X, mid.Y)

                        # Create tag using Revit 2026 API
                        ref = DB.Reference(wall)
                        tag = DB.IndependentTag.Create(
                            doc,
                            active_view.Id,
                            ref,
                            use_leader,
                            DB.TagMode.TM_ADDBY_CATEGORY,
                            DB.TagOrientation.Horizontal,
                            mid,
                        )

                        if tag:
                            tags_placed += 1
                    except Exception as tag_err:
                        logger.warning("Could not tag wall {}: {}".format(
                            wall_id_val, str(tag_err)
                        ))
                        continue

                t.Commit()

                walls_total = len(walls)
                message = "Tagged {} wall{} ({} already tagged, {} total in view)".format(
                    tags_placed,
                    "s" if tags_placed != 1 else "",
                    walls_already_tagged,
                    walls_total,
                )

                return routes.make_response(
                    data={
                        "status": "success",
                        "tags_placed": tags_placed,
                        "walls_already_tagged": walls_already_tagged,
                        "walls_total": walls_total,
                        "message": message,
                    }
                )

            except Exception as tx_error:
                if t.HasStarted() and not t.HasEnded():
                    t.RollBack()
                raise tx_error

        except Exception as e:
            logger.error("Failed to tag walls: {}".format(str(e)))
            error_trace = traceback.format_exc()
            return routes.make_response(
                data={"error": str(e), "traceback": error_trace}, status=500
            )

    logger.info("Annotation routes registered successfully")
