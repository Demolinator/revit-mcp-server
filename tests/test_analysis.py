"""Offline tests for revit_mcp/analysis.py route handlers."""

import importlib
import sys
import types

import pytest


def _make_element(elem_id, category_name="Walls", type_name="Basic Wall"):
    return types.SimpleNamespace(
        Id=elem_id,
        Name=type_name,
        Category=types.SimpleNamespace(Name=category_name),
        LevelId=-1,
        LookupParameter=lambda _name: None,
        GetTypeId=lambda: -1,
    )


def _load_ai_filter_handler(monkeypatch, elements):
    class FakeCollector:
        def __init__(self, _doc, *_args):
            self._items = list(elements)

        def OfCategory(self, _bic):
            return self

        def WhereElementIsNotElementType(self):
            return self

        def ToElements(self):
            return list(self._items)

    fake_db = types.SimpleNamespace(
        BuiltInCategory=types.SimpleNamespace(
            OST_Walls="OST_Walls",
            OST_Doors="OST_Doors",
        ),
        ElementId=types.SimpleNamespace(InvalidElementId=-1),
        FilteredElementCollector=FakeCollector,
    )
    fake_routes = types.SimpleNamespace(
        make_response=lambda data=None, status=200: {"data": data, "status": status},
    )
    fake_pyrevit = types.ModuleType("pyrevit")
    fake_pyrevit.routes = fake_routes
    fake_pyrevit.revit = types.SimpleNamespace()
    fake_pyrevit.DB = fake_db

    fake_utils = types.ModuleType("utils")
    fake_utils.get_element_name = lambda elem: elem.Name
    fake_utils.normalize_string = lambda text: str(text)
    fake_utils.get_element_id_value = lambda elem: elem.Id

    monkeypatch.setitem(sys.modules, "pyrevit", fake_pyrevit)
    monkeypatch.setitem(sys.modules, "utils", fake_utils)
    monkeypatch.delitem(sys.modules, "revit_mcp.analysis", raising=False)

    analysis = importlib.import_module("revit_mcp.analysis")

    registered = {}

    class FakeAPI:
        def route(self, path, methods=None):
            _ = methods

            def decorator(fn):
                registered[path] = fn
                return fn

            return decorator

    analysis.register_analysis_routes(FakeAPI())
    return registered["/ai_filter/"]


@pytest.mark.parametrize(
    "payload,elem_count,expected_message",
    [
        ({"category": "OST_Walls"}, 0, "Found 0 walls matching filters"),
        ({"category": "OST_Walls"}, 1, "Found 1 walls matching filters"),
        ({"category": "OST_Walls"}, 4, "Found 4 walls matching filters"),
        ({"category": "OST_Doors"}, 3, "Found 3 doors matching filters"),
        ({}, 0, "Found 0 elements matching filters"),
        ({}, 1, "Found 1 element matching filters"),
        ({}, 4, "Found 4 elements matching filters"),
        ({"category": None}, 1, "Found 1 element matching filters"),
        ({"category": None}, 4, "Found 4 elements matching filters"),
        ({"category": ""}, 0, "Found 0 elements matching filters"),
        ({"category": ""}, 1, "Found 1 element matching filters"),
        ({"category": ""}, 4, "Found 4 elements matching filters"),
    ],
)
def test_ai_element_filter_message_pluralization(
    monkeypatch, payload, elem_count, expected_message
):
    elements = [_make_element(i + 1) for i in range(elem_count)]
    handler = _load_ai_filter_handler(monkeypatch, elements)
    doc = types.SimpleNamespace(GetElement=lambda _eid: None)
    request = types.SimpleNamespace(data=payload)

    resp = handler(doc, request)

    assert resp["status"] == 200
    assert resp["data"]["total_matched"] == elem_count
    assert resp["data"]["message"] == expected_message


def test_ai_element_filter_message_uses_total_matched_when_capped(monkeypatch):
    elements = [_make_element(i + 1) for i in range(4)]
    handler = _load_ai_filter_handler(monkeypatch, elements)
    doc = types.SimpleNamespace(GetElement=lambda _eid: None)

    resp_no_cat = handler(doc, types.SimpleNamespace(data={"max_elements": 1}))
    assert resp_no_cat["data"]["count"] == 1
    assert resp_no_cat["data"]["total_matched"] == 4
    assert resp_no_cat["data"]["message"] == "Found 4 elements matching filters"

    resp_walls = handler(
        doc, types.SimpleNamespace(data={"category": "OST_Walls", "max_elements": 1})
    )
    assert resp_walls["data"]["count"] == 1
    assert resp_walls["data"]["total_matched"] == 4
    assert resp_walls["data"]["message"] == "Found 4 walls matching filters"
