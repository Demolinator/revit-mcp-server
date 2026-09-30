# Security Policy

## Threat model in brief

- The MCP server talks to **pyRevit Routes on `localhost:48884`**, which has
  **no authentication**. Anything that can reach that port can drive Revit.
- The `execute_revit_code` tool **runs arbitrary IronPython inside Revit**
  with the user's permissions, by design.
- The HTTP transports (`--sse`, `--streamable-http`, `--combined`) bind to
  `127.0.0.1` by default. If you expose them through a tunnel (ngrok, etc.),
  you are exposing full control of your Revit session. Use an authenticated
  tunnel and don't share the URL.

## Supported versions

Security fixes are made on the latest `master` only.

## Reporting a vulnerability

**Please do not open a public issue for security problems.**

Email **talal@demolinator.com** with:

- a description of the issue and its impact
- steps to reproduce (Revit / pyRevit / client versions)
- any suggested fix

You should get an acknowledgement within a few days. Once a fix is released,
we're happy to credit you in the release notes unless you prefer otherwise.
