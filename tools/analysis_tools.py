# -*- coding: utf-8 -*-
"""Analysis tools — element filtering, rooms, materials, and statistics"""

from mcp.server.fastmcp import Context
from .utils import format_response


def register_analysis_tools(mcp, revit_get, revit_post, revit_image=None):
    """Register analysis tools with the MCP server."""
    _ = revit_image  # Acknowledge unused parameter

    @mcp.tool()
    async def ai_element_filter(
        category: str = None,
        type_name: str = None,
        visible_in_view: bool = False,
        bounding_box_min: dict = None,
        bounding_box_max: dict = None,
        max_elements: int = 50,
        ctx: Context = None,
    ) -> str:
        """Filter and find Revit elements by category, type, visibility, and spatial bounds.

        A powerful query tool for finding specific elements in the model. Combine
        filters for precise results — e.g., find all exterior walls on Level 1
        visible in the current view.

        Args:
            category: BuiltInCategory name, e.g. "OST_Walls", "OST_Doors" (optional)
            type_name: Filter by family type name or partial match (optional)
            visible_in_view: Only include elements visible in the active view (optional)
            bounding_box_min: Spatial filter min corner {"x", "y", "z"} in mm (optional)
            bounding_box_max: Spatial filter max corner {"x", "y", "z"} in mm (optional)
            max_elements: Maximum results to return (defaults to 50)
            ctx: MCP context for logging
        """
        data = {
            "category": category,
            "type_name": type_name,
            "visible_in_view": visible_in_view,
            "bounding_box_min": bounding_box_min,
            "bounding_box_max": bounding_box_max,
            "max_elements": max_elements,
        }
        response = await revit_post("/ai_filter/", data, ctx)
        return format_response(response)

    @mcp.tool()
    async def export_room_data(
        ctx: Context = None,
    ) -> str:
        """Export data for all rooms defined in the Revit model.

        Returns room names, numbers, levels, areas, perimeters, and departments
        in a structured format suitable for analysis and reporting.

        Args:
            ctx: MCP context for logging
        """
        response = await revit_get("/room_data/", ctx)
        return format_response(response)

    @mcp.tool()
    async def get_material_quantities(
        categories: list[str] = None,
        ctx: Context = None,
    ) -> str:
        """Get material quantities (areas and volumes) from the Revit model.

        Returns aggregated material data across all elements, optionally filtered
        by category. Useful for quantity takeoffs and cost estimation.

        Args:
            categories: List of categories to include, e.g. ["OST_Walls", "OST_Floors"]
                (optional, defaults to all categories)
            ctx: MCP context for logging
        """
        data = {"categories": categories}
        response = await revit_post("/material_quantities/", data, ctx)
        return format_response(response)

    @mcp.tool()
    async def analyze_model_statistics(
        ctx: Context = None,
    ) -> str:
        """Analyze the Revit model and return element counts grouped by category.

        Provides a high-level overview of what's in the model — how many walls,
        doors, windows, floors, etc. Useful for progress tracking and model health checks.

        Args:
            ctx: MCP context for logging
        """
        response = await revit_get("/model_statistics/", ctx)
        return format_response(response)
