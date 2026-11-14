# Contributors

These are the people who have worked on Revit MCP Server in this repository.
Every entry links to the public record of the work, so anyone can check it.

**Every merged pull request earns a place here, including one-line fixes.**
A bug report with a clear repro counts too. See
[Getting credit for your work](CONTRIBUTING.md#getting-credit-for-your-work).

## Maintainer

| Contributor | Role | Record |
|---|---|---|
| [Talal Ahmed](https://github.com/Demolinator) | Maintainer. Revit 2027 support, the expansion to 48 tools, and the rewrite of the server half | [Commits](https://github.com/Demolinator/revit-mcp-server/commits?author=Demolinator) |

## Code

| Contributor | Contribution | Record |
|---|---|---|
| [Vishal Habib](https://github.com/vishalhabib99) | Made 47 optional arguments in 21 tools accept the `null` they advertise, added a regression test, and reported the bug in the first place | [PR #26](https://github.com/Demolinator/revit-mcp-server/pull/26), [#24](https://github.com/Demolinator/revit-mcp-server/issues/24) |
| [Harsh Raj Singhania](https://github.com/HarshRajSinghania) | Fixed `get_revit_view` cutting off view names that contain `#`, with an offline test | [PR #48](https://github.com/Demolinator/revit-mcp-server/pull/48) |
| [bfs2021](https://github.com/bfs2021) | Fixed the `ai_element_filter` total so it counts only elements matching the type name filter | [PR #49](https://github.com/Demolinator/revit-mcp-server/pull/49) |

## Bug reports and research

| Contributor | Contribution | Record |
|---|---|---|
| [jalv92](https://github.com/jalv92) | Found that concurrent tool calls could return each other's results, and traced the cause to pyRevit Routes, where it was reported and then fixed | [#23](https://github.com/Demolinator/revit-mcp-server/issues/23), [pyRevit #3752](https://github.com/pyrevitlabs/pyRevit/issues/3752) |

## Built on

This project started as a fork of
[mcp-servers-for-revit/mcp-server-for-revit-python](https://github.com/mcp-servers-for-revit/mcp-server-for-revit-python),
created by [Juan Rodriguez](https://github.com/JotaDeRodriguez), with contributions from
[Jean-Marc Couffin](https://github.com/jmcouffin) and [ArmandU25](https://github.com/ArmandU25).
Their work is kept in this repository's history, and Juan Rodriguez's copyright
notice is kept in the [LICENSE](LICENSE).
