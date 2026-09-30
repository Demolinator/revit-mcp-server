# -*- coding: utf-8 -*-
"""Family discovery, loading, and placement tools."""

from typing import Any, Dict

from .utils import Context, format_response


def register_family_tools(mcp, revit_get, revit_post):
    """Register place_family, list_families, list_family_categories, load_family."""

    @mcp.tool()
    async def place_family(
        family_name: str,
        type_name: str = None,
        x: float = 0.0,
        y: float = 0.0,
        z: float = 0.0,
        rotation: float = 0.0,
        level_name: str = None,
        properties: Dict[str, Any] = None,
        ctx: Context = None,
    ) -> str:
        """Place one instance of a loaded family (furniture, equipment, doors, windows...).

        Coordinates are in millimeters. Doors and windows are hosted on the
        wall nearest the point, so create walls first. Use list_families to
        find valid names, or load_family to bring in a new .rfa.

        Args:
            family_name: Family name, e.g. "Desk".
            type_name: Type within the family, e.g. "1525 x 762mm". Uses the
                first type when omitted.
            x: X coordinate in mm.
            y: Y coordinate in mm.
            z: Z offset in mm.
            rotation: Rotation about the vertical axis, in degrees.
            level_name: Level to place on, e.g. "Level 1".
            properties: Instance parameters to set afterwards, e.g.
                {"Comments": "AI placed"}.
        """
        payload = {
            "family_name": family_name,
            "type_name": type_name,
            "location": {"x": x, "y": y, "z": z},
            "rotation": rotation,
            "level_name": level_name,
            "properties": properties or {},
        }
        return format_response(await revit_post("/place_family/", payload, ctx))

    @mcp.tool()
    async def list_families(
        contains: str = None, limit: int = 50, ctx: Context = None
    ) -> str:
        """List loaded family types as family name, type name, and category.

        Args:
            contains: Only return families or types whose name contains this text.
            limit: Maximum number of results (default 50).
        """
        query = {}
        if contains:
            query["contains"] = contains
        if limit != 50:
            query["limit"] = str(limit)
        return format_response(await revit_get("/list_families/", ctx, params=query))

    @mcp.tool()
    async def list_family_categories(ctx: Context = None) -> str:
        """List the categories that have loadable families in this model, with counts."""
        return format_response(await revit_get("/list_family_categories/", ctx))

    @mcp.tool()
    async def load_family(file_path: str, ctx: Context = None) -> str:
        """Load a Revit family (.rfa file) from disk into the active document.

        Use this when a needed family (furniture, doors, windows, equipment) is
        not already loaded in the project — load it first, then place_family can
        place its types. The file_path must be a full path to a .rfa file
        accessible to the machine running Revit.

        Args:
            file_path: Full path to the .rfa family file, e.g.
                "C:\\ProgramData\\Autodesk\\RVT 2027\\Libraries\\English\\Furniture\\Chair.rfa"
            ctx: MCP context for logging
        """
        response = await revit_post("/load_family/", {"file_path": file_path}, ctx)
        return format_response(response)
