# -*- coding: UTF-8 -*-
"""
Views Module for Revit MCP
Handles view export and image generation functionality
"""

from utils import get_element_id_value
from pyrevit import routes, revit, DB
import tempfile
import os
import base64
import logging
from System.Collections.Generic import List

from utils import normalize_string, get_element_name

logger = logging.getLogger(__name__)


def register_views_routes(api):
    """Register all view-related routes with the API"""

    @api.route("/get_view/<view_name>", methods=["GET"])
    def get_view(doc, view_name):
        """
        Export a named Revit view as a PNG image and return the image data

        Args:
            doc: Revit document (provided by MCP context)
            view_name: Name of the view to export

        Returns:
            dict: Contains base64 encoded image data and content type, or error message
        """
        try:
            if not doc:
                return routes.make_response(
                    data={"error": "No active Revit document"}, status=503
                )

            # Normalize the view name
            view_name = normalize_string(view_name)
            logger.info("Exporting view: {}".format(view_name))

            # Define output folder in temp directory
            output_folder = os.path.join(tempfile.gettempdir(), "RevitMCPExports")

            # Create output folder if it doesn't exist
            if not os.path.exists(output_folder):
                os.makedirs(output_folder)

            # Create filename prefix
            file_path_prefix = os.path.join(output_folder, "export")

            # Find the view by name
            target_view = None
            all_views = DB.FilteredElementCollector(doc).OfClass(DB.View).ToElements()

            for view in all_views:
                try:
                    # Use safe name access
                    current_view_name = get_element_name(view)
                    if current_view_name == view_name:
                        target_view = view
                        break
                except Exception as e:
                    logger.warning("Could not get name for view: {}".format(str(e)))
                    continue

            if not target_view:
                # Get list of available views for better error message
                available_views = []
                for view in all_views:
                    try:
                        view_name_safe = get_element_name(view)
                        # Filter out system views and templates
                        if (
                            hasattr(view, "IsTemplate")
                            and not view.IsTemplate
                            and view.ViewType != DB.ViewType.Internal
                            and view.ViewType != DB.ViewType.ProjectBrowser
                        ):
                            available_views.append(view_name_safe)
                    except:
                        continue

                return routes.make_response(
                    data={
                        "error": "View '{}' not found".format(view_name),
                        "available_views": available_views[
                            :20
                        ],  # Limit to first 20 for readability
                    },
                    status=404,
                )

            # Check if view can be exported
            try:
                if hasattr(target_view, "IsTemplate") and target_view.IsTemplate:
                    return routes.make_response(
                        data={"error": "Cannot export view templates"}, status=400
                    )

                if target_view.ViewType == DB.ViewType.Internal:
                    return routes.make_response(
                        data={"error": "Cannot export internal views"}, status=400
                    )
            except Exception as e:
                logger.warning("Could not check view properties: {}".format(str(e)))

            # Set up export options
            ieo = DB.ImageExportOptions()
            ieo.ExportRange = DB.ExportRange.SetOfViews

            # Create list of view IDs to export
            viewIds = List[DB.ElementId]()
            viewIds.Add(target_view.Id)
            ieo.SetViewsAndSheets(viewIds)

            ieo.FilePath = file_path_prefix
            ieo.HLRandWFViewsFileType = DB.ImageFileType.PNG
            ieo.ShadowViewsFileType = DB.ImageFileType.PNG
            ieo.ImageResolution = DB.ImageResolution.DPI_150
            ieo.ZoomType = DB.ZoomFitType.FitToPage
            ieo.PixelSize = 1024  # Set a reasonable default size

            # Export the image
            logger.info("Starting image export for view: {}".format(view_name))
            doc.ExportImage(ieo)

            # Find the exported file (most recent PNG in folder)
            matching_files = []
            try:
                matching_files = [
                    os.path.join(output_folder, f)
                    for f in os.listdir(output_folder)
                    if f.endswith(".png")
                ]
                matching_files.sort(key=lambda x: os.path.getctime(x), reverse=True)
            except Exception as e:
                logger.error("Could not list exported files: {}".format(str(e)))
                return routes.make_response(
                    data={"error": "Could not access export folder"}, status=500
                )

            if not matching_files:
                return routes.make_response(
                    data={"error": "Export failed - no image file was created"},
                    status=500,
                )

            exported_file = matching_files[0]
            logger.info("Image exported successfully: {}".format(exported_file))

            # Read and encode the image
            try:
                with open(exported_file, "rb") as img_file:
                    img_data = img_file.read()

                encoded_data = base64.b64encode(img_data).decode("utf-8")

                # Get file size for logging
                file_size = len(img_data)
                logger.info(
                    "Image encoded successfully. Size: {} bytes".format(file_size)
                )

            except Exception as e:
                logger.error("Could not read/encode image file: {}".format(str(e)))
                return routes.make_response(
                    data={"error": "Could not read exported image file"}, status=500
                )
            finally:
                # Clean up the file
                try:
                    if os.path.exists(exported_file):
                        os.remove(exported_file)
                        logger.info("Temporary export file cleaned up")
                except Exception as e:
                    logger.warning(
                        "Could not clean up temporary file: {}".format(str(e))
                    )

            return routes.make_response(
                data={
                    "image_data": encoded_data,
                    "content_type": "image/png",
                    "view_name": view_name,
                    "file_size_bytes": len(img_data),
                    "export_success": True,
                }
            )

        except Exception as e:
            logger.error("Failed to export view '{}': {}".format(view_name, str(e)))
            return routes.make_response(
                data={"error": "Failed to export view: {}".format(str(e))}, status=500
            )

    @api.route("/list_views/", methods=["GET"])
    def list_views(doc):
        """
        Get a list of all exportable views in the current Revit model

        Returns:
            dict: List of view names organized by type
        """
        try:
            if not doc:
                return routes.make_response(
                    data={"error": "No active Revit document"}, status=503
                )

            logger.info("Listing all exportable views")

            # Get all views
            all_views = DB.FilteredElementCollector(doc).OfClass(DB.View).ToElements()

            views_by_type = {
                "floor_plans": [],
                "ceiling_plans": [],
                "elevations": [],
                "sections": [],
                "3d_views": [],
                "drafting_views": [],
                "schedules": [],
                "other": [],
            }

            for view in all_views:
                try:
                    # Skip templates and internal views
                    if hasattr(view, "IsTemplate") and view.IsTemplate:
                        continue

                    if (
                        view.ViewType == DB.ViewType.Internal
                        or view.ViewType == DB.ViewType.ProjectBrowser
                    ):
                        continue

                    view_name = get_element_name(view)
                    view_type = view.ViewType

                    # Categorize views
                    if view_type == DB.ViewType.FloorPlan:
                        views_by_type["floor_plans"].append(view_name)
                    elif view_type == DB.ViewType.CeilingPlan:
                        views_by_type["ceiling_plans"].append(view_name)
                    elif view_type == DB.ViewType.Elevation:
                        views_by_type["elevations"].append(view_name)
                    elif view_type == DB.ViewType.Section:
                        views_by_type["sections"].append(view_name)
                    elif view_type == DB.ViewType.ThreeD:
                        views_by_type["3d_views"].append(view_name)
                    elif view_type == DB.ViewType.DraftingView:
                        views_by_type["drafting_views"].append(view_name)
                    elif view_type == DB.ViewType.Schedule:
                        views_by_type["schedules"].append(view_name)
                    else:
                        views_by_type["other"].append(view_name)

                except Exception as e:
                    logger.warning("Could not process view: {}".format(str(e)))
                    continue

            # Sort all lists alphabetically
            for view_list in views_by_type.values():
                view_list.sort()

            # Count total exportable views
            total_views = sum(len(view_list) for view_list in views_by_type.values())

            return routes.make_response(
                data={
                    "views_by_type": views_by_type,
                    "total_exportable_views": total_views,
                    "status": "success",
                }
            )

        except Exception as e:
            logger.error("Failed to list views: {}".format(str(e)))
            return routes.make_response(
                data={"error": "Failed to list views: {}".format(str(e))}, status=500
            )

    @api.route("/current_view_info/", methods=["GET"])
    def get_current_view_info(uidoc):
        """
        Get detailed information about the currently active view.

        Args:
            uidoc: UIDocument (provided by MCP context)

        Returns:
            dict: Detailed information about the current view
        """
        try:
            if not uidoc or not uidoc.Document:
                return routes.make_response(
                    data={"error": "No active Revit document"}, status=503
                )

            current_view = uidoc.ActiveView
            if not current_view:
                return routes.make_response(
                    data={"error": "No active view found"}, status=404
                )

            logger.info("Getting current view info")

            # Get basic view information
            view_info = {
                "view_name": get_element_name(current_view),
                "view_type": str(current_view.ViewType),
                "view_id": get_element_id_value(current_view),
                "is_template": (
                    current_view.IsTemplate
                    if hasattr(current_view, "IsTemplate")
                    else False
                ),
            }

            # Add scale information if available
            try:
                view_info["scale"] = current_view.Scale
            except Exception:
                view_info["scale"] = None

            # Add crop box information if available
            try:
                view_info["crop_box_active"] = current_view.CropBoxActive
            except Exception:
                view_info["crop_box_active"] = False

            # Add view family type if available
            try:
                view_family_type = current_view.Document.GetElement(
                    current_view.GetTypeId()
                )
                if view_family_type:
                    view_info["view_family_type"] = get_element_name(view_family_type)
                else:
                    view_info["view_family_type"] = "Unknown"
            except Exception:
                view_info["view_family_type"] = "Unknown"

            # Add detail level if available
            try:
                view_info["detail_level"] = str(current_view.DetailLevel)
            except Exception:
                view_info["detail_level"] = "Unknown"

            # Add view discipline if available
            try:
                view_info["discipline"] = str(current_view.Discipline)
            except Exception:
                view_info["discipline"] = "Unknown"

            return routes.make_response(
                data={"status": "success", "view_info": view_info}
            )

        except Exception as e:
            logger.error("Get current view info failed: {}".format(str(e)))
            return routes.make_response(
                data={"error": "Failed to get current view info: {}".format(str(e))},
                status=500,
            )

    @api.route("/current_view_elements/", methods=["GET"])
    def get_current_view_elements(doc, uidoc):
        """
        Get all elements visible in the current view.

        Args:
            doc: Revit document (provided by MCP context)
            uidoc: UIDocument (provided by MCP context)

        Returns:
            dict: List of elements with detailed information
        """
        try:
            if not doc or not uidoc:
                return routes.make_response(
                    data={"error": "No active Revit document"}, status=503
                )

            current_view = uidoc.ActiveView
            if not current_view:
                return routes.make_response(
                    data={"error": "No active view found"}, status=404
                )

            logger.info("Getting elements in current view")

            # Get all elements in the current view
            collector = DB.FilteredElementCollector(doc, current_view.Id)
            elements = collector.WhereElementIsNotElementType().ToElements()

            # Process elements to get basic information
            elements_info = []
            for elem in elements:
                try:
                    element_info = {
                        "element_id": get_element_id_value(elem),
                        "name": get_element_name(elem),
                        "element_type": elem.GetType().Name,
                    }

                    # Add category information
                    if elem.Category:
                        element_info["category"] = elem.Category.Name
                        element_info["category_id"] = get_element_id_value(elem.Category.Id)
                    else:
                        element_info["category"] = "Unknown"
                        element_info["category_id"] = None

                    # Add level information if available
                    try:
                        level_param = elem.get_Parameter(
                            DB.BuiltInParameter.FAMILY_LEVEL_PARAM
                        )
                        if level_param:
                            level_id = level_param.AsElementId()
                            if level_id != DB.ElementId.InvalidElementId:
                                level_elem = doc.GetElement(level_id)
                                element_info["level"] = get_element_name(level_elem)
                                element_info["level_id"] = get_element_id_value(level_id)
                            else:
                                element_info["level"] = None
                                element_info["level_id"] = None
                        else:
                            element_info["level"] = None
                            element_info["level_id"] = None
                    except Exception:
                        element_info["level"] = None
                        element_info["level_id"] = None

                    # Add location information if available
                    try:
                        location = elem.Location
                        if hasattr(location, "Point"):
                            pt = location.Point
                            element_info["location"] = {
                                "type": "point",
                                "x": pt.X,
                                "y": pt.Y,
                                "z": pt.Z,
                            }
                        elif hasattr(location, "Curve"):
                            curve = location.Curve
                            start = curve.GetEndPoint(0)
                            end = curve.GetEndPoint(1)
                            element_info["location"] = {
                                "type": "curve",
                                "start": {"x": start.X, "y": start.Y, "z": start.Z},
                                "end": {"x": end.X, "y": end.Y, "z": end.Z},
                            }
                        else:
                            element_info["location"] = {"type": "unknown"}
                    except Exception:
                        element_info["location"] = {"type": "unknown"}

                    elements_info.append(element_info)

                except Exception as elem_error:
                    # Skip elements that cause errors but log the issue
                    logger.warning(
                        "Could not process element {}: {}".format(
                            get_element_id_value(elem) if elem else "Unknown", str(elem_error)
                        )
                    )
                    continue

            # Group elements by category for easier analysis
            elements_by_category = {}
            for elem_info in elements_info:
                category = elem_info["category"]
                if category not in elements_by_category:
                    elements_by_category[category] = []
                elements_by_category[category].append(elem_info)

            # Create summary statistics
            category_counts = {
                category: len(elements)
                for category, elements in elements_by_category.items()
            }

            result = {
                "status": "success",
                "view_name": get_element_name(current_view),
                "view_id": get_element_id_value(current_view),
                "total_elements": len(elements_info),
                "elements": elements_info,
                "elements_by_category": elements_by_category,
                "category_counts": category_counts,
            }

            return routes.make_response(data=result)

        except Exception as e:
            logger.error("Get current view elements failed: {}".format(str(e)))
            return routes.make_response(
                data={
                    "error": "Failed to get current view elements: {}".format(str(e))
                },
                status=500,
            )

    logger.info("Views routes registered successfully")
