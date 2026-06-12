<div align="center">

  <h1>WebSearch-mcp</h1>

  <p>A local MCP server that gives Claude Code web search capabilities on any provider.</p>

  [![License](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
  [![Python](https://img.shields.io/badge/Python_3.13-3776AB?logo=python&logoColor=white)](https://www.python.org/)
  [![MCP](https://img.shields.io/badge/MCP-Server-764ABC?logo=anthropic&logoColor=white)](https://modelcontextprotocol.io/)
  [![uv](https://img.shields.io/badge/uv-Package_Manager-DE5FE9?logo=astral&logoColor=white)](https://docs.astral.sh/uv/)
  [![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](http://makeapullrequest.com)

</div>

---

## Why this exists

Claude Code routed through LiteLLM or AWS Bedrock has **WebFetch** (client-executed — reads a known URL) but **not WebSearch** (server-executed — discovers URLs). The distinction:

- **WebFetch** works on any provider because Claude Code itself makes the HTTP request.
- **WebSearch** is an Anthropic-run server-side tool that Bedrock doesn't support.

The only missing primitive is **discovery** — turning a question into a list of relevant URLs. This MCP server fills that gap with a single `web_search` tool backed by [ddgs](https://github.com/deedy5/ddgs) (DuckDuckGo metasearch). Claude Code's native WebFetch handles reading whatever pages it finds interesting.

## How it works

```
You ask Claude Code a question that needs live web info
    │
    ▼
Claude calls web_search("your query")
    │
    ▼
This MCP server queries DuckDuckGo via ddgs
    │
    ▼
Returns: titles + URLs + snippets
    │
    ▼
Claude uses WebFetch on the URLs it wants to read
```

## Setup

### Prerequisites

- Python 3.13+
- [uv](https://docs.astral.sh/uv/) package manager
- Claude Code CLI

```bash
# Install uv (if you don't have it)
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### Install

```bash
git clone https://github.com/victormacaubas/web-search-mcp.git
```

### Register with Claude Code

```bash
claude mcp add --scope user web-search -- uv run --directory /absolute/path/to/web-search-mcp python -m web_search_mcp
```

Then allow-list the tool in `~/.claude/settings.json`:

```json
{
  "permissions": {
    "allow": [
      "mcp__web-search__web_search"
    ]
  }
}
```

Restart Claude Code and the `web_search` tool is available in all sessions.

## Usage

Once registered, Claude Code will automatically use it when it needs to search the web. You can also prompt it directly:

> "Search for the latest Anthropic MCP documentation"

The tool returns JSON with results:

```json
{
  "results": [
    {
      "title": "Model Context Protocol Documentation",
      "url": "https://modelcontextprotocol.io/docs",
      "snippet": "The Model Context Protocol (MCP) is an open protocol..."
    }
  ]
}
```

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `query` | string | required | Search query (1-500 chars) |
| `max_results` | int | 5 | Number of results (1-20) |
| `region` | string | null | Locale code (e.g. `us-en`, `br-pt`) |

## Architecture

```
src/web_search_mcp/
├── __main__.py    # Entry point (python -m web_search_mcp)
├── server.py      # FastMCP instance + web_search tool
├── search.py      # SearchBackend protocol + DdgsSearchBackend
└── models.py      # SearchResult dataclass + WebSearchInput validation
```

**Key design decisions:**

- **Swappable backend** — `SearchBackend` is a Python Protocol. The ddgs implementation can be replaced with SearXNG or a licensed SERP API without touching the MCP layer.
- **stdio transport** — Runs as a subprocess of Claude Code. stdout is the MCP wire, stderr for logs.
- **No `fetch_url` tool** — Redundant with Claude Code's native WebFetch.

## Development

```bash
# Run tests
uv run pytest

# Lint + format check
uv run ruff check . && uv run ruff format --check .

# Type check (strict)
uv run mypy src/

# Run the server directly
uv run python -m web_search_mcp
```

## Swapping the search backend

The `SearchBackend` protocol has a single method:

```python
class SearchBackend(Protocol):
    async def search(self, query: str, max_results: int, region: str | None) -> list[SearchResult]: ...
```

To use a different backend (e.g., SearXNG, Brave API), implement this protocol and swap the `backend` variable in `server.py`.

## Disclaimer

This tool is designed for **ad-hoc, conversational web searches** — a developer occasionally checking docs, verifying a fact, or looking something up mid-session. It is **not** intended for:

- High-volume agentic workflows that issue dozens of searches per minute
- Production systems with uptime requirements
- Commercial applications at scale

The ddgs library scrapes DuckDuckGo's frontend. At conversational volume (a few searches per hour) this works reliably. At high volume, you will hit rate limits or CAPTCHAs. If your use case requires production-grade search at scale, swap in a licensed Search API via the `SearchBackend` protocol.

## Limitations

- **ddgs relies on scraping** — If DuckDuckGo changes their frontend, searches break until the package is updated.
- **Rate limits** — DuckDuckGo can rate-limit or CAPTCHA under heavy load. At conversational volume this is unlikely.
- **No guaranteed uptime** — This is a personal tool, not a service.

## License

MIT
