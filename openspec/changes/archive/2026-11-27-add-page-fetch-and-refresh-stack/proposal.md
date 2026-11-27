# Proposal

## Why

The `researcher` agent reads pages through the built-in page fetch of the client. That tool sends most pages through a second model, so the agent gets an answer, not the page text. Quotes are not real page text, text after the first 100,000 characters is not read, and "not found" can mean "not asked". The stack of this server is also six months old. The MCP SDK 1.x line now gets security fixes only, the `web_search` input is nested under one `params` key, failures come back as normal results, and searches fail at random when many agents search at the same time.

## What Changes

- Add a `fetch_page` tool. It returns the page text as markdown with no model between the page and the agent. It reads a long page in parts, finds text in a page, and gives an outline of a long page.
- `fetch_page` asks the server for markdown first. It converts HTML only when the server sends HTML. The conversion keeps code blocks, tables, headings, and links.
- `fetch_page` refuses addresses that are not public, on the first request and on each redirect.
- **BREAKING**: `web_search` accepts its parameters as top-level arguments. The `params` wrapper is removed.
- **BREAKING**: `web_search` reports a failure as a tool error. It no longer returns a normal result that starts with `Error:`.
- `web_search` gets a `time_range` parameter (`day`, `week`, `month`, `year`).
- `web_search` makes one more attempt after a failure, and the server runs one search at a time.
- The annotation requirement for `web_search` is corrected. The spec and the code disagree today on `idempotentHint`.
- The server gives usage instructions to the client. Tool descriptions become short.
- Migrate the MCP SDK from 1.x to 2.x. `FastMCP` is now `MCPServer`.
- Upgrade `ddgs`. Give each dependency a lower bound. Update the `uv_build` pin. `httpx` is declared today but not used; `fetch_page` uses it.
- Rewrite `AGENTS.md` without the static project map. Remove the same map from `README.md`.
- Make the project description independent of the gateway in `pyproject.toml`, `README.md`, `openspec/config.yaml`, and `AGENTS.md`.
- Remove the recorded decision "No `fetch_url` tool". This change reverses it.

Not in this change: JavaScript rendering, PDF text, pages that need a login, and clients that imitate a browser to pass bot checks.

## Capabilities

### New Capabilities

- `web-fetch`: Retrieval of the text of a public web page as it is written, with paging, in-page find, an outline, a result header that states what was returned, and a guard against addresses that are not public.

### Modified Capabilities

- `web-search`: Top-level parameters, a recency parameter, failures as tool errors, one retry, one search at a time, corrected annotations, short tool description, and server instructions. The search backend stays swappable.

## Impact

- **Code**: `src/web_search_mcp/` (server, models, search backend, new fetch modules) and `tests/`.
- **Tool interface**: New tool id `mcp__web-search__fetch_page`. The argument shape of `mcp__web-search__web_search` changes. A client that sends `{"params": {...}}` gets a validation error.
- **Dependencies**: `mcp` 2.x, `ddgs` 9.16.1 or later, `httpx` (now used), `beautifulsoup4`, `markdownify`, `lxml`. Lower bounds for all. New `uv_build` pin.
- **Client configuration**: The permission allow-list needs the new tool id. The registration command does not change.
- **Documents**: `AGENTS.md`, `README.md`, `pyproject.toml`, `openspec/config.yaml`.
- **Other repositories (follow-up, not in this change)**: The `researcher` agent definitions in `data-engineering-skills` name the built-in fetch tool. They must name `fetch_page` before the agent can use it.
