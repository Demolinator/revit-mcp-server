# -*- coding: utf-8 -*-
"""Structure tools — grids and structural framing"""

from .utils import Context, format_response


def register_structure_tools(mcp, revit_get, revit_post, revit_image=None):
    """Register structure tools with the MCP server."""
    _ = revit_image  # Acknowledge unused parameter

    @mcp.tool()
    async def create_grid(
        grids: list[dict],
        ctx: Context = None,
    ) -> str:
        """Create grid lines for the structural layout of a building.

        Grids define the column grid system. Each grid is a line from start to end
        point (in millimeters). Names auto-assign (A, B, C... or 1, 2, 3...) if
        not provided. Supports batch creation.

        Args:
            grids: List of grid definitions, each with:
                - start_point (dict): {"x": float, "y": float, "z": float} in mm (required)
                - end_point (dict): {"x": float, "y": float, "z": float} in mm (required)
                - name (str): Grid line name (optional, auto-assigned)
            ctx: MCP context for logging
        """
        data = {"grids": grids}
        response = await revit_post("/create_grid/", data, ctx)
        return format_response(response)

    @mcp.tool()
    async def create_structural_framing(
        elements: list[dict],
        ctx: Context = None,
    ) -> str:
        """Create structural beams and framing elements in Revit.

        Beams are placed along a line between two points, positioned at the
        given level's elevation (like walls/floors). The point `z` is an offset
        from that level — so pass z=0 to put the beam on the level, or a small
        z for a drop/raise relative to it. All dimensions in millimeters.
        Supports batch creation.

        Args:
            elements: List of beam definitions, each with:
                - start_point (dict): {"x": float, "y": float, "z": float} in mm (required; z is offset from level)
                - end_point (dict): {"x": float, "y": float, "z": float} in mm (required; z is offset from level)
                - type_name (str): Beam family type name (optional)
                - level_name (str): Target level name — sets the beam elevation (optional)
                - name (str): Description for reference (optional)
            ctx: MCP context for logging
        """
        data = {"elements": elements}
        response = await revit_post("/create_framing/", data, ctx)
        return format_response(response)
