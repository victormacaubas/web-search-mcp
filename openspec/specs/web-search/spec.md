# web-search Capability Spec

## Purpose

MCP server capability exposing a `web_search` tool backed by ddgs (DuckDuckGo metasearch). Handles discovery (query → URLs + snippets) via a swappable `SearchBackend` protocol, communicating over stdio transport.

---

## Requirements

### Requirement: Search tool accepts a query and returns results

The `web_search` tool SHALL accept a text query and return a list of search results. Each result SHALL contain a title, URL, and text snippet. The tool SHALL return results as a JSON-formatted string.

#### Scenario: Basic search returns results

- **WHEN** the tool is called with query "Python asyncio tutorial"
- **THEN** it returns a JSON string containing a list of results, each with `title`, `url`, and `snippet` fields

#### Scenario: Empty query is rejected

- **WHEN** the tool is called with an empty or whitespace-only query
- **THEN** input validation rejects the request before any search is performed

---

### Requirement: Search tool supports max_results parameter

The tool SHALL accept an optional `max_results` parameter (default: 5, range: 1–20) controlling the maximum number of results returned.

#### Scenario: Default result count

- **WHEN** the tool is called without specifying max_results
- **THEN** it returns at most 5 results

#### Scenario: Custom result count

- **WHEN** the tool is called with max_results=10
- **THEN** it returns at most 10 results

#### Scenario: Out-of-range max_results is rejected

- **WHEN** the tool is called with max_results=50
- **THEN** input validation rejects the request

---

### Requirement: Search tool supports region parameter

The tool SHALL accept an optional `region` parameter (e.g., "us-en", "br-pt") to localize results. When omitted, the backend's default region applies.

#### Scenario: Region-specific results

- **WHEN** the tool is called with query "news" and region "br-pt"
- **THEN** results are localized to the specified region

#### Scenario: No region defaults to backend default

- **WHEN** the tool is called without a region parameter
- **THEN** the backend uses its own default region behavior

---

### Requirement: Search backend is swappable via protocol

The system SHALL define a `SearchBackend` protocol (Python `Protocol` class) with a single async method for performing searches. The ddgs implementation SHALL conform to this protocol. Alternative backends can be substituted without modifying the MCP tool layer.

#### Scenario: ddgs backend conforms to protocol

- **WHEN** the ddgs backend class is instantiated
- **THEN** it satisfies the `SearchBackend` protocol (verified by mypy)

#### Scenario: Backend failure surfaces as tool error

- **WHEN** the search backend raises an exception (network error, rate limit, etc.)
- **THEN** the tool returns a clear error message string (not an unhandled crash)

---

### Requirement: Server uses stdio transport

The MCP server SHALL communicate via stdio (stdin/stdout for the MCP wire protocol). All logging and diagnostics SHALL go to stderr only.

#### Scenario: Server starts cleanly

- **WHEN** the server process is launched
- **THEN** it begins listening on stdin for MCP messages without printing anything to stdout before a request arrives

#### Scenario: Logging goes to stderr

- **WHEN** the server logs a diagnostic message (e.g., search timing)
- **THEN** the message appears on stderr, never stdout

---

### Requirement: Tool annotations are correctly set

The `web_search` tool SHALL declare MCP annotations: `readOnlyHint=true`, `destructiveHint=false`, `idempotentHint=true`, `openWorldHint=true`.

#### Scenario: Tool is annotated as read-only

- **WHEN** a client inspects the tool's annotations
- **THEN** it sees readOnlyHint=true and destructiveHint=false
