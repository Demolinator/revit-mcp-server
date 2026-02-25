# -*- coding: utf-8 -*-
"""Building creation tools — walls, floors, roofs, ceilings, and levels"""

from mcp.server.fastmcp import Context
from .utils import format_response


def register_building_tools(mcp, revit_get, revit_post, revit_image=None):
    """Register building creation tools with the MCP server."""
    _ = revit_image  # Acknowledge unused parameter

    @mcp.tool()
    async def create_line_based_element(
        elements: list[dict],
        ctx: Context = None,
    ) -> str:
        """Create walls, beams, and other line-based building elements in Revit.

        Each element needs start and end points (in millimeters), element type
        (wall/beam), and optionally a level name, height, and family type name.
        Supports batch creation — pass multiple elements in one call.

        Args:
            elements: List of element definitions, each with:
                - element_type (str): "wall" or "beam" (required)
                - start_point (dict): {"x": float, "y": float, "z": float} in mm (required)
                - end_point (dict): {"x": float, "y": float, "z": float} in mm (required)
                - type_name (str): Family type name, e.g. "Generic - 200mm" (optional)
                - level_name (str): Target level name (optional, defaults to first level)
                - height (float): Element height in mm (optional, defaults to 3000)
                - offset (float): Offset from base level in mm (optional, defaults to 0)
                - structural (bool): Mark as structural (optional, defaults to false)
                - name (str): Description for reference (optional)
            ctx: MCP context for logging
        """
        data = {"elements": elements}
        response = await revit_post("/create_line/", data, ctx)
        return format_response(response)

    @mcp.tool()
    async def create_surface_based_element(
        elements: list[dict],
        ctx: Context = None,
    ) -> str:
        """Create floors, roofs, ceilings, and other surface-based building elements.

        Each element needs a closed boundary polygon (list of line segments) where
        the last point connects back to the first. All dimensions in millimeters.
        Supports batch creation.

        Args:
            elements: List of element definitions, each with:
                - element_type (str): "floor", "roof", or "ceiling" (required)
                - boundary (list[dict]): Array of {"p0": Point, "p1": Point} segments
                  forming a closed polygon (required, minimum 3 segments)
                - type_name (str): Family type name (optional)
                - level_name (str): Target level name (optional)
                - offset (float): Offset from level in mm (optional, defaults to 0)
                - name (str): Description for reference (optional)
            ctx: MCP context for logging
        """
        data = {"elements": elements}
        response = await revit_post("/create_surface/", data, ctx)
        return format_response(response)

    @mcp.tool()
    async def create_level(
        levels: list[dict],
        ctx: Context = None,
    ) -> str:
        """Create building levels (floor elevations) in Revit.

        Levels define the floor-to-floor heights of a building and must be
        created before placing walls, floors, or other level-dependent elements.

        Args:
            levels: List of level definitions, each with:
                - elevation (float): Elevation in mm from project origin (required)
                - name (str): Level name, e.g. "Ground Floor" (optional, auto-assigned)
            ctx: MCP context for logging
        """
        data = {"levels": levels}
        response = await revit_post("/create_level/", data, ctx)
        return format_response(response)
