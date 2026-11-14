# Contributors

Revit MCP Server exists because of the people below. Every entry links to the
public record of the work, so anyone can check it.

**Every merged pull request earns a place here, including one-line fixes and
typo corrections.** A bug report with a clear repro counts too. See
[Getting credit for your work](CONTRIBUTING.md#getting-credit-for-your-work).

## Maintainer

| Contributor | Role | Record |
|---|---|---|
| [Talal Ahmed](https://github.com/Demolinator) | Maintainer. Revit 2027 support, the expansion to 48 tools, and the rewrite of the server half | [Commits](https://github.com/Demolinator/revit-mcp-server/commits?author=Demolinator) |

## Code

| Contributor | Contribution | Record |
|---|---|---|
| [Juan Rodriguez](https://github.com/JotaDeRodriguez) | Original author of the project, including the first MCP server and the pyRevit extension | [Commits](https://github.com/Demolinator/revit-mcp-server/commits?author=JotaDeRodriguez) |
| [Jean-Marc Couffin](https://github.com/jmcouffin) | Color tools, UTF-8 and response formatting work, and documentation fixes | [Commits](https://github.com/Demolinator/revit-mcp-server/commits?author=jmcouffin) |
| [ArmandU25](https://github.com/ArmandU25) | Fixed the combined transport mode and documented the transport modes | [Commits](https://github.com/Demolinator/revit-mcp-server/commits?author=ArmandU25) |
| [Vishal Habib](https://github.com/vishalhabib99) | Made 47 optional arguments in 21 tools accept the `null` they advertise, added a regression test, and reported the bug in the first place | [PR #26](https://github.com/Demolinator/revit-mcp-server/pull/26), [#24](https://github.com/Demolinator/revit-mcp-server/issues/24) |

## Bug reports and research

| Contributor | Contribution | Record |
|---|---|---|
| [jalv92](https://github.com/jalv92) | Found that concurrent tool calls could return each other's results, and traced the cause to pyRevit Routes, where it was reported and then fixed | [#23](https://github.com/Demolinator/revit-mcp-server/issues/23), [pyRevit #3752](https://github.com/pyrevitlabs/pyRevit/issues/3752) |
