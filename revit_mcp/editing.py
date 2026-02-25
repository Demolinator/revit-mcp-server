# -*- coding: UTF-8 -*-
"""
Editing Module for Revit MCP
Handles element deletion, modification, and selection retrieval
"""

from utils import get_element_name, make_element_id, get_element_id_value
from pyrevit import routes, revit, DB
import json
import traceback
import logging

logger = logging.getLogger(__name__)


def register_editing_routes(api):
    """Register all editing routes with the API"""

    @api.route("/delete_elements/", methods=["POST"])
    def delete_elements_handler(doc, request):
        """Delete one or more elements from the Revit model."""
        try:
            if not doc:
                return routes.make_response(
                    data={"error": "No active Revit document"}, status=503
                )

            # Parse request data
            if not request or not request.data:
                return routes.make_response(
                    data={"error": "No data provided"}, status=400
                )

            data = json.loads(request.data) if isinstance(request.data, str) else request.data

            element_ids = data.get("element_ids", [])
            if not element_ids:
                return routes.make_response(
                    data={"error": "No element_ids provided"}, status=400
                )

            # Validate all elements exist before deleting
            elements_to_delete = []
            for eid in element_ids:
                elem_id = make_element_id(eid)
                elem = doc.GetElement(elem_id)
                if not elem:
                    return routes.make_response(
                        data={"error": "Element {} not found in the active model".format(eid)},
                        status=404,
                    )
                elements_to_delete.append(elem_id)

            # Delete in a single transaction
            t = DB.Transaction(doc, "Delete Elements via MCP")
            t.Start()

            try:
                deleted_ids = []
                cascaded_ids = []

                for elem_id in elements_to_delete:
                    # doc.Delete returns a collection of all deleted IDs (including cascaded)
                    result = doc.Delete(elem_id)
                    primary_id = get_element_id_value(elem_id)
                    deleted_ids.append(primary_id)

                    # Track cascaded deletions
                    if result:
                        for del_id in result:
                            del_id_int = get_element_id_value(del_id)
                            if del_id_int != primary_id and del_id_int not in cascaded_ids:
                                cascaded_ids.append(del_id_int)

                t.Commit()

                # Remove primary IDs from cascaded list
                cascaded_ids = [cid for cid in cascaded_ids if cid not in deleted_ids]

                message = "Deleted {} element{}".format(
                    len(deleted_ids),
                    "s" if len(deleted_ids) != 1 else ""
                )
                if cascaded_ids:
                    message += " ({} hosted element{} also removed)".format(
                        len(cascaded_ids),
                        "s" if len(cascaded_ids) != 1 else ""
                    )

                return routes.make_response(
                    data={
                        "status": "success",
                        "deleted_count": len(deleted_ids),
                        "deleted_ids": deleted_ids,
                        "cascaded_ids": cascaded_ids,
                        "message": message,
                    }
                )

            except Exception as tx_error:
                if t.HasStarted() and not t.HasEnded():
                    t.RollBack()
                raise tx_error

        except Exception as e:
            logger.error("Failed to delete elements: {}".format(str(e)))
            error_trace = traceback.format_exc()
            return routes.make_response(
                data={"error": str(e), "traceback": error_trace}, status=500
            )

    @api.route("/modify_element/", methods=["POST"])
    def modify_element_handler(doc, request):
        """Modify parameter values on a Revit element."""
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

            element_id = data.get("element_id")
            parameters = data.get("parameters", {})

            if element_id is None:
                return routes.make_response(
                    data={"error": "No element_id provided"}, status=400
                )

            if not parameters:
                return routes.make_response(
                    data={"error": "No parameters provided"}, status=400
                )

            # Find the element
            elem_id = make_element_id(element_id)
            elem = doc.GetElement(elem_id)
            if not elem:
                return routes.make_response(
                    data={"error": "Element {} not found in the active model".format(element_id)},
                    status=404,
                )

            # Start transaction
            t = DB.Transaction(doc, "Modify Element via MCP")
            t.Start()

            try:
                changes = []
                failed = []

                for param_name, new_value in parameters.items():
                    param = elem.LookupParameter(param_name)
                    if not param:
                        # List available parameters for better error messages
                        available = []
                        for p in elem.Parameters:
                            try:
                                available.append(p.Definition.Name)
                            except Exception:
                                continue
                        available.sort()
                        failed.append({
                            "parameter": param_name,
                            "reason": "not found",
                            "available_parameters": available[:20],
                        })
                        continue

                    if param.IsReadOnly:
                        failed.append({
                            "parameter": param_name,
                            "reason": "read-only",
                        })
                        continue

                    # Get old value
                    old_value = ""
                    try:
                        if param.StorageType == DB.StorageType.String:
                            old_value = param.AsString() or ""
                        elif param.StorageType == DB.StorageType.Integer:
                            old_value = str(param.AsInteger())
                        elif param.StorageType == DB.StorageType.Double:
                            old_value = str(round(param.AsDouble(), 6))
                        elif param.StorageType == DB.StorageType.ElementId:
                            old_value = str(get_element_id_value(param.AsElementId()))
                    except Exception:
                        old_value = ""

                    # Set new value
                    try:
                        if param.StorageType == DB.StorageType.String:
                            param.Set(str(new_value))
                        elif param.StorageType == DB.StorageType.Integer:
                            param.Set(int(new_value))
                        elif param.StorageType == DB.StorageType.Double:
                            param.Set(float(new_value))
                        elif param.StorageType == DB.StorageType.ElementId:
                            param.Set(make_element_id(new_value))
                        else:
                            failed.append({
                                "parameter": param_name,
                                "reason": "unsupported storage type",
                            })
                            continue

                        changes.append({
                            "parameter": param_name,
                            "old_value": old_value,
                            "new_value": str(new_value),
                            "status": "set",
                        })
                    except Exception as set_err:
                        failed.append({
                            "parameter": param_name,
                            "reason": "set failed: {}".format(str(set_err)),
                        })

                t.Commit()

                message = "Modified {} parameter{} on element {}".format(
                    len(changes),
                    "s" if len(changes) != 1 else "",
                    element_id,
                )

                return routes.make_response(
                    data={
                        "status": "success",
                        "element_id": element_id,
                        "changes": changes,
                        "failed": failed,
                        "message": message,
                    }
                )

            except Exception as tx_error:
                if t.HasStarted() and not t.HasEnded():
                    t.RollBack()
                raise tx_error

        except Exception as e:
            logger.error("Failed to modify element: {}".format(str(e)))
            error_trace = traceback.format_exc()
            return routes.make_response(
                data={"error": str(e), "traceback": error_trace}, status=500
            )

    @api.route("/selected_elements/", methods=["GET"])
    def get_selected_elements_handler(doc, uidoc):
        """Get details of elements currently selected in Revit UI."""
        try:
            if not doc:
                return routes.make_response(
                    data={"error": "No active Revit document"}, status=503
                )

            if not uidoc:
                return routes.make_response(
                    data={"error": "No active UI document"}, status=503
                )

            # Get current selection
            selection = uidoc.Selection.GetElementIds()

            elements = []
            for elem_id in selection:
                elem = doc.GetElement(elem_id)
                if not elem:
                    continue

                elem_info = {
                    "id": get_element_id_value(elem_id),
                    "category": elem.Category.Name if elem.Category else "Unknown",
                    "type": get_element_name(elem),
                }

                # Try to get level
                try:
                    level_id = elem.LevelId
                    if level_id and level_id != DB.ElementId.InvalidElementId:
                        level = doc.GetElement(level_id)
                        if level:
                            elem_info["level"] = get_element_name(level)
                except Exception:
                    pass

                # Get key parameters
                params = {}
                key_param_names = ["Mark", "Comments", "Length", "Area", "Volume", "Width", "Height"]
                for pname in key_param_names:
                    try:
                        p = elem.LookupParameter(pname)
                        if p and p.HasValue:
                            if p.StorageType == DB.StorageType.String:
                                val = p.AsString()
                                if val:
                                    params[pname] = val
                            elif p.StorageType == DB.StorageType.Double:
                                params[pname] = str(round(p.AsDouble(), 4))
                            elif p.StorageType == DB.StorageType.Integer:
                                params[pname] = str(p.AsInteger())
                    except Exception:
                        continue

                if params:
                    elem_info["parameters"] = params

                elements.append(elem_info)

            count = len(elements)
            if count == 0:
                message = "No elements currently selected"
            elif count == 1:
                message = "1 element currently selected"
            else:
                message = "{} elements currently selected".format(count)

            return routes.make_response(
                data={
                    "status": "success",
                    "elements": elements,
                    "count": count,
                    "message": message,
                }
            )

        except Exception as e:
            logger.error("Failed to get selected elements: {}".format(str(e)))
            error_trace = traceback.format_exc()
            return routes.make_response(
                data={"error": str(e), "traceback": error_trace}, status=500
            )

    logger.info("Editing routes registered successfully")
