## What does this PR do?

<!-- One or two sentences. Link the issue it closes, e.g. "Closes #12". -->

## Type of change

- [ ] Bug fix
- [ ] New tool
- [ ] Improvement to an existing tool
- [ ] Docs / tests / CI / refactor

## How was it tested?

<!-- Which Revit versions did you test in? Check all that apply. -->

- [ ] Revit 2024
- [ ] Revit 2025
- [ ] Revit 2026
- [ ] Revit 2027
- [ ] Not tested in Revit (docs / `tools/` / `main.py` only)

pyRevit version:
MCP client used:

<!-- Describe what you ran (prompts, tool calls, curl requests) and the result. For new tools, include one failure case. -->

## Checklist

- [ ] `revit_mcp/` code is IronPython 2.7-compatible (no f-strings or type hints)
- [ ] Model changes are in a transaction with `suppress_warnings()`; lengths are in mm
- [ ] ElementIds use `make_element_id()` / `get_element_id_value()`
- [ ] New routes are registered in `startup.py`, new tools in `tools/__init__.py`
- [ ] README tool tables/counts (and `LLM.txt`, if relevant) are updated
- [ ] `uv run pytest` passes (tool contract regenerated if tools changed on purpose)
