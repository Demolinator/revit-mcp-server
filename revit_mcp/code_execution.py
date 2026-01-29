# -*- coding: UTF-8 -*-
"""
Code Execution Module for Revit MCP
Handles direct execution of IronPython code in Revit context.
"""
from pyrevit import routes, revit, DB
import json
import logging
import sys
import traceback
from StringIO import StringIO

# Standard logger setup
logger = logging.getLogger(__name__)


def register_code_execution_routes(api):
    """Register code execution routes with the API."""

    @api.route("/execute_code/", methods=["POST"])
    def execute_code(doc, request):
        """
        Execute IronPython code in Revit context.

        Expected payload:
        {
            "code": "python code as string",
            "description": "optional description of what the code does"
        }
        """
        try:
            # Parse the request data
            data = (
                json.loads(request.data)
                if isinstance(request.data, str)
                else request.data
            )
            code_to_execute = data.get("code", "")
            description = data.get("description", "Code execution")

            if not code_to_execute:
                return routes.make_response(
                    data={"error": "No code provided"}, status=400
                )

            logger.info("Executing code: {}".format(description))

            # Create a transaction for any model modifications
            t = DB.Transaction(doc, "MCP Code Execution: {}".format(description))
            t.Start()

            try:
                # Capture stdout to return any print statements
                old_stdout = sys.stdout
                captured_output = StringIO()
                sys.stdout = captured_output

                # Create a namespace with common Revit objects available
                namespace = {
                    "doc": doc,
                    "DB": DB,
                    "revit": revit,
                    "__builtins__": __builtins__,
                    "print": lambda *args: captured_output.write(
                        " ".join(str(arg) for arg in args) + "\n"
                    ),
                }

                # Execute the code
                exec(code_to_execute, namespace)

                # Restore stdout
                sys.stdout = old_stdout

                # Get any printed output
                output = captured_output.getvalue()
                captured_output.close()

                # Commit the transaction
                t.Commit()

                return routes.make_response(
                    data={
                        "status": "success",
                        "description": description,
                        "output": (
                            output
                            if output
                            else "Code executed successfully (no output)"
                        ),
                        "code_executed": code_to_execute,
                    }
                )

            except Exception as exec_error:
                # Restore stdout if something went wrong
                sys.stdout = old_stdout

                # Capture any partial output before the error
                partial_output = captured_output.getvalue()
                captured_output.close()

                # Rollback transaction if it's still active
                if t.HasStarted() and not t.HasEnded():
                    t.RollBack()

                # Get the full traceback
                error_traceback = traceback.format_exc()

                # Build enhanced error message with hints
                error_type = type(exec_error).__name__
                error_msg = str(exec_error)
                enhanced_message = "{}: {}".format(error_type, error_msg)

                # Add helpful hints for common errors
                hints = []
                if error_type == "AttributeError":
                    if error_msg == "Name" or "Name" in error_msg:
                        hints.append(
                            "The 'Name' property may not be directly accessible in IronPython. "
                            "Try using getattr(element, 'Name', 'N/A') or "
                            "element.get_Parameter(DB.BuiltInParameter.ALL_MODEL_TYPE_NAME).AsString()"
                        )
                    else:
                        hints.append(
                            "Some Revit API properties are not directly accessible in IronPython. "
                            "Try using getattr(obj, 'property_name', default_value) for safe access."
                        )
                elif error_type == "NullReferenceException" or "NoneType" in error_msg:
                    hints.append(
                        "An object is None/null. Ensure you check if elements exist before "
                        "accessing their properties: 'if element:' or 'if element is not None:'"
                    )
                elif error_type == "InvalidOperationException":
                    hints.append(
                        "This operation may require being inside a transaction, or the element "
                        "may be in a state that doesn't allow this operation."
                    )
                elif "Transaction" in error_msg or "transaction" in error_msg:
                    hints.append(
                        "Transaction error. Note that this endpoint already wraps your code "
                        "in a transaction. Avoid starting nested transactions."
                    )

                logger.error("Code execution failed: {}".format(enhanced_message))
                logger.error("Traceback: {}".format(error_traceback))

                response_data = {
                    "status": "error",
                    "error": enhanced_message,
                    "error_type": error_type,
                    "traceback": error_traceback,
                    "code_attempted": code_to_execute,
                }

                if partial_output:
                    response_data["partial_output"] = partial_output

                if hints:
                    response_data["hints"] = hints

                return routes.make_response(
                    data=response_data,
                    status=500,
                )

        except Exception as e:
            logger.error("Execute code request failed: {}".format(str(e)))
            return routes.make_response(data={"error": str(e)}, status=500)

    logger.info("Code execution routes registered successfully.")
