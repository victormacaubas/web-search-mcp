## Context

Claude Code on Bedrock/LiteLLM has `WebFetch` but not `WebSearch`. The missing piece is URL discovery — this server provides it via a local MCP tool backed by ddgs. It runs as a subprocess of Claude Code, communicating over stdio.

The repo is greenfield. We use Python 3.13, uv for packaging, FastMCP for the MCP layer, and ddgs for search.

## Goals / Non-Goals

**Goals:**

- Ship a working `web_search` MCP tool that Claude Code can use for URL discovery
- Clean separation between MCP layer and search backend (protocol-based)
- Proper project scaffolding (uv, pyproject.toml, ruff, mypy, pytest)
- Correct stdio behavior (MCP on stdout, logs on stderr)

**Non-Goals:**

- No `fetch_url` tool (WebFetch already does this)
- No HTTP/SSE transport (single-user, local only)
- No caching layer (low volume, not worth the complexity)
- No multi-backend runtime switching (hardcode ddgs; swap means code change)
- No rate limiting (single user, conversational pace)

## Decisions

### 1. Package layout: src layout with `web_search_mcp` package

Use `src/web_search_mcp/` with a `__main__.py` entry point so `python -m web_search_mcp` launches the server. This is the standard uv/modern Python convention.

**Alternative considered**: Single-file script. Rejected — the backend protocol separation needs at least a few modules, and a proper package supports testing and mypy much better.

### 2. SearchBackend as a `typing.Protocol`

Define a structural protocol with one async method:

```python
class SearchBackend(Protocol):
    async def search(self, query: str, max_results: int, region: str | None) -> list[SearchResult]: ...
```

The ddgs implementation class satisfies this protocol. No ABC, no registration — just structural subtyping checked by mypy.

**Alternative considered**: ABC with `register()`. Rejected — overkill for a two-class hierarchy (protocol + one impl). Protocol is lighter and plays well with mypy strict.

### 3. ddgs async API via `DDGS` class

The `ddgs` library provides `DDGS().atext()` for async text search. We wrap this in our backend class, mapping results to our `SearchResult` dataclass.

**Alternative considered**: Sync API with `asyncio.to_thread`. Rejected — ddgs already has native async; no reason to wrap sync.

### 4. Error handling: catch-and-return, never crash

All exceptions from the backend are caught at the tool level and returned as an error string. The MCP server process never dies from a search failure.

**Alternative considered**: Let exceptions propagate to FastMCP's error handler. Rejected — we want control over the error message format to make it actionable for the LLM.

### 5. Logging to stderr via stdlib `logging`

Configure a stderr handler at import time. No structured logging (JSON) — this is a local dev tool, human-readable is fine.

## Risks / Trade-offs

- **ddgs breakage** → Mitigation: acceptable — "no search until package update" is fine for personal use. The protocol boundary means swapping backends is a one-file change.
- **DuckDuckGo rate limiting / CAPTCHA** → Mitigation: at conversational volume (few searches/hour) this is unlikely to trigger. If it does, the error surfaces cleanly to the LLM.
- **ddgs is not typed** → Mitigation: we wrap it in our own typed layer; mypy strict applies to our code, not ddgs internals.
