# -*- coding: utf-8 -*-
"""Shared helpers for tool modules.

Tool modules import ``Context`` and ``format_response`` from here so they all
share one way of turning route results into text for the model.
"""

import json

from mcp.server.fastmcp import Context  # re-exported for tool modules

__all__ = ["Context", "format_response"]

# Keys that describe the envelope rather than the payload.
_ENVELOPE_KEYS = ("status", "health", "success")
_FAILURE_STATUSES = ("error", "failed", "failure", "exception")


def _to_text(value):
    """Render a payload value readably: JSON for containers, str otherwise."""
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, indent=2, ensure_ascii=False, default=str)
    return str(value)


def _is_failure(payload):
    status = str(payload.get("status", "")).lower()
    return bool(payload.get("error")) or status in _FAILURE_STATUSES


def _describe_failure(payload):
    lines = ["Error: {}".format(payload.get("error") or "Revit reported a failure")]
    if payload.get("details"):
        lines.append("Details: {}".format(_to_text(payload["details"])))
    extra = {k: v for k, v in payload.items()
             if k not in ("error", "details", "traceback") + _ENVELOPE_KEYS}
    if extra:
        lines.append("Context: {}".format(_to_text(extra)))
    if payload.get("traceback"):
        lines.append("Traceback:\n{}".format(payload["traceback"]))
    return "\n".join(lines)


def _describe_status(payload):
    lines = ["Revit MCP status: {} ({})".format(payload.get("status"), payload.get("health", "unknown"))]
    for key in sorted(k for k in payload if k not in ("status", "health")):
        lines.append("  {}: {}".format(key, payload[key]))
    return "\n".join(lines)


def format_response(response):
    """Turn a route result into text for the model.

    * strings (transport errors from the client) pass through unchanged
    * failures (an ``error`` key or a failure ``status``) become an ``Error:`` block
    * code-execution results return their captured ``output``
    * health checks (``status == "active"``) get a short status summary
    * anything else returns its ``message`` followed by the remaining data as JSON,
      so IDs and values created by a tool are never dropped
    """
    if not isinstance(response, dict):
        return str(response)
    if _is_failure(response):
        return _describe_failure(response)
    if "output" in response:
        return str(response["output"])
    if str(response.get("status", "")).lower() == "active":
        return _describe_status(response)

    message = response.get("message")
    data = {k: v for k, v in response.items() if k not in _ENVELOPE_KEYS + ("message",)}
    if not data:
        return message or "Done."
    if not message and list(data) in (["result"], ["data"]):
        return _to_text(next(iter(data.values())))  # generic wrapper key adds nothing
    body = _to_text(data)
    return "{}\n{}".format(message, body) if message else body
