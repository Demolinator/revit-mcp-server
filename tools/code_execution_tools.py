# -*- coding: utf-8 -*-
"""Escape hatch: run IronPython inside Revit."""

from .utils import Context, format_response


def register_code_execution_tools(mcp, revit_get, revit_post, revit_image):
    """Register execute_revit_code."""
    del revit_get, revit_image  # not needed by this tool

    @mcp.tool()
    async def execute_revit_code(
        code: str, description: str = "Code execution", ctx: Context = None
    ) -> str:
        """Run IronPython 2.7 code inside Revit and return what it prints.

        Only use this when no dedicated tool can do the job. The code runs
        inside a single transaction that is committed on success and rolled
        back on error, so do not start your own Transaction.

        Available names: ``doc`` (active Document), ``DB`` (Autodesk.Revit.DB),
        ``revit`` (pyRevit helpers), ``System``, ``clr``, and ``print`` (its
        output is returned to you).

        IronPython 2.7 rules:
        * no f-strings; use "{}".format(...)
        * Revit stores lengths in feet; divide millimeters by 304.8
        * build element IDs as DB.ElementId(System.Int64(n)); a bare int is
          ambiguous in Revit 2027
        * some elements lack ``.Name``; read it defensively, e.g.
          getattr(el, "Name", None) or the ALL_MODEL_TYPE_NAME parameter
        * check doc.GetElement(...) for None before using the result

        Example:
            walls = DB.FilteredElementCollector(doc) \\
                .OfCategory(DB.BuiltInCategory.OST_Walls) \\
                .WhereElementIsNotElementType().ToElements()
            print("walls: {}".format(len(walls)))

        Args:
            code: IronPython source to execute.
            description: Short label; it becomes the transaction name shown
                in Revit's Undo menu.
        """
        if ctx:
            await ctx.info("Running Revit code: {}".format(description))
        payload = {"code": code, "description": description}
        return format_response(await revit_post("/execute_code/", payload, ctx))
