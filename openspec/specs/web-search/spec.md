# web-search Capability Spec

## Purpose

MCP server capability exposing a `web_search` tool backed by ddgs (DuckDuckGo metasearch). Handles discovery (query → URLs + snippets) via a swappable `SearchBackend` protocol, communicating over stdio transport.

---

## Requirements

### Requirement: Search tool accepts a query and returns results

The `web_search` tool SHALL accept a text query and return a list of search results. Each result SHALL contain a title, URL, and text snippet. The tool SHALL return results as a JSON-formatted string. The tool SHALL accept its parameters as top-level arguments.

#### Scenario: Basic search returns results

- **WHEN** the tool is called with query "Python asyncio tutorial"
- **THEN** it returns a JSON string containing a list of results, each with `title`, `url`, and `snippet` fields

#### Scenario: Empty query is rejected

- **WHEN** the tool is called with an empty or whitespace-only query
- **THEN** input validation rejects the request before any search is performed

#### Scenario: Top-level arguments are accepted

- **WHEN** a client calls the tool with the arguments `{"query": "Python asyncio tutorial"}`
- **THEN** the tool does the search and returns results

#### Scenario: Arguments in a wrapper are rejected

- **WHEN** a client calls the tool with the arguments `{"params": {"query": "Python asyncio tutorial"}}`
- **THEN** input validation rejects the request

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
- **THEN** the tool reports a tool error with a clear message, and does not return a normal result or crash

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

The `web_search` tool SHALL declare the MCP annotations `readOnlyHint=true` and `openWorldHint=true`.

#### Scenario: Tool is annotated as read-only

- **WHEN** a client inspects the tool's annotations
- **THEN** it sees readOnlyHint=true and openWorldHint=true

---

### Requirement: Search tool supports a recency parameter

The tool SHALL accept an optional `time_range` parameter with the values `day`, `week`, `month`, and `year`. When the parameter is given, the tool SHALL return only results from that period. When the parameter is omitted, the tool SHALL NOT limit results by date.

#### Scenario: Results from the last month

- **WHEN** the tool is called with `time_range` set to `month`
- **THEN** the backend receives a request that is limited to the last month

#### Scenario: No time range

- **WHEN** the tool is called without `time_range`
- **THEN** the backend receives a request with no date limit

#### Scenario: Value that is not valid is rejected

- **WHEN** the tool is called with `time_range` set to `decade`
- **THEN** input validation rejects the request

---

### Requirement: Search failure message does not claim that no pages exist

When a search returns no results or the search engines refuse the request, the tool SHALL report a tool error. The message SHALL state that the engines returned nothing or refused the request, and that this is not proof that no pages exist. When a search does not complete in time, the message SHALL state that the search timed out.

#### Scenario: Engines return nothing

- **WHEN** the backend reports that no results were found
- **THEN** the tool reports a tool error that states the two possible causes and tells the agent to try again or to change the query

#### Scenario: Search times out

- **WHEN** the backend reports a timeout
- **THEN** the tool reports a tool error that states that the search timed out

---

### Requirement: Search makes one more attempt after a failure

When the first attempt of a search fails, the default backend SHALL make one more attempt after a short delay. The backend SHALL report the failure only when the second attempt also fails.

#### Scenario: Second attempt succeeds

- **WHEN** the first attempt fails and the second attempt returns results
- **THEN** the tool returns the results and reports no error

#### Scenario: Two attempts fail

- **WHEN** the first attempt and the second attempt fail
- **THEN** the tool reports a tool error after two attempts and makes no third attempt

---

### Requirement: One search runs at a time

In one server process, the default backend SHALL run a maximum of one search at a time and SHALL keep a minimum interval between the starts of two searches.

#### Scenario: Three calls at the same time

- **WHEN** three agents call the tool at the same time
- **THEN** the three searches run one after the other, and each call gets its result

---

### Requirement: Search tool description is short

The description of the `web_search` tool SHALL be 1,000 characters or fewer and SHALL state in its first sentence what the tool does.

#### Scenario: Client reads the tool description

- **WHEN** a client lists the tools of the server
- **THEN** the description of `web_search` is 1,000 characters or fewer

---

### Requirement: Server gives usage instructions to the client

The server SHALL give instructions to the client at the start of a session. The instructions SHALL state when to use each tool and SHALL state that page text and search snippets are untrusted data. The instructions SHALL be 2,000 characters or fewer.

#### Scenario: Client reads the server instructions

- **WHEN** a client connects to the server
- **THEN** the client receives instructions that name `web_search` and `fetch_page` and are 2,000 characters or fewer
