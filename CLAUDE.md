## What this is

A Python MCP server that exposes a `web_search` tool backed by [ddgs](https://github.com/deedy5/ddgs) (DuckDuckGo metasearch). It exists because Claude Code on Bedrock/LiteLLM has `WebFetch` (client-executed) but not `WebSearch` (server-executed). This server fills the gap: it handles **discovery** (query → URLs + snippets), while Claude Code's native `WebFetch` handles reading.

Intended for personal/educational use — single engineer, low volume, conversational doc-checking. Not a production search service.

## Tech stack

- **Language**: Python 3.13
- **Package manager**: uv
- **MCP framework**: FastMCP (from `mcp` SDK)
- **Search backend**: ddgs (metasearch aggregator — mostly hits Bing's index via DuckDuckGo)
- **Transport**: stdio (local tool, subprocess of Claude Code)
- **Linting/formatting**: ruff
- **Type checking**: mypy (strict)
- **Testing**: pytest + pytest-asyncio

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

## Architecture

Key design decisions:
- **Swappable backend**: `SearchBackend` protocol so ddgs can be replaced with SearXNG or a licensed SERP API without touching the MCP layer.
- **stderr logging only**: stdio transport means stdout is the MCP wire — all diagnostics go to stderr.
- **No `fetch_url` tool**: redundant with Claude Code's native `WebFetch`.

## Conventions

- Follow `python-engineering-standards` skill for all code.
- Follow `mcp-builder` skill for MCP server patterns.
- Use OpenSpec workflow (`/opsx:propose`, `/opsx:apply`) for non-trivial changes.
- Server name: `web_search_mcp` (per MCP naming convention).
- Tool names prefixed with `web_search_` to avoid conflicts with other MCP servers.
- All network calls async (`httpx` or ddgs async API).
- Pydantic v2 models for all tool inputs.

## MCP registration (for the user)

```bash
claude mcp add web-search -- uv run --directory /absolute/path/to/web-search-mcp python -m web_search_mcp
```

## Disclaimer

Uses ddgs, which scrapes DuckDuckGo — intended for personal/educational use. For commercial or production use, swap in a licensed Search API via the `SearchBackend` protocol.
