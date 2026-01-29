# -*- coding: utf-8 -*-
"""Code execution tools for the MCP server."""

from mcp.server.fastmcp import Context
from .utils import format_response


def register_code_execution_tools(mcp, revit_get, revit_post, revit_image=None):
    """Register code execution tools with the MCP server."""
    # Note: revit_get and revit_image are unused but kept for interface consistency
    _ = revit_get, revit_image  # Acknowledge unused parameters

    @mcp.tool()
    async def execute_revit_code(
        code: str, description: str = "Code execution", ctx: Context = None
    ) -> str:
        """
        Execute IronPython code directly in Revit context.

        This tool allows you to send IronPython 2.7.12 code to be executed inside Revit.
        The code has access to:
        - doc: The active Revit document
        - DB: Revit API Database namespace
        - revit: pyRevit module
        - print: Function to output text (returned in response)

        Use this when the existing MCP tools cannot accomplish what you need.

        Args:
            code: The IronPython code to execute (as a string)
            description: Optional description of what the code does
            ctx: MCP context for logging

        Returns:
            Execution results including any output or errors

        Example:
            code = '''
                    # encoding: utf-8
                    # Hello World example
                    print("Hello from Revit!")
                    from pyrevit import revit, DB, forms, script
                    output = script.get_output()
                    output.close_others()
                    doc = revit.doc
                    print("Document title:", doc.Title)
                    print("Number of walls:", len(list(DB.FilteredElementCollector(doc).OfCategory(DB.BuiltInCategory.OST_Walls).WhereElementIsNotElementType())))
                    collector = DB.FilteredElementCollector(doc).OfClass(DB.TextNoteType).ToElements()
                    print("Number of text note types:", len(collector))
                    '''
                    
        Tips for writing IronPython code in Revit:
        -----------------------------------------
        1. Accessing Element.Name property:
           Some Revit elements don't expose the 'Name' property directly in IronPython.
           Use defensive access patterns:

           # Option 1: Use getattr with a default value
           name = getattr(element, 'Name', 'N/A')

           # Option 2: Use try-except
           try:
               name = element.Name
           except AttributeError:
               name = 'Unable to retrieve name'

           # Option 3: Use BuiltInParameter for element types
           param = element_type.get_Parameter(DB.BuiltInParameter.ALL_MODEL_TYPE_NAME)
           name = param.AsString() if param else 'N/A'

        2. Always check if elements exist before accessing properties:
           element = doc.GetElement(element_id)
           if element:
               # Safe to access element properties

        3. Use hasattr() before accessing optional properties:
           if hasattr(element_type, 'FamilyName'):
               family_name = element_type.FamilyName

        4. The Tool already wraps the code around a transaction.
        """
        try:
            payload = {"code": code, "description": description}

            if ctx:
                await ctx.info("Executing code: {}".format(description))

            response = await revit_post("/execute_code/", payload, ctx)
            return format_response(response)

        except (ConnectionError, ValueError, RuntimeError) as e:
            error_msg = "Error during code execution: {}".format(str(e))
            if ctx:
                await ctx.error(error_msg)
            return error_msg
