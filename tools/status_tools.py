# -*- coding: utf-8 -*-
"""Connection health and model overview tools."""

from .utils import Context, format_response


def register_status_tools(mcp, revit_get):
    """Register get_revit_status and get_revit_model_info."""

    @mcp.tool()
    async def get_revit_status(ctx: Context) -> str:
        """Check that Revit is reachable and has a project open.

        Call this first when starting a session or when other tools fail, to
        tell connection problems apart from modelling problems.
        """
        return format_response(await revit_get("/status/", ctx, timeout=10.0))

    @mcp.tool()
    async def get_revit_model_info(ctx: Context) -> str:
        """Summarize the open Revit model.

        Returns project information, levels, element counts by category,
        rooms, view and sheet counts, linked models, and warnings. Useful for
        orienting yourself before creating or editing elements.
        """
        return format_response(await revit_get("/model_info/", ctx))
