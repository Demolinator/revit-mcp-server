# -*- coding: utf-8 -*-
"""Room creation tools — rooms and room separation lines"""

from mcp.server.fastmcp import Context
from .utils import format_response


def register_room_tools(mcp, revit_get, revit_post, revit_image=None):
    """Register room tools with the MCP server."""
    _ = revit_image  # Acknowledge unused parameter

    @mcp.tool()
    async def create_room(
        level_name: str,
        location: dict = None,
        name: str = None,
        number: str = None,
        ctx: Context = None,
    ) -> str:
        """Create a room in the Revit model at a specified level.

        Rooms must be placed inside enclosed areas (bounded by walls or room
        separation lines). If no location is given, Revit auto-places the room.

        Args:
            level_name: Target level name (e.g., "Level 1")
            location: Optional placement point {"x": float, "y": float} in mm
            name: Room name (e.g., "Living Room")
            number: Room number (e.g., "101")
            ctx: MCP context for logging
        """
        data = {"level_name": level_name}
        if location is not None:
            data["location"] = location
        if name is not None:
            data["name"] = name
        if number is not None:
            data["number"] = number
        response = await revit_post("/create_room/", data, ctx)
        return format_response(response)

    @mcp.tool()
    async def create_room_separation(
        lines: list[dict],
        level_name: str = None,
        view_name: str = None,
        ctx: Context = None,
    ) -> str:
        """Create room separation lines to define room boundaries.

        Room separation lines act as invisible walls for room calculation.
        Use these when physical walls don't fully enclose a space (e.g.,
        open-plan areas, corridors). All coordinates in millimeters.

        Args:
            lines: List of line segments, each with:
                - start_point (dict): {"x": float, "y": float, "z": float} in mm
                - end_point (dict): {"x": float, "y": float, "z": float} in mm
            level_name: Target level name (defaults to active view's level)
            view_name: Plan view name (defaults to active view)
            ctx: MCP context for logging
        """
        data = {"lines": lines}
        if level_name is not None:
            data["level_name"] = level_name
        if view_name is not None:
            data["view_name"] = view_name
        response = await revit_post("/create_room_separation/", data, ctx)
        return format_response(response)
