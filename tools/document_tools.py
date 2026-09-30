# -*- coding: utf-8 -*-
"""Document tools — saving and persistence"""

from .utils import Context, format_response


def register_document_tools(mcp, revit_get, revit_post, revit_image=None):
    """Register document persistence tools with the MCP server."""
    _ = revit_image  # Acknowledge unused parameter

    @mcp.tool()
    async def save_document(
        file_path: str = None,
        overwrite: bool = True,
        ctx: Context = None,
    ) -> str:
        """Save the active Revit document to disk so work persists.

        If file_path is given (or the document was started from a template and
        has never been saved), performs Save As to that path. Otherwise saves
        the document in place. Use this to persist a model before closing or
        restarting Revit.

        Args:
            file_path: Full .rvt path to save to, e.g. "C:\\Models\\ESB.rvt"
                (required the first time a template-based model is saved)
            overwrite: Overwrite an existing file at that path (defaults to True)
            ctx: MCP context for logging
        """
        data = {"file_path": file_path, "overwrite": overwrite}
        response = await revit_post("/save_document/", data, ctx)
        return format_response(response)
