# -*- coding: utf-8 -*-
"""Tests for route registration in startup.py. No Revit required.

Inside Revit the extension runs startup.py with a real ``pyrevit`` package. Here
a small stub stands in for it, so the registration loop can be driven with fake
route modules.
"""

import os
import re
import sys
import types

import pytest

MODULES = [("alpha", "register_alpha_routes"), ("beta", "register_beta_routes"),
           ("gamma", "register_gamma_routes")]
PACKAGE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "revit_mcp")
REGISTER_DEF = re.compile(r"^def (register_\w+_routes)\(", re.MULTILINE)


def _install_pyrevit_stub():
    if "pyrevit" in sys.modules:
        return
    pyrevit = types.ModuleType("pyrevit")
    routes = types.ModuleType("pyrevit.routes")
    routes.API = lambda name: types.SimpleNamespace(name=name)
    pyrevit.routes = routes
    sys.modules["pyrevit"] = pyrevit
    sys.modules["pyrevit.routes"] = routes


_install_pyrevit_stub()

import startup  # noqa: E402  (the pyrevit stub has to be in place first)


def make_loader(broken_imports=(), broken_registrations=()):
    """A load_module() stand-in serving MODULES, with the named modules broken."""

    def load(module_name):
        if module_name in broken_imports:
            raise ImportError("no module named {}".format(module_name))
        module = types.SimpleNamespace()

        def register(api, _name=module_name):
            if _name in broken_registrations:
                raise RuntimeError("{} cannot register".format(_name))
            api.registered.append(_name)

        setattr(module, dict(MODULES)[module_name], register)
        return module

    return load


def run_registration(**kwargs):
    api = types.SimpleNamespace(registered=[])
    return api.registered, startup.register_modules(api, MODULES, make_loader(**kwargs))


def test_a_broken_import_only_disables_its_own_module():
    registered, failures = run_registration(broken_imports=("beta",))

    assert registered == ["alpha", "gamma"]
    assert [failure["module"] for failure in failures] == ["beta"]
    assert "no module named beta" in failures[0]["error"]


def test_a_failing_register_function_only_disables_its_own_module():
    registered, failures = run_registration(broken_registrations=("alpha",))

    assert registered == ["beta", "gamma"]
    assert [failure["module"] for failure in failures] == ["alpha"]
    assert "cannot register" in failures[0]["error"]


def test_nothing_is_reported_when_every_module_registers():
    registered, failures = run_registration()

    assert failures == []
    assert registered == ["alpha", "beta", "gamma"]


def test_every_route_module_is_registered_at_startup():
    """A module that defines a register_*_routes function must be listed too."""
    defined = set()
    for filename in os.listdir(PACKAGE_DIR):
        if filename.endswith(".py"):
            with open(os.path.join(PACKAGE_DIR, filename), encoding="utf-8") as handle:
                defined.update(REGISTER_DEF.findall(handle.read()))

    assert defined == {function for _, function in startup.MODULES}
    assert startup.MODULES[0] == ("status", "register_status_routes")


def test_register_routes_records_failures_on_the_package(monkeypatch):
    import revit_mcp

    monkeypatch.setattr(startup, "register_modules",
                        lambda api, **kwargs: [{"module": "views", "error": "boom"}])
    startup.register_routes()

    assert revit_mcp.REGISTRATION_FAILURES == [{"module": "views", "error": "boom"}]
    revit_mcp.REGISTRATION_FAILURES[:] = []
