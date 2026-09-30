# -*- coding: utf-8 -*-
"""MCP tool modules.

Each module in this package defines ``register_<name>_tools(mcp, ...)`` and
pairs with a route module in ``revit_mcp/``. To add a module, create it and
append one row to ``_MODULES``.
"""

from importlib import import_module

# (module, registration function, HTTP helpers it takes after `mcp`)
_ALL = ("get", "post", "image")
_MODULES = (
    ("status_tools", "register_status_tools", ("get",)),
    ("view_tools", "register_view_tools", _ALL),
    ("family_tools", "register_family_tools", ("get", "post")),
    ("model_tools", "register_model_tools", ("get",)),
    ("colors_tools", "register_colors_tools", ("get", "post")),
    ("code_execution_tools", "register_code_execution_tools", _ALL),
    ("building_tools", "register_building_tools", _ALL),
    ("editing_tools", "register_editing_tools", _ALL),
    ("structure_tools", "register_structure_tools", _ALL),
    ("annotation_tools", "register_annotation_tools", _ALL),
    ("analysis_tools", "register_analysis_tools", _ALL),
    ("documentation_tools", "register_documentation_tools", _ALL),
    ("room_tools", "register_room_tools", _ALL),
    ("view_management_tools", "register_view_management_tools", _ALL),
    ("tag_tools", "register_tag_tools", _ALL),
    ("transform_tools", "register_transform_tools", _ALL),
    ("mep_tools", "register_mep_tools", _ALL),
    ("parameter_tools", "register_parameter_tools", _ALL),
    ("interop_tools", "register_interop_tools", _ALL),
    ("detail_tools", "register_detail_tools", _ALL),
    ("clash_tools", "register_clash_tools", _ALL),
    ("document_tools", "register_document_tools", _ALL),
)


def register_tools(mcp_server, revit_get, revit_post, revit_image):
    """Register every tool module with ``mcp_server``."""
    helpers = {"get": revit_get, "post": revit_post, "image": revit_image}
    for module_name, func_name, needs in _MODULES:
        register = getattr(import_module("." + module_name, __name__), func_name)
        register(mcp_server, *(helpers[n] for n in needs))
