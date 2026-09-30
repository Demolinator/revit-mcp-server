# -*- coding: utf-8 -*-
"""Tests for the CPython half of the server. No Revit required.

The live checks that need a running Revit are in tests/live/ and are not
collected by pytest.
"""

import asyncio
import base64
import json
import os

import httpx
import pytest

import main
from tools.utils import format_response

CONTRACT = os.path.join(os.path.dirname(__file__), "tool_contract.json")


def run(coro):
    return asyncio.run(coro)


# --- tool contract ------------------------------------------------------------

def test_tool_contract_is_unchanged():
    """Tool names and input schemas are the public API; changing one is a breaking change.

    If you add or change a tool on purpose, regenerate tests/tool_contract.json
    (see CONTRIBUTING.md) and mention it in your PR.
    """
    expected = json.load(open(CONTRACT, encoding="utf-8"))
    actual = {t.name: t.inputSchema for t in run(main.mcp.list_tools())}
    assert sorted(actual) == sorted(expected)
    for name in expected:
        assert actual[name] == expected[name], name


def test_every_tool_has_a_description():
    for tool in run(main.mcp.list_tools()):
        assert tool.description and len(tool.description.strip()) > 20, tool.name


# --- format_response ----------------------------------------------------------

def test_strings_pass_through():
    assert format_response("Error: boom") == "Error: boom"


def test_error_key_is_reported():
    text = format_response({"error": "Level not found: L9", "traceback": "tb"})
    assert text.startswith("Error: Level not found: L9")
    assert "Traceback:\ntb" in text


def test_failure_status_without_error_key():
    assert format_response({"status": "failed"}).startswith("Error:")


def test_message_keeps_created_ids():
    text = format_response({"status": "success", "message": "Placed 1 desk", "element_id": 4242})
    assert text.startswith("Placed 1 desk")
    assert "4242" in text


def test_data_only_payload_keeps_keys():
    text = format_response({"total_elements": 812, "levels": [{"name": "L1"}]})
    assert "total_elements" in text and "812" in text and "L1" in text


def test_code_output_is_returned_verbatim():
    assert format_response({"status": "success", "output": "walls: 3\n"}) == "walls: 3\n"


def test_status_summary():
    text = format_response({"status": "active", "health": "healthy", "document_title": "Office"})
    assert "active" in text and "Office" in text


def test_non_ascii_survives():
    assert "Этаж 1" in format_response({"levels": ["Этаж 1"]})


# --- RevitClient ----------------------------------------------------------------

def client_with(handler):
    client = main.RevitClient("http://revit.test/revit_mcp")
    client._http = httpx.AsyncClient(base_url=client.root, transport=httpx.MockTransport(handler))
    return client


def test_get_returns_json():
    client = client_with(lambda req: httpx.Response(200, json={"status": "active"}))
    assert run(client.get("/status/")) == {"status": "active"}


def test_post_sends_json_body():
    seen = {}

    def handler(request):
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"status": "success"})

    run(client_with(handler).post("/save_document/", {"file_path": "C:\\m.rvt"}))
    assert seen["body"] == {"file_path": "C:\\m.rvt"}


def test_route_error_body_is_kept_as_dict():
    client = client_with(lambda req: httpx.Response(500, json={"error": "Transaction failed"}))
    assert run(client.post("/x/", {})) == {"error": "Transaction failed"}


def test_unreachable_revit_gives_actionable_hint():
    def handler(request):
        raise httpx.ConnectError("refused", request=request)

    text = run(client_with(handler).get("/status/"))
    assert "cannot reach Revit" in text and "Routes" in text


def test_missing_route_mentions_extension():
    client = client_with(lambda req: httpx.Response(404, text="not found"))
    text = run(client.get("/check_clashes/"))
    assert "404" in text and "extension" in text


def test_timeout_is_explained():
    def handler(request):
        raise httpx.ReadTimeout("slow", request=request)

    assert "did not answer" in run(client_with(handler).get("/model_info/"))


def test_image_is_decoded():
    png = b"\x89PNG\r\n\x1a\nfake"
    body = {"image_data": base64.b64encode(png).decode("ascii")}
    image = run(client_with(lambda req: httpx.Response(200, json=body)).image("/get_view/L1"))
    assert isinstance(image, main.Image) and image.data == png


@pytest.mark.parametrize("argv,expected", [
    ([], "stdio"),
    (["--http"], "streamable-http"),
    (["--streamable-http"], "streamable-http"),
    (["--sse"], "sse"),
    (["--combined"], "combined"),
])
def test_transport_flags(argv, expected):
    assert main.parse_args(argv).transport == expected
