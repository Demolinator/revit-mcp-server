# -*- coding: utf-8 -*-
"""Editing tools — delete, modify, and select elements"""

from mcp.server.fastmcp import Context
from .utils import format_response


def register_editing_tools(mcp, revit_get, revit_post, revit_image=None):
    """Register editing tools with the MCP server."""
    _ = revit_image  # Acknowledge unused parameter

    @mcp.tool()
    async def delete_elements(
        element_ids: list[int],
        ctx: Context = None,
    ) -> str:
        """Delete one or more elements from the Revit model.

        Removes elements by their IDs. If a deleted element hosts other elements
        (e.g., a wall with doors), the hosted elements are also deleted (cascade).
        All deletions happen in a single transaction — if any fails, none are deleted.

        Args:
            element_ids: List of Revit element IDs to delete
            ctx: MCP context for logging
        """
        data = {"element_ids": element_ids}
        response = await revit_post("/delete_elements/", data, ctx)
        return format_response(response)

    @mcp.tool()
    async def modify_element(
        element_id: int,
        parameters: dict,
        ctx: Context = None,
    ) -> str:
        """Modify parameter values on a Revit element.

        Changes one or more instance parameters on the specified element.
        Returns old and new values for confirmation.

        Args:
            element_id: Revit element ID to modify
            parameters: Dictionary of parameter name to new value pairs
                e.g., {"Mark": "EW-01", "Comments": "Updated via MCP"}
            ctx: MCP context for logging
        """
        data = {"element_id": element_id, "parameters": parameters}
        response = await revit_post("/modify_element/", data, ctx)
        return format_response(response)

    @mcp.tool()
    async def get_selected_elements(
        ctx: Context = None,
    ) -> str:
        """Get details of elements currently selected in the Revit UI.

        Returns IDs, categories, types, and key parameters of all elements
        the user has selected in Revit. Returns an empty list if nothing
        is selected (not an error).

        Args:
            ctx: MCP context for logging
        """
        response = await revit_get("/selected_elements/", ctx)
        return format_response(response)
