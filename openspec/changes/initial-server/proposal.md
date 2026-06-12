## Why

Claude Code on Bedrock/LiteLLM has `WebFetch` (client-executed, reads a known URL) but not `WebSearch` (server-executed, discovers URLs). The only missing primitive is **discovery** — turning a question into a list of relevant URLs. A local MCP server backed by ddgs fills this gap with zero external API keys, fully under personal control.

## What Changes

- Introduce a Python MCP server (`web_search_mcp`) with a single `web_search` tool
- Implement a `SearchBackend` protocol with a ddgs implementation (swappable for SearXNG or licensed APIs later)
- Return titles, URLs, and snippets — Claude Code's native `WebFetch` handles the actual page reading
- Expose via stdio transport as a Claude Code subprocess

## Capabilities

### New Capabilities

- `web-search`: The core tool — accepts a query and optional parameters (max results, region), returns ranked search results with title, URL, and snippet. Backed by swappable search backend.

### Modified Capabilities

(none — greenfield project)

## Impact

- **New dependencies**: `mcp`, `ddgs`, `httpx`, `pydantic`
- **Dev dependencies**: `pytest`, `pytest-asyncio`, `ruff`, `mypy`
- **Registration**: User adds this server to Claude Code via `claude mcp add`
- **No external services**: ddgs scrapes DuckDuckGo directly, no API keys needed
- **Risk**: ddgs can break if DuckDuckGo changes their frontend — acceptable for personal use (just means "no search until package update")
