# Revit MCP Server

MCP server for Autodesk Revit 2024/2025/2026/2027 via pyRevit — 48 tools for building design, editing, analysis, clash detection, MEP, interop, documentation, and model persistence.

Works with any MCP client: Claude Desktop, Claude Code, Cursor, Windsurf, Copilot, or any other MCP-compatible application.

## How It Works

```
AI Client ──stdio/SSE/HTTP──> MCP Server (Python/FastMCP) ──HTTP :48884──> pyRevit Routes ──> Revit API
```

The MCP server runs on your machine and communicates with Revit through pyRevit's Routes API. Any MCP-compatible AI client can connect to it.

## Prerequisites

| Requirement | Details |
|-------------|---------|
| **Windows 10/11** | Revit is Windows-only |
| **Autodesk Revit** | 2024, 2025, 2026, or 2027 |
| **pyRevit** | Installed and loaded in Revit |
| **uv** | Python package manager ([install](https://docs.astral.sh/uv/getting-started/installation/)) |
| **A project open in Revit** | Tools require an active document |

## Install pyRevit (if not already installed)

pyRevit is a free add-in that lets scripts run inside Revit. This MCP server needs it to communicate with Revit.

1. Go to https://github.com/pyrevitlabs/pyRevit/releases
2. Download the latest **.exe installer** (e.g. `pyRevit_CLI_x.x.x.x_admin_signed.exe`)
3. Run the installer — accept all defaults, click **Next** through each screen
4. Open (or restart) Revit — you should see a **pyRevit** tab in the ribbon at the top
5. In the pyRevit tab, click **Settings** (gear icon)
6. In the Settings window, go to the **Routes** section on the left
7. Check the box to **Enable Routes Server**
8. Click **Save Settings** and let pyRevit reload

To verify: open a browser and go to `http://localhost:48884/` — you should see a response (not a "connection refused" error).

## Quick Start

### 1. Get the code

```bash
git clone https://github.com/Demolinator/revit-mcp-server.git
cd revit-mcp-server
uv sync
```

### 2. Load the extension into pyRevit

`startup.py` and `revit_mcp/` run **inside Revit**, so pyRevit has to load this folder as an extension.

> Don't install "MCP Server for Revit Python" from the pyRevit Extensions manager. That entry installs the original upstream project, which lacks most of the 48 routes this server calls.

1. Pick a folder for your pyRevit extensions, e.g. `C:\pyRevitExtensions`.
2. Link this repo into it under a name ending in `.extension` (a junction keeps it updated whenever you `git pull`):
   ```powershell
   New-Item -ItemType Junction -Path C:\pyRevitExtensions\revit-mcp.extension -Target C:\path\to\revit-mcp-server
   ```
   (Copying the folder there with that name works too; you'll just need to copy it again after updates.)
3. In Revit: **pyRevit tab → Settings → Custom Extension Directories** → add `C:\pyRevitExtensions`.
4. In the same Settings window, under **Routes**, turn on **Routes Server** (port `48884`).
5. **Save Settings and Reload.**

### 3. Check Revit is answering

With a project open, browse to <http://localhost:48884/revit_mcp/status/>. A working setup answers with `"status": "active"` and your project's title. A 404 means the extension isn't loaded; "can't reach this page" means Routes is off or Revit is closed.

### 4. Connect your AI client

Most desktop clients start the server themselves over stdio. Add this to the client's MCP configuration (for Claude Desktop: `claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "revit": {
      "command": "uv",
      "args": ["run", "--directory", "C:\path\to\revit-mcp-server", "main.py"]
    }
  }
}
```

For Claude Code: `claude mcp add revit -- uv run --directory C:\path\to\revit-mcp-server main.py`

Clients that connect over HTTP instead (some Cursor/Windsurf setups, remote clients) need the server started separately:

```bash
uv run main.py --http        # then point the client at http://127.0.0.1:8000/mcp
```

| Start with | Protocol | Served at |
|---|---|---|
| `uv run main.py` | stdio (default) | the client's stdin/stdout |
| `--http` (alias `--streamable-http`) | Streamable HTTP | `/mcp` |
| `--sse` | Server-Sent Events (older clients) | `/sse` and `/messages/` |
| `--combined` | Streamable HTTP + SSE together | all of the above |

### Configuration

Set these environment variables (or the `env` block of your MCP client config) to change the defaults:

| Variable | Default | Purpose |
|---|---|---|
| `REVIT_HOST` | `localhost` | Machine running Revit + pyRevit Routes |
| `REVIT_PORT` | `48884` | pyRevit Routes port |
| `MCP_HOST` | `127.0.0.1` | Bind address for `--http` / `--sse` / `--combined` |
| `MCP_PORT` | `8000` | Port for `--http` / `--sse` / `--combined` |

Keep `MCP_HOST` on `127.0.0.1` unless you understand the risks in [SECURITY.md](SECURITY.md).

### Try tools without an AI client

```bash
uv run mcp dev main.py       # opens the MCP Inspector at http://127.0.0.1:6274
```

## Supported Tools (48)

### Create (15)

| Tool | Description |
|------|-------------|
| `create_level` | Create new levels with elevations |
| `create_line_based_element` | Create walls, beams, and other line-based elements |
| `create_surface_based_element` | Create floors, roofs, and surface elements |
| `place_family` | Place a family instance at specified location |
| `create_grid` | Create column grid lines |
| `create_structural_framing` | Create structural beams and framing |
| `create_sheet` | Create new drawing sheets |
| `create_schedule` | Create schedules with custom fields |
| `create_room` | Create rooms at specified levels |
| `create_room_separation` | Create room separation boundary lines |
| `create_duct` | Create ducts between two points (MEP) |
| `create_pipe` | Create pipes between two points (MEP) |
| `create_mep_system` | Create mechanical or piping systems |
| `create_detail_line` | Create view-specific detail lines |
| `create_view` | Create floor plans, sections, elevations, 3D views |

### Query (12)

| Tool | Description |
|------|-------------|
| `get_revit_status` | Check if the API is active and responding |
| `get_revit_model_info` | Get model information |
| `list_levels` | Get all levels with elevations |
| `list_families` | Get available family types |
| `list_family_categories` | Get all family categories |
| `get_revit_view` | Export a view as an image |
| `list_revit_views` | List all exportable views |
| `get_current_view_info` | Get active view details |
| `get_current_view_elements` | Get elements in current view |
| `get_selected_elements` | Get currently selected elements |
| `list_category_parameters` | List parameters for a category |
| `get_element_properties` | Get all parameters and properties of an element |

### Modify (9)

| Tool | Description |
|------|-------------|
| `delete_elements` | Delete elements from the model |
| `modify_element` | Modify element parameter values |
| `color_splash` | Color elements by parameter values |
| `clear_colors` | Reset element colors |
| `tag_walls` | Tag all walls in current view |
| `set_parameter` | Set a single parameter value on an element |
| `tag_elements` | Tag specific elements with annotation symbols |
| `transform_elements` | Move, copy, rotate, or mirror elements |
| `set_active_view` | Switch the active view in Revit |

### Analyze (5)

| Tool | Description |
|------|-------------|
| `ai_element_filter` | Filter elements by category and parameters |
| `export_room_data` | Export room areas, volumes, boundaries |
| `get_material_quantities` | Material takeoff data |
| `check_clashes` | Detect hard clashes (interferences) between disciplines, e.g. structure vs MEP |
| `analyze_model_statistics` | Element counts and model stats |

### Document (2)

| Tool | Description |
|------|-------------|
| `create_dimensions` | Create dimension annotations |
| `export_document` | Export views to PDF or image |

### Interop & Persistence (4)

| Tool | Description |
|------|-------------|
| `export_ifc` | Export model to IFC format (IFC2x3/IFC4) |
| `link_file` | Link or import DWG, DXF, DGN, SAT, SKP, 3DM, or RVT files |
| `load_family` | Load a Revit family (`.rfa`) from disk so its types can be placed |
| `save_document` | Save / Save-As the model to disk (persistence across sessions) |

### Advanced (1)

| Tool | Description |
|------|-------------|
| `execute_revit_code` | Execute IronPython code in Revit context |

## Architecture

Two runtimes communicate over HTTP:

| Component | Runtime | Location | Purpose |
|-----------|---------|----------|---------|
| `main.py` + `tools/` | Python 3.11+ (CPython) | Your machine | MCP protocol, tool definitions |
| `startup.py` + `revit_mcp/` | IronPython 2.7 (inside Revit) | Revit process | pyRevit route handlers, Revit API |

## Multi-Version Revit Support

This server supports Revit 2024, 2025, 2026, and 2027 through centralized helper functions that handle the ElementId API differences across versions:

- `get_element_id_value()` — Extracts integer IDs using `.Value` (2024+) with `.IntegerValue` fallback
- `make_element_id()` — Creates ElementIds using `System.Int64` (2024+) with `int` fallback

No configuration needed — version detection is automatic via try/except at runtime.

> **Revit 2027 note:** Revit 2027 runs on **.NET 10** (vs .NET 8 in 2025/2026). This MCP server is pyRevit-based, so .NET compatibility is handled by pyRevit itself — ensure you run a **pyRevit build with Revit 2027 support**. None of the 48 tools use APIs removed in 2027 (AXM/FormIt import, `Mechanical.Zone` members, legacy rebar creation, or the dropped `EnergyDataSettings` properties).

## Unit Handling

All tools accept **millimeters (mm)**. The server converts to Revit's internal feet.

| From | To mm |
|------|-------|
| meters | x 1000 |
| feet | x 304.8 |
| inches | x 25.4 |

## Creating Your Own Tools

Adding a new tool requires 2 files + 2 registration lines:

1. **Route handler** in `revit_mcp/new_module.py` (IronPython 2.7)
2. **Tool definition** in `tools/new_tools.py` (Python 3.11+)
3. **Register routes** in `startup.py`
4. **Register tools** in `tools/__init__.py`

See [CONTRIBUTING.md](CONTRIBUTING.md#adding-a-new-tool) for a complete worked example, and `LLM.txt` for context that helps AI assistants understand the codebase.

## Contributing

Contributions are welcome — from typo fixes to new tools! Read **[CONTRIBUTING.md](CONTRIBUTING.md)** for the dev setup, the edit–reload loop, a step-by-step "add a tool" walkthrough, and coding conventions.

- Looking for a place to start? See issues labeled [`good first issue`](https://github.com/Demolinator/revit-mcp-server/labels/good%20first%20issue).
- Found a bug or have an idea? [Open an issue](https://github.com/Demolinator/revit-mcp-server/issues/new/choose).
- Please follow our [Code of Conduct](CODE_OF_CONDUCT.md), and report security issues privately per [SECURITY.md](SECURITY.md).

## Author

**Talal Ahmed**

## License

MIT
