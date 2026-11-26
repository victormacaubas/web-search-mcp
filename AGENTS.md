## What this is

A Python MCP server that exposes a single `web_search` tool backed by [ddgs](https://github.com/deedy5/ddgs) (DuckDuckGo metasearch). It exists because Claude Code on Bedrock/LiteLLM has `WebFetch` (client-executed) but not `WebSearch` (server-executed). This server handles **discovery** (query → URLs + snippets); Claude Code's native `WebFetch` handles reading.

Intended for personal/educational use — single engineer, low volume, conversational doc-checking. Not a production search service.

## Tech stack

- **Language**: Python 3.13
- **Package manager**: uv
- **MCP framework**: FastMCP (from `mcp[cli]`)
- **Search backend**: ddgs (DuckDuckGo metasearch, synchronous API wrapped in `asyncio.to_thread`)
- **Transport**: stdio (local subprocess of Claude Code)
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

## Project layout

```
src/web_search_mcp/
├── __init__.py          # Package marker (empty)
├── __main__.py          # Entry point: imports mcp from server, calls mcp.run()
├── models.py            # SearchResult dataclass + WebSearchInput Pydantic model
├── search.py            # SearchBackend Protocol + DdgsSearchBackend impl + SearchError
├── server.py            # FastMCP instance, web_search tool function, stderr logging setup
└── py.typed             # PEP 561 typed marker

tests/
├── conftest.py          # MockSearchBackend + fixtures (sample_results, mock_backend, error_backend)
├── test_models.py       # WebSearchInput validation tests
├── test_search.py       # DdgsSearchBackend unit tests (patching DDGS)
└── test_server.py       # Integration tests for web_search tool (patching server.backend)

openspec/                # OpenSpec workflow artifacts
├── config.yaml
├── specs/web-search/    # Canonical capability spec
└── changes/archive/     # Completed change cycles
```

## Architecture

Three-layer stack:

1. **models.py** — Data shapes. `SearchResult` (dataclass: title, url, snippet) is the internal contract. `WebSearchInput` (Pydantic v2: query, max_results, region) validates MCP tool input with field constraints and `str_strip_whitespace=True`.
2. **search.py** — Backend protocol. `SearchBackend` is a `Protocol` with one async method: `search(query, max_results, region) -> list[SearchResult]`. `DdgsSearchBackend` wraps the synchronous `DDGS().text()` via `asyncio.to_thread` and maps results to `SearchResult`. `SearchError` is the domain exception.
3. **server.py** — MCP layer. Creates the `FastMCP` instance, instantiates `backend = DdgsSearchBackend()` at module level, defines the `web_search` tool with `ToolAnnotations(readOnlyHint=True, openWorldHint=True)`, and configures stderr-only logging.

Key decisions:
- **Swappable backend**: Replace the `backend` assignment in `server.py` to swap search providers without touching the tool function.
- **stderr logging only**: stdout is the MCP wire — all diagnostics go to stderr via explicit `StreamHandler(sys.stderr)`.
- **No `fetch_url` tool**: Redundant with Claude Code's native `WebFetch`.
- **Module-level backend**: Tests inject mocks by patching `web_search_mcp.server.backend`.

## Conventions

- Follow `python-engineering-standards` skill for all code.
- Follow `mcp-builder` skill for MCP server patterns.
- Use OpenSpec workflow (`/opsx:propose`, `/opsx:apply`) for non-trivial changes.
- Server name: `web_search_mcp`.
- Tool name: `web_search` (single tool, prefixed to avoid conflicts with other MCP servers on the host).
- All network calls async (ddgs sync API wrapped in `asyncio.to_thread`).
- Pydantic v2 models for tool inputs; plain dataclasses for internal data.
- Tests use `asyncio_mode = "auto"` — no `@pytest.mark.asyncio` decorators needed.
- Ruff target: py313. Rules enforce import sorting, type-checking imports (`TCH`), and pyupgrade (`UP`).

## MCP registration

```bash
claude mcp add web-search -- uv run --directory /absolute/path/to/web-search-mcp python -m web_search_mcp
```

Replace `/absolute/path/to/web-search-mcp` with the actual directory path.

## Disclaimer

Uses ddgs, which scrapes DuckDuckGo — intended for personal/educational use. For commercial or production use, swap in a licensed Search API via the `SearchBackend` protocol.
