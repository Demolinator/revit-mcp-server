# -*- coding: utf-8 -*-
"""Annotation tools — dimensions and wall tags"""

from mcp.server.fastmcp import Context
from .utils import format_response


def register_annotation_tools(mcp, revit_get, revit_post, revit_image=None):
    """Register annotation tools with the MCP server."""
    _ = revit_image  # Acknowledge unused parameter

    @mcp.tool()
    async def create_dimensions(
        element_ids: list[int],
        dimension_type: str = "linear",
        ctx: Context = None,
    ) -> str:
        """Create dimension annotations for elements in the current view.

        Automatically dimensions the specified elements. Works in plan, section,
        and elevation views. The dimension line is placed at an offset from the
        elements for readability.

        Args:
            element_ids: List of element IDs to dimension
            dimension_type: Type of dimension — "linear", "aligned", or "angular"
                (defaults to "linear")
            ctx: MCP context for logging
        """
        data = {"element_ids": element_ids, "dimension_type": dimension_type}
        response = await revit_post("/create_dimensions/", data, ctx)
        return format_response(response)

    @mcp.tool()
    async def tag_walls(
        use_leader: bool = False,
        tag_type_name: str = None,
        ctx: Context = None,
    ) -> str:
        """Tag all untagged walls in the current Revit view.

        Places wall tags on every wall visible in the active view that doesn't
        already have a tag. Tags are centered on each wall segment.

        Args:
            use_leader: Whether to show leader lines (defaults to False)
            tag_type_name: Specific wall tag family type name (optional, uses first available)
            ctx: MCP context for logging
        """
        data = {"use_leader": use_leader, "tag_type_name": tag_type_name}
        response = await revit_post("/tag_walls/", data, ctx)
        return format_response(response)
