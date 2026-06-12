## 1. Project Scaffolding

- [x] 1.1 Run `uv init` to generate pyproject.toml, configure project metadata (name, version, python-requires, description)
- [x] 1.2 Add dependencies (`mcp`, `ddgs`, `httpx`, `pydantic`) and dev dependencies (`pytest`, `pytest-asyncio`, `ruff`, `mypy`) to pyproject.toml
- [x] 1.3 Create `src/web_search_mcp/` package directory with `__init__.py` and `__main__.py`
- [x] 1.4 Configure ruff, mypy, and pytest in pyproject.toml (ruff rules, mypy strict, pytest asyncio_mode=auto)
- [x] 1.5 Run `uv sync` to install all dependencies into the existing venv

## 2. Models and Protocol

- [x] 2.1 Create `src/web_search_mcp/models.py` — define `SearchResult` dataclass (title, url, snippet) and Pydantic `WebSearchInput` model (query, max_results, region)
- [x] 2.2 Create `src/web_search_mcp/search.py` — define `SearchBackend` Protocol with async `search` method signature

## 3. Search Backend Implementation

- [x] 3.1 Implement `DdgsSearchBackend` class in `search.py` — wraps `DDGS().text()` via asyncio.to_thread, maps results to `SearchResult`, handles exceptions
- [x] 3.2 Verify `DdgsSearchBackend` satisfies `SearchBackend` protocol (mypy pass)

## 4. MCP Server and Tool

- [x] 4.1 Create `src/web_search_mcp/server.py` — initialize `FastMCP("web_search_mcp")`, configure stderr logging
- [x] 4.2 Implement `web_search` tool — accepts `WebSearchInput`, calls backend, returns JSON-formatted results string with proper annotations and docstring
- [x] 4.3 Wire `__main__.py` to call `mcp.run()` (stdio transport)

## 5. Testing

- [x] 5.1 Create `tests/` directory with `conftest.py` (fixtures for a mock search backend)
- [x] 5.2 Write unit tests for `WebSearchInput` model validation (valid inputs, empty query rejection, out-of-range max_results)
- [x] 5.3 Write unit tests for `DdgsSearchBackend` (mock ddgs responses, error handling)
- [x] 5.4 Write integration test for the `web_search` tool function (using mock backend, verify JSON output shape)

## 6. Verification

- [x] 6.1 Run `uv run ruff check . && uv run ruff format --check .` — all clean
- [x] 6.2 Run `uv run mypy src/` — passes with strict mode
- [x] 6.3 Run `uv run pytest` — all tests pass
- [x] 6.4 Smoke test: run `uv run python -m web_search_mcp` and verify it starts without stdout output (manually send MCP init if needed)
