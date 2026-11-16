# -*- coding: UTF-8 -*-
"""
Revit MCP Extension Startup
Registers all MCP routes and initializes the API
"""

from pyrevit import routes
import importlib
import logging

import revit_mcp

logger = logging.getLogger(__name__)

# Initialize the main API
api = routes.API("revit_mcp")

# Route modules, in registration order
MODULES = (
    ("status", "register_status_routes"),
    ("model_info", "register_model_info_routes"),
    ("views", "register_views_routes"),
    ("placement", "register_placement_routes"),
    ("colors", "register_color_routes"),
    ("code_execution", "register_code_execution_routes"),
    ("building", "register_building_routes"),
    ("editing", "register_editing_routes"),
    ("structure", "register_structure_routes"),
    ("annotation", "register_annotation_routes"),
    ("analysis", "register_analysis_routes"),
    ("documentation", "register_documentation_routes"),
    ("rooms", "register_room_routes"),
    ("view_management", "register_view_management_routes"),
    ("tags", "register_tag_routes"),
    ("transforms", "register_transform_routes"),
    ("mep", "register_mep_routes"),
    ("parameters", "register_parameter_routes"),
    ("interop", "register_interop_routes"),
    ("detail", "register_detail_routes"),
    ("clash", "register_clash_routes"),
    ("document", "register_document_routes"),
)


def _load_module(module_name):
    """Import one route module from the revit_mcp package."""
    return importlib.import_module("revit_mcp.{}".format(module_name))


def register_modules(api, modules=MODULES, load_module=_load_module):
    """Register every module in `modules` on its own, keeping one failure local.

    A module that cannot be imported or registered only loses its own tools;
    the rest still come up. Returns the failures as
    ``[{"module": <name>, "error": <message>}]``.
    """
    failures = []

    for module_name, register_name in modules:
        try:
            module = load_module(module_name)
            getattr(module, register_name)(api)
        except Exception as exc:
            logger.error(
                "Failed to register MCP routes from %s: %s", module_name, exc
            )
            logger.debug("Traceback for %s", module_name, exc_info=True)
            failures.append({"module": module_name, "error": str(exc)})

    if failures:
        logger.warning(
            "%d of %d MCP route modules failed to register: %s",
            len(failures),
            len(modules),
            ", ".join(failure["module"] for failure in failures),
        )
    else:
        logger.info("All MCP routes registered successfully")

    return failures


def register_routes():
    """Register all MCP route modules"""
    revit_mcp.REGISTRATION_FAILURES[:] = register_modules(api)


# Register all routes when the extension loads
register_routes()
