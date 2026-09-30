# -*- coding: utf-8 -*-
"""Revit MCP Server - entry point.

Exposes Revit to MCP clients. Every tool forwards to an HTTP endpoint served by
the revit-mcp pyRevit extension (``startup.py`` + ``revit_mcp/``) running
inside Revit.

Usage:
    uv run main.py                     # stdio (Claude Desktop / Claude Code)
    uv run main.py --http              # streamable HTTP on /mcp
    uv run main.py --sse               # legacy SSE on /sse + /messages/
    uv run main.py --combined          # streamable HTTP and SSE together

Environment:
    REVIT_HOST  host running Revit + pyRevit Routes   (default: localhost)
    REVIT_PORT  pyRevit Routes port                   (default: 48884)
    MCP_HOST    bind address for --http/--sse modes   (default: 127.0.0.1)
    MCP_PORT    port for --http/--sse modes           (default: 8000)
"""

import argparse
import base64
import os
from typing import Any, Dict, Optional, Union

import httpx
from mcp.server.fastmcp import FastMCP, Image

REVIT_HOST = os.environ.get("REVIT_HOST", "localhost")
REVIT_PORT = int(os.environ.get("REVIT_PORT", "48884"))
MCP_HOST = os.environ.get("MCP_HOST", "127.0.0.1")
MCP_PORT = int(os.environ.get("MCP_PORT", "8000"))

API_ROOT = "http://{}:{}/revit_mcp".format(REVIT_HOST, REVIT_PORT)
DEFAULT_TIMEOUT = 30.0
IMAGE_TIMEOUT = 60.0

UNREACHABLE_HINT = (
    "Error: cannot reach Revit at {root}.\n"
    "Check that:\n"
    "  1. Revit is open with a project (not just the start screen)\n"
    "  2. pyRevit Routes Server is enabled (pyRevit tab > Settings > Routes)\n"
    "  3. the revit-mcp pyRevit extension is installed and loaded\n"
    "Test in a browser: {root}/status/"
)
NOT_FOUND_HINT = (
    "Error: Revit does not provide the route '{path}' (HTTP 404).\n"
    "The pyRevit extension loaded in Revit is probably missing or a different "
    "version from this server. Reinstall the extension from this repository "
    "and reload pyRevit."
)
TIMEOUT_HINT = (
    "Error: Revit did not answer '{path}' within {secs:.0f}s.\n"
    "Revit may be busy or blocked by an open dialog; check the Revit window."
)

Payload = Dict[str, Any]
Result = Union[Payload, str]


class RevitClient(object):
    """Async HTTP client for the revit-mcp routes.

    One pooled connection is shared by all tool calls. Methods never raise:
    failures come back as an ``"Error: ..."`` string the model can read.
    """

    def __init__(self, root: str = API_ROOT):
        self.root = root
        self._http: Optional[httpx.AsyncClient] = None

    def _session(self) -> httpx.AsyncClient:
        if self._http is None or self._http.is_closed:
            self._http = httpx.AsyncClient(
                base_url=self.root,
                limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
            )
        return self._http

    async def _send(self, method: str, path: str, timeout: float, **kwargs) -> Union[httpx.Response, str]:
        try:
            return await self._session().request(method, path, timeout=timeout, **kwargs)
        except (httpx.ConnectError, httpx.ConnectTimeout):
            return UNREACHABLE_HINT.format(root=self.root)
        except httpx.TimeoutException:
            return TIMEOUT_HINT.format(path=path, secs=timeout)
        except httpx.HTTPError as exc:
            return "Error: request to {} failed: {}".format(path, exc)

    @staticmethod
    def _decode(path: str, response: Union[httpx.Response, str]) -> Result:
        if isinstance(response, str):
            return response
        if response.status_code == 404:
            return NOT_FOUND_HINT.format(path=path)
        try:
            body = response.json()
        except ValueError:
            return "Error: {} - {}".format(response.status_code, response.text)
        if response.status_code >= 400 and isinstance(body, dict) and "error" not in body:
            body = dict(body, error="HTTP {}".format(response.status_code))
        return body

    async def get(self, path: str, ctx=None, timeout: float = DEFAULT_TIMEOUT,
                  params: Optional[Payload] = None) -> Result:
        """GET a route and return its decoded JSON (or an error string)."""
        return self._decode(path, await self._send("GET", path, timeout, params=params))

    async def post(self, path: str, data: Optional[Payload] = None, ctx=None,
                   timeout: float = DEFAULT_TIMEOUT) -> Result:
        """POST a JSON body to a route and return its decoded JSON (or an error string)."""
        return self._decode(path, await self._send("POST", path, timeout, json=data or {}))

    async def image(self, path: str, ctx=None) -> Union[Image, str]:
        """GET a route that returns ``{"image_data": <base64 png>}`` as an MCP image."""
        result = self._decode(path, await self._send("GET", path, IMAGE_TIMEOUT))
        if isinstance(result, str):
            return result
        encoded = result.get("image_data") if isinstance(result, dict) else None
        if not encoded:
            return "Error: {}".format(result.get("error") if isinstance(result, dict) else result)
        return Image(data=base64.b64decode(encoded), format="png")


revit = RevitClient()
mcp = FastMCP(
    "Revit MCP Server",
    host=MCP_HOST,
    port=MCP_PORT,
    stateless_http=True,
    json_response=True,
)

from tools import register_tools  # noqa: E402  (needs `mcp` defined first)

register_tools(mcp, revit.get, revit.post, revit.image)


async def serve_http_and_sse() -> None:
    """Serve streamable HTTP (/mcp) and SSE (/sse, /messages/) from one app.

    The streamable-HTTP app owns the lifespan that starts its session manager,
    so the SSE routes are mounted onto it rather than the other way round.
    """
    import uvicorn

    app = mcp.streamable_http_app()
    app.routes.extend(mcp.sse_app().routes)
    config = uvicorn.Config(app, host=MCP_HOST, port=MCP_PORT,
                            log_level=mcp.settings.log_level.lower())
    await uvicorn.Server(config).serve()


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Revit MCP Server")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--http", "--streamable-http", dest="transport", action="store_const",
                      const="streamable-http", help="serve streamable HTTP on /mcp")
    mode.add_argument("--sse", dest="transport", action="store_const", const="sse",
                      help="serve legacy SSE on /sse and /messages/")
    mode.add_argument("--combined", dest="transport", action="store_const", const="combined",
                      help="serve streamable HTTP and SSE together")
    parser.set_defaults(transport="stdio")
    return parser.parse_args(argv)


if __name__ == "__main__":
    transport = parse_args().transport
    if transport == "combined":
        import anyio

        print("Serving streamable HTTP (/mcp) and SSE (/sse, /messages/) on http://{}:{}".format(MCP_HOST, MCP_PORT))
        anyio.run(serve_http_and_sse)
    else:
        mcp.run(transport=transport)
