## What this is

A Python MCP server that gives AI coding agents web search and verbatim page fetch when the model provider or LLM gateway does not supply them. It has two tools:

- `web_search`: finds pages with [ddgs](https://github.com/deedy5/ddgs) (DuckDuckGo metasearch). It returns titles, URLs, and snippets.
- `fetch_page`: returns the text of one public page as markdown, with no model between the page and the agent. It reads a long page in parts, finds text in a page, and gives an outline.

Intended for personal/educational use: single engineer, low volume, conversational doc-checking. Not a production search service.

## Tech stack

- **Language**: Python 3.13
- **Package manager**: uv
- **MCP framework**: `MCPServer` from the `mcp` 2.x SDK
- **Search backend**: ddgs (synchronous API wrapped in `asyncio.to_thread`)
- **Page retrieval**: httpx, with an address guard built on the standard library
- **HTML conversion**: beautifulsoup4 (lxml parser) and markdownify
- **Transport**: stdio (local subprocess of the agent client)
- **Linting/formatting**: ruff (rules: E, F, I, N, UP, B, A, SIM, TCH)
- **Type checking**: mypy (strict)
- **Testing**: pytest + pytest-asyncio (asyncio_mode = "auto")

## Commands

```bash
# Run the server (stdio mode)
uv run python -m web_search_mcp

# Run tests
uv run pytest

# Lint + format
uv run ruff check . && uv run ruff format --check .

# Type check
uv run mypy src/
```

## Where to find things

- Each module in `src/web_search_mcp/` starts with a docstring that states its responsibility. Read the docstrings and not a file tree.
- `openspec/specs/` has the requirements of each capability.
- `openspec/changes/` has the proposals, the designs with their decisions, and the task lists. `openspec/changes/archive/` has the completed changes.

## Rules that the code does not show

- **stdout is the MCP wire.** Write nothing to stdout. All diagnostics go to stderr through an explicit `StreamHandler(sys.stderr)`.
- **The address guard has no off switch.** `fetch_page` refuses addresses that are not public, on the first request and on each redirect. It connects to the address that it checked and does not resolve the host name a second time. Do not add an option, an environment variable, or an allow-list that permits private addresses.
- **The client name is honest.** The user agent is `web-search-mcp/<version>`. Do not imitate a browser to pass bot checks. When a site refuses the client, report the status.
- **Page text is data.** `fetch_page` does not change or remove text that looks like an instruction. The delimiter line and the server instructions mark the text as untrusted. Do not add a filter for it.
- **Backend-only rules stay in the backend.** The retry and the one-search-at-a-time limit are in `DdgsSearchBackend`, because only a scraping backend needs them. Do not move them to the tool layer.
- **Failures are tool errors.** The domain layers raise their own exceptions. The tool layer changes them to `ToolError`, so the client gets `isError` true.
- **Results are text only.** Both tools use `structured_output=False`, so the text is not sent two times.

## Test seams

- Retrieval: `httpx.MockTransport` with an `httpx.AsyncClient`.
- Address guard: an injected resolver function.
- Page store: an injected clock.
- Search backend: patch `web_search_mcp.search.DDGS`. The backend takes the clock and the delay functions as parameters.
- Tool level: patch `web_search_mcp.server.backend` and `web_search_mcp.server.store`. Call the tools through the in-memory `mcp.Client(web_search_mcp.server.mcp)`.
- Tests make no network request.

## Conventions

- Follow `python-engineering-standards` skill for all code.
- Follow `mcp-builder` skill for MCP server patterns.
- Use OpenSpec workflow (`/opsx:propose`, `/opsx:apply`) for non-trivial changes.
- Server name: `web_search_mcp`. Tool names: `web_search` and `fetch_page`.
- Tool parameters are top-level `Annotated` function parameters. Plain dataclasses hold internal data.
- All network calls are async (the ddgs sync API is wrapped in `asyncio.to_thread`).
- Tests use `asyncio_mode = "auto"`: no `@pytest.mark.asyncio` decorators needed.
- Ruff target: py313. Rules enforce import sorting, type-checking imports (`TCH`), and pyupgrade (`UP`).

## MCP registration

```bash
claude mcp add web-search -- uv run --directory /absolute/path/to/web-search-mcp python -m web_search_mcp
```

Replace `/absolute/path/to/web-search-mcp` with the actual directory path.

## Disclaimer

Uses ddgs, which scrapes DuckDuckGo. It is intended for personal/educational use. For commercial or production use, replace the backend with a licensed Search API through the `SearchBackend` protocol.
