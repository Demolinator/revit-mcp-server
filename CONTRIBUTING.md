# Contributing to Revit MCP Server

Thanks for your interest in improving this project! Whether you are a BIM
professional who found a bug, a Python developer who wants to add a tool, or
someone fixing a typo — contributions of every size are welcome.

This guide covers everything you need to go from "I have an idea" to a merged
pull request.

- [Ways to contribute](#ways-to-contribute)
- [How the project is built](#how-the-project-is-built)
- [Development setup](#development-setup)
- [The edit–reload loop](#the-editreload-loop)
- [Adding a new tool](#adding-a-new-tool)
- [Coding conventions](#coding-conventions)
- [Testing](#testing)
- [Submitting a pull request](#submitting-a-pull-request)
- [Reporting bugs and requesting features](#reporting-bugs-and-requesting-features)
- [Security](#security)
- [Related repositories](#related-repositories)

---

## Ways to contribute

You do **not** need Revit installed for many useful contributions:

| Contribution | Needs Revit? |
|---|---|
| Fix docs, README tables, `LLM.txt` | No |
| Improve tool docstrings (they are what the AI reads!) | No |
| Offline tests, CI, packaging, `main.py` / `tools/` logic | No |
| Fix or add route handlers in `revit_mcp/` | **Yes** (2024–2027) |
| Verify a bug report on your Revit version | **Yes** |

Good places to start:

- Issues labeled [`good first issue`](https://github.com/Demolinator/revit-mcp-server/labels/good%20first%20issue) — small, well-scoped, and documented.
- Issues labeled [`help wanted`](https://github.com/Demolinator/revit-mcp-server/labels/help%20wanted) — bigger items where help is especially appreciated.
- **Maintaining a fork with improvements?** Please consider upstreaming them.
  Several forks contain fixes (non-ASCII text handling, offline tests, new
  tools) that would benefit everyone. Small, focused PRs are much easier to
  review than one large merge.

If you plan a larger change (new tool family, architecture change, new
dependency), please **open an issue first** so we can agree on the approach
before you invest time.

---

## How the project is built

The project has **two halves that run in two different Python runtimes** and
talk over HTTP. Understanding this split is the single most important thing
for contributors.

```
AI client ──stdio/SSE/HTTP──▶ main.py + tools/        ──HTTP :48884──▶ startup.py + revit_mcp/ ──▶ Revit API
                              (CPython 3.11+, your PC)                  (IronPython 2.7, inside Revit)
```

| Part | Runtime | What it does |
|---|---|---|
| `main.py` | CPython 3.11+ | FastMCP server, shared HTTP client, transport selection |
| `tools/*_tools.py` | CPython 3.11+ | MCP tool definitions — thin wrappers that POST/GET to routes |
| `tools/utils.py` | CPython 3.11+ | `format_response()` turns route JSON into text for the AI |
| `startup.py` | IronPython 2.7 | pyRevit extension entry point; registers every route module |
| `revit_mcp/*.py` | IronPython 2.7 | pyRevit Routes handlers that call the Revit API |
| `revit_mcp/utils.py` | IronPython 2.7 | Shared helpers (ElementId compat, transactions, strings) |

Every tool therefore has **two pieces**: a tool in `tools/` and a route in
`revit_mcp/`. They are usually paired by module name (e.g.
`tools/mep_tools.py` ↔ `revit_mcp/mep.py`).

> **Important:** code in `revit_mcp/` and `startup.py` must be valid
> **IronPython 2.7**. See [Coding conventions](#coding-conventions).

---

## Development setup

### Prerequisites

- Windows 10/11 with **Autodesk Revit 2024, 2025, 2026, or 2027** (only needed for route work)
- [**pyRevit**](https://github.com/pyrevitlabs/pyRevit/releases) installed, with a build that supports your Revit version
- [**uv**](https://docs.astral.sh/uv/getting-started/installation/)
- Git

### 1. Fork and clone

```bash
# Fork on GitHub first, then:
git clone https://github.com/<your-username>/revit-mcp-server.git
cd revit-mcp-server
git remote add upstream https://github.com/Demolinator/revit-mcp-server.git
uv sync
```

Quick sanity check (works without Revit):

```bash
uv run python -c "import main; print('server imports OK')"
```

### 2. Point pyRevit at your clone (so edits are live)

Rather than copying files into `%APPDATA%`, register your working copy
directly so pyRevit loads the code you are editing:

1. Create a folder whose name ends in `.extension`, e.g.
   `C:\dev\pyrevit-ext\revit-mcp-dev.extension`, and make it a **directory
   junction** to your clone:

   ```powershell
   New-Item -ItemType Directory -Force C:\dev\pyrevit-ext | Out-Null
   New-Item -ItemType Junction -Path C:\dev\pyrevit-ext\revit-mcp-dev.extension -Target C:\path\to\revit-mcp-server
   ```

2. In Revit: **pyRevit tab → Settings → Custom Extension Directories** → add
   `C:\dev\pyrevit-ext` → **Save Settings and Reload**.
3. **pyRevit tab → Settings → Routes** → enable **Routes Server** → save.
4. Open any project and browse to <http://localhost:48884/revit_mcp/status/>.
   You should see `"status": "active"`.

> Make sure you don't also have the extension installed from the pyRevit
> Extensions manager, or two copies will fight over the same routes.

### 3. Connect an MCP client to your clone

The easiest way to exercise tools is the MCP Inspector:

```bash
uv run mcp dev main.py      # then open http://127.0.0.1:6274
```

Or point Claude Desktop / Claude Code / Cursor at your clone:

```json
{
  "mcpServers": {
    "revit-dev": {
      "command": "uv",
      "args": ["run", "--directory", "C:\\path\\to\\revit-mcp-server", "main.py"]
    }
  }
}
```

---

## The edit–reload loop

| You changed… | To pick it up… |
|---|---|
| `revit_mcp/*.py` or `startup.py` | **pyRevit tab → Reload** (no Revit restart needed) |
| `tools/*.py` or `main.py` | Restart the MCP server (restart Inspector / reconnect your client) |
| Both | Do both |

Tips:

- Test a route directly, without any AI in the loop:

  ```powershell
  curl http://localhost:48884/revit_mcp/status/
  curl -X POST http://localhost:48884/revit_mcp/save_document/ -H "Content-Type: application/json" -d "{}"
  ```

- Route errors and `logger` output appear in the **pyRevit output window** /
  pyRevit log file.
- If Revit shows a modal dialog, the Routes server is blocked until it is
  dismissed. Any transaction you open must call `suppress_warnings()` (see below).

---

## Adding a new tool

Adding a tool touches **four places** plus docs. Here's a minimal, complete
example for a hypothetical `count_walls` tool.

### 1. Route handler — `revit_mcp/<module>.py` (IronPython 2.7)

```python
# -*- coding: UTF-8 -*-
"""Wall Stats Module for Revit MCP"""

from pyrevit import routes, DB
import json
import logging

logger = logging.getLogger(__name__)


def register_wall_stats_routes(api):
    """Register wall statistics routes with the API."""

    @api.route("/count_walls/", methods=["POST"])
    def count_walls(doc, request):
        """
        Count walls, optionally on one level.

        Payload: {"level_name": "Level 1"}   (optional)
        """
        try:
            if not doc:
                return routes.make_response(
                    data={"error": "No active Revit document"}, status=503
                )

            data = {}
            if request and request.data:
                data = json.loads(request.data) if isinstance(request.data, str) else request.data
            level_name = data.get("level_name")

            walls = (
                DB.FilteredElementCollector(doc)
                .OfCategory(DB.BuiltInCategory.OST_Walls)
                .WhereElementIsNotElementType()
                .ToElements()
            )
            if level_name:
                walls = [w for w in walls
                         if doc.GetElement(w.LevelId) is not None
                         and doc.GetElement(w.LevelId).Name == level_name]

            return routes.make_response(data={
                "status": "success",
                "count": len(walls),
                "message": "Found {} walls".format(len(walls)),
            })
        except Exception as e:
            logger.error("count_walls failed: {}".format(str(e)))
            return routes.make_response(data={"error": str(e)}, status=500)

    logger.info("Wall stats routes registered successfully")
```

### 2. Register the route — `startup.py`

```python
        from revit_mcp.wall_stats import register_wall_stats_routes

        register_wall_stats_routes(api)
```

### 3. Tool definition — `tools/<module>_tools.py` (CPython 3.11+)

```python
# -*- coding: utf-8 -*-
"""Wall statistics tools"""

from mcp.server.fastmcp import Context
from .utils import format_response


def register_wall_stats_tools(mcp, revit_get, revit_post, revit_image=None):
    """Register wall statistics tools with the MCP server."""
    _ = revit_get, revit_image  # Acknowledge unused parameters

    @mcp.tool()
    async def count_walls(level_name: str = None, ctx: Context = None) -> str:
        """Count the walls in the active Revit model.

        Use this to get a quick wall count, either for the whole model or for
        a single level.

        Args:
            level_name: Name of a level to restrict the count to, e.g. "Level 1".
                Omit to count every wall in the model.
            ctx: MCP context for logging
        """
        response = await revit_post("/count_walls/", {"level_name": level_name}, ctx)
        return format_response(response)
```

> **The docstring is the tool's user interface.** The AI decides *when* and
> *how* to call your tool purely from its name, docstring, and argument
> descriptions. Be explicit about units (mm), valid values, and when to use
> this tool versus a similar one.

### 4. Register the tool — `tools/__init__.py`

Add both the import and the `register_*` call, following the existing pattern.

### 5. Update the docs

- Add a row to the right table in `README.md` and update the **tool count**
  in the headings, the intro line, and the "Supported Tools (N)" heading.
- Update `LLM.txt` if you added a module or changed an architectural convention.

Sanity check that code and README agree:

```bash
grep -c "@mcp.tool" tools/*.py | awk -F: '{s+=$2} END {print s " tools"}'
grep -h "@api.route" revit_mcp/*.py | wc -l
```

---

## Coding conventions

### IronPython 2.7 (`revit_mcp/`, `startup.py`)

These files run inside Revit and **cannot use Python 3 syntax**:

- ❌ No f-strings → use `"{}".format(x)`
- ❌ No type hints, no `async`/`await`, no walrus operator, no `pathlib`
- ❌ No `print()` to stdout for diagnostics → use `logger`
- ✅ Start each file with `# -*- coding: UTF-8 -*-`
- ✅ Import shared helpers as `from utils import ...` (matching existing modules)
- ✅ Parse payloads defensively — `request.data` may be a `str` or a `dict`

### Revit API rules

- **Units:** every tool accepts **millimeters**. Convert to Revit internal
  feet in the route (`mm / 304.8`). Never expose feet to the AI.
- **ElementIds:** always use `make_element_id()` and `get_element_id_value()`
  from `revit_mcp/utils.py`. They handle the `Int64` / `.Value` differences
  across 2024–2027. In Revit 2027 a bare `DB.ElementId(<int>)` can raise
  *"Multiple targets could match"*.
- **Transactions:** wrap model changes in a `DB.Transaction`, and call
  `suppress_warnings(t)` right after `t.Start()`. Otherwise a routine Revit
  warning opens a modal dialog and **hangs the Routes server**. Roll back on
  exceptions.
- **Don't open a transaction** around `doc.Save()` / `doc.SaveAs()`, exports,
  or pure reads.
- **Version differences:** prefer feature detection (`hasattr`, `try/except`)
  over version-number checks. Note in your PR which Revit versions you tested.

### Route response contract

`tools/utils.py::format_response()` relies on this shape:

| Outcome | Return |
|---|---|
| Success | `{"status": "success", "message": "...", ...data}` with HTTP 200 |
| Failure | `{"error": "human-readable reason", ...}` with 4xx/5xx |

Put an actionable hint in error messages ("provide a file_path…",
"level 'L9' not found; available: L1, L2") because the AI will read them and
retry.

### CPython side (`main.py`, `tools/`)

- Keep tools **thin**: validate/shape arguments, call `revit_get` / `revit_post`,
  return `format_response(...)`. Revit logic belongs in the route.
- Use `revit_post` for anything that changes the model; `revit_get` for reads.
- Match the existing `register_<x>_tools(mcp, revit_get, revit_post, revit_image=None)` signature.
- Tool names are `snake_case` verbs: `create_*`, `list_*`, `get_*`, `set_*`, …
  Check the README table to avoid overlapping an existing tool.

### General

- Match the style of the surrounding file; keep diffs focused.
- No new runtime dependencies without discussing in an issue first.

---

## Testing

The current tests in `tests/` are **integration checks that need a running
Revit** with the extension loaded and a project open. They are plain scripts
(not pytest tests):

```bash
uv run python tests/test_model_info_format.py   # needs Revit + open project
uv run python tests/test_init_latency.py        # stdio cold-start time
```

An offline test suite (mocked pyRevit / HTTP) and CI are tracked as open
issues, and contributions there are very welcome.

**Before opening a PR that touches `revit_mcp/`**, please manually verify in
Revit:

1. pyRevit reloads without errors, and `/revit_mcp/status/` returns `active`.
2. Your tool works via MCP Inspector or an AI client, **including one
   failure case** (bad ID, missing level, etc.) that returns a clear error.
3. No modal dialogs appeared, and Revit's **Undo** list shows a sensible entry.
4. Record the **Revit + pyRevit versions** you tested in the PR.

Changes that only touch `tools/`, `main.py`, or docs just need
`uv run python -c "import main"` to succeed.

---

## Submitting a pull request

1. **Sync** with upstream: `git fetch upstream && git checkout -b my-change upstream/master`
2. Make **one logical change per PR**. Separate refactors from features.
3. Write commits in [Conventional Commits](https://www.conventionalcommits.org/)
   style, as the history already does:
   - `feat: add count_walls tool`
   - `fix(placement): host doors on walls in Revit 2027`
   - `docs: correct tool counts in README`
   - `perf:`, `refactor:`, `test:`, `chore:` as appropriate
4. Push to your fork and open a PR against **`master`**. Fill in the PR
   template, especially the **tested Revit versions**.
5. A maintainer will review. Expect questions; they're how we keep 48+ tools
   reliable across four Revit versions. Push follow-up commits to the same
   branch.

By contributing, you agree that your contributions are licensed under the
project's [MIT License](LICENSE).

---

## Reporting bugs and requesting features

Use the [issue forms](https://github.com/Demolinator/revit-mcp-server/issues/new/choose).
The most useful bug reports include:

- Revit version (e.g. 2026.1) and pyRevit version
- MCP client (Claude Desktop, Claude Code, Cursor, …) and transport (stdio/HTTP)
- The tool name and the arguments that were sent
- The output of <http://localhost:48884/revit_mcp/status/>
- The full error text (the `=== ERROR DETAILS ===` block if present)

Please don't attach confidential project models. A minimal repro in a new
project from the default template is ideal.

---

## Security

`execute_revit_code` runs arbitrary IronPython inside Revit, and pyRevit
Routes has no authentication. Only expose the server on `localhost` or
behind a trusted tunnel. If you find a security problem, please **don't open
a public issue**. See [SECURITY.md](SECURITY.md).

---

## Related repositories

- **[Demolinator/revit-mcp-plugin](https://github.com/Demolinator/revit-mcp-plugin)** —
  a Claude plugin (skills, slash commands, one-click setup scripts) that
  **bundles a copy of this server** under `revit-bim/mcp-server/`.
  Server changes (tools, routes, `main.py`) should be made **here first** and
  are then synced into the plugin. Changes to skills, commands, or setup scripts
  belong in the plugin repo.
- **[pyRevit](https://github.com/pyrevitlabs/pyRevit)** — the Routes framework
  this server builds on.

---

Questions? Open an issue with the `question` label. We're happy to help you
get your first contribution in. 🏗️
