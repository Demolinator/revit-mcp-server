# -*- coding: utf-8 -*-
"""Color-by-parameter visualization tools."""

from typing import List, Optional

from .utils import Context, format_response


def register_colors_tools(mcp, revit_get, revit_post):
    """Register color_splash, clear_colors, and list_category_parameters."""
    del revit_get  # not needed by these tools

    @mcp.tool()
    async def color_splash(
        category_name: str,
        parameter_name: str,
        use_gradient: bool = False,
        custom_colors: Optional[List[str]] = None,
        ctx: Context = None,
    ) -> str:
        """Color elements of a category in the active view by a parameter's value.

        Every distinct value gets its own color, which makes patterns (fire
        ratings, departments, levels, types…) visible at a glance.

        Args:
            category_name: Revit category, e.g. "Walls", "Rooms", "Doors".
            parameter_name: Parameter to color by; list_category_parameters
                shows the options.
            use_gradient: Blend colors along a gradient instead of using
                distinct colors (best for numeric parameters).
            custom_colors: Optional hex colors to use in order, e.g.
                ["#FF0000", "#00AA00"].
        """
        payload = {
            "category_name": category_name,
            "parameter_name": parameter_name,
            "use_gradient": use_gradient,
        }
        if custom_colors:
            payload["custom_colors"] = custom_colors
        return format_response(await revit_post("/color_splash/", payload, ctx))

    @mcp.tool()
    async def clear_colors(category_name: str, ctx: Context = None) -> str:
        """Remove color overrides from a category in the active view.

        Args:
            category_name: Revit category previously colored, e.g. "Walls".
        """
        return format_response(
            await revit_post("/clear_colors/", {"category_name": category_name}, ctx)
        )

    @mcp.tool()
    async def list_category_parameters(category_name: str, ctx: Context = None) -> str:
        """List the parameters available on elements of a category.

        Use this before color_splash, ai_element_filter, or set_parameter to
        find the exact parameter name.

        Args:
            category_name: Revit category, e.g. "Walls", "Doors", "Rooms".
        """
        return format_response(
            await revit_post("/list_category_parameters/", {"category_name": category_name}, ctx)
        )
