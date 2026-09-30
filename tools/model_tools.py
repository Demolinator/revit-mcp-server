# -*- coding: utf-8 -*-
"""Model structure tools."""

from .utils import Context, format_response


def register_model_tools(mcp, revit_get):
    """Register list_levels."""

    @mcp.tool()
    async def list_levels(ctx: Context = None) -> str:
        """List every level in the model with its name, ID, and elevation (mm and feet).

        Use the returned level names wherever another tool asks for a
        ``level_name``.
        """
        return format_response(await revit_get("/list_levels/", ctx))
