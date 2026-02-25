# -*- coding: utf-8 -*-
"""Documentation tools — sheets, schedules, and document export"""

from mcp.server.fastmcp import Context
from .utils import format_response


def register_documentation_tools(mcp, revit_get, revit_post, revit_image=None):
    """Register documentation tools with the MCP server."""
    _ = revit_image  # Acknowledge unused parameter

    @mcp.tool()
    async def create_sheet(
        sheet_number: str = None,
        sheet_name: str = "Unnamed Sheet",
        title_block_name: str = None,
        ctx: Context = None,
    ) -> str:
        """Create a drawing sheet in Revit for construction documentation.

        Sheets are the printable output of a Revit project. Each sheet has a
        title block, sheet number, and name. Views can be placed on sheets
        after creation.

        Args:
            sheet_number: Sheet number, e.g. "A101" (optional, auto-assigned)
            sheet_name: Sheet title, e.g. "Ground Floor Plan" (defaults to "Unnamed Sheet")
            title_block_name: Title block family name (optional, uses first available)
            ctx: MCP context for logging
        """
        data = {
            "sheet_number": sheet_number,
            "sheet_name": sheet_name,
            "title_block_name": title_block_name,
        }
        response = await revit_post("/create_sheet/", data, ctx)
        return format_response(response)

    @mcp.tool()
    async def create_schedule(
        category: str,
        fields: list[str] = None,
        schedule_name: str = None,
        ctx: Context = None,
    ) -> str:
        """Create a schedule (quantity takeoff view) for a specific element category.

        Schedules tabulate element data — e.g., a wall schedule showing all walls
        with their types, lengths, and areas. The schedule appears as a new view
        in the Revit project browser.

        Args:
            category: BuiltInCategory name, e.g. "OST_Walls", "OST_Rooms" (required)
            fields: Parameter names to include as columns (optional, uses default set)
                e.g., ["Family and Type", "Length", "Area", "Mark"]
            schedule_name: Name for the schedule view (optional, auto-generated)
            ctx: MCP context for logging
        """
        data = {
            "category": category,
            "fields": fields,
            "schedule_name": schedule_name,
        }
        response = await revit_post("/create_schedule/", data, ctx)
        return format_response(response)

    @mcp.tool()
    async def export_document(
        view_name: str = None,
        format: str = "pdf",
        resolution: int = 300,
        ctx: Context = None,
    ) -> str:
        """Export a Revit view or sheet to PDF or image format.

        Exports the specified view (or the active view if none specified) to a
        file on disk. Supported formats: PDF, PNG, JPG, DWG.

        Args:
            view_name: Name of the view or sheet to export (optional, uses active view)
            format: Output format — "pdf", "png", "jpg", or "dwg" (defaults to "pdf")
            resolution: DPI for image formats (defaults to 300, ignored for PDF/DWG)
            ctx: MCP context for logging
        """
        data = {
            "view_name": view_name,
            "format": format,
            "resolution": resolution,
        }
        response = await revit_post("/export_document/", data, ctx)
        return format_response(response)
