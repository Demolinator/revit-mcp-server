# -*- coding: utf-8 -*-
"""View inspection and image export tools."""

from typing import Union

from mcp.server.fastmcp import Image

from .utils import Context, format_response


def register_view_tools(mcp, revit_get, revit_post, revit_image):
    """Register view listing, inspection, and image export tools."""
    del revit_post  # not needed by these tools

    @mcp.tool()
    async def get_revit_view(view_name: str, ctx: Context = None) -> Union[Image, str]:
        """Render a Revit view to a PNG image so you can see it.

        Args:
            view_name: Exact view name as returned by list_revit_views,
                e.g. "Level 1" or "{3D}".
        """
        return await revit_image("/get_view/{}".format(view_name), ctx)

    @mcp.tool()
    async def list_revit_views(ctx: Context = None) -> str:
        """List the views that can be exported as images, grouped by view type."""
        return format_response(await revit_get("/list_views/", ctx))

    @mcp.tool()
    async def get_current_view_info(ctx: Context = None) -> str:
        """Describe the view currently open in Revit.

        Returns its name, type, ID, and whether it is a template. Check this
        before view-specific tools such as tagging or detail lines.
        """
        return format_response(await revit_get("/current_view_info/", ctx))

    @mcp.tool()
    async def get_current_view_elements(ctx: Context = None) -> str:
        """List the elements visible in the current view, with IDs and categories.

        Use the returned element IDs with editing, tagging, or property tools.
        """
        return format_response(await revit_get("/current_view_elements/", ctx))
