# Tasks

Follow the `python-engineering-standards` and `mcp-builder` skills for all code. For each task group, write the tests first, then the code. Each group is complete when `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .`, and `uv run mypy src/` pass.

## 1. Stack migration (no behavior change)

- [ ] 1.1 Create a git worktree at `../web-search-mcp-dev` on a new branch `feat/page-fetch-and-refresh-stack` from `main`, and do all work in the worktree. The registered `web-search` server runs from the main checkout, so it stays on `main` during the work. Verify with `git worktree list` and with `git -C ../web-search-mcp-dev branch --show-current`.
- [ ] 1.2 In `pyproject.toml`, set the dependency floors from design D18, add `beautifulsoup4`, `markdownify`, and `lxml`, and set `uv_build>=0.13.5,<0.14`. Run `uv lock --upgrade` and `uv sync`. Verify that `uv run python -c "import mcp.server.mcpserver, bs4, markdownify, httpx"` exits with 0 and that `uv.lock` shows `mcp` 2.x and `ddgs` 9.16.1 or later.
- [ ] 1.3 Replace `FastMCP` with `MCPServer` in the server module and keep the tool behavior as it is. Verify that the existing test suite passes with no change to its assertions.
- [ ] 1.4 Verify that the server starts on stdio: run `uv run python -m web_search_mcp` with an empty stdin and confirm that nothing is written to stdout before a request.

## 2. `web_search` tool contract

- [ ] 2.1 Add tool-level tests that use the in-memory `mcp.Client`: top-level arguments are accepted, a `params` wrapper is rejected, an empty query is rejected, `max_results=50` is rejected, `time_range="decade"` is rejected. Verify that the tests fail before task 2.2 and pass after it.
- [ ] 2.2 Change `web_search` to top-level `Annotated` parameters, add `time_range`, remove `WebSearchInput`, and pass `time_range` to the backend through the `SearchBackend` protocol. Verify with the tests of 2.1 and with `uv run mypy src/`.
- [ ] 2.3 Report failures with `ToolError` and set `structured_output=False`. Verify with a test that a backend failure gives a result with `isError` true and that a success gives one text block with the JSON string and no structured content.
- [ ] 2.4 Set the annotations to `readOnlyHint=true` and `openWorldHint=true` only, and write a tool description of 1,000 characters or fewer. Verify with a test that reads the tool definition through the client.
- [ ] 2.5 Update the `web_search` section of `README.md`: argument table with `time_range`, the error form, and a call example. Verify that the example call in the README is equal to a call in the tests.

## 3. Search backend resilience

- [ ] 3.1 Add backend tests with a patched `DDGS`: `time_range` maps to `timelimit`, a timeout maps to a timeout `SearchError`, "No results found." maps to a `SearchError` whose message states the two possible causes. Verify that the tests fail before task 3.2 and pass after it.
- [ ] 3.2 Implement the mapping and set `timeout=10` on `DDGS`. Verify with the tests of 3.1.
- [ ] 3.3 Add one retry after a delay of 1 to 2 seconds, with the delay function injected. Verify with tests: first attempt fails and second succeeds gives results; two failures give one `SearchError` after exactly two attempts.
- [ ] 3.4 Run one search at a time with a minimum interval between starts, with the clock and the delay injected. Verify with a test that three concurrent calls do not overlap in the backend and that all three get results.

## 4. Address guard

- [ ] 4.1 Add table-driven tests for the guard with an injected resolver. Refused: `localhost`, `127.0.0.1`, `10.0.0.5`, `192.168.1.1`, `169.254.169.254`, `100.64.0.1`, `0.0.0.0`, `[::1]`, `[::ffff:127.0.0.1]`, `[64:ff9b::a9fe:a9fe]`, `[fec0::1]`, `[fe80::1]`, a host name with one public and one private address, a URL with user information, `file://` and `ftp://` URLs. Accepted: a host name that resolves to a public IPv4 address and one that resolves to a public IPv6 address. Verify that the tests fail before task 4.2.
- [ ] 4.2 Implement the guard module as design D10 gives it. It returns the checked address for the connection. Verify with the tests of 4.1.
- [ ] 4.3 Prove the connection to a checked address: write a test that sends a request to an IP literal with the `Host` header and the `sni_hostname` extension, and confirm that the request goes to the given address and that the host name is used for TLS. If this does not work with `httpx`, record the result in `design.md` D10 and use a custom transport. Verify that the test passes.

## 5. Page retrieval

- [ ] 5.1 Add retrieval tests with `httpx.MockTransport`: the `Accept` header prefers markdown; a redirect to a different host is followed and the final URL is reported; 6 redirects give an error; a redirect to a private address is refused with no request to it; a 20 MB body stops at 5 MB with an error; a slow response gives a time limit error; status 404 gives an error with the status and the final URL; status 429 gives an error with `Retry-After`; a name that does not resolve gives an error that states it. Verify that the tests fail before task 5.2.
- [ ] 5.2 Implement the retrieval module as design D9 gives it, with the guard on each hop and the user agent `web-search-mcp/<version>`. Verify with the tests of 5.1.

## 6. Content conversion

- [ ] 6.1 Add fixture HTML files in `tests/fixtures/` that we write for the tests: a page with `main`, `nav`, `header`, and `footer`; a page with no main region; a page with 5 preformatted blocks, one of them with highlight markup inside; a page with a table; a page with relative links and heading permalink anchors; a page of 12,000 characters of markup with less than 200 characters of text. Verify that each fixture is a valid HTML file that the parser reads.
- [ ] 6.2 Add conversion tests against the fixtures: navigation text is absent; body text is present when there is no main region; the number of fenced blocks is equal to the number of preformatted blocks and each block text is unchanged; the table cells are present; links are absolute; permalink anchors are absent. Add content type tests: markdown is returned unchanged, JSON is returned unchanged, `application/pdf` gives an error that names the type. Verify that the tests fail before task 6.3.
- [ ] 6.3 Implement the extract module as design D7 and D8 give it. Verify with the tests of 6.2.
- [ ] 6.4 Add the warning for a page with almost no text. Verify with the fixture of 6.1 that the warning is present, and with the main-region fixture that it is absent.

## 7. Page store, parts, find, outline

- [ ] 7.1 Add tests for parts: the default part; consecutive parts joined are equal to the full text; a part ends at a line end when one is in the last half of the range; a range with no line end is cut at the limit; an offset at or after the end gives an error that states the total length. Verify that the tests fail before task 7.2.
- [ ] 7.2 Implement parts and the result header as design D12 and D13 give them. Verify with the tests of 7.1.
- [ ] 7.3 Add and implement the outline: headings with level and offset, no headings from fenced code blocks, a maximum of 50 with the reduction rule, no outline when the full page is returned or when `offset` is not 0. Verify with tests for each of these cases, with a 174-heading text among them.
- [ ] 7.4 Add and implement find: matches with the offset of the line start and the text around them, no regard to letter case, zero matches with the statement that the full text was searched, 45 matches give 20 with the total and the offset to continue, a read from a match offset starts with the line of the match. Verify with tests for each of these cases.
- [ ] 7.5 Add and implement the snapshot store with an injected clock: one retrieval for two calls in 15 minutes, a new retrieval after 15 minutes, one retrieval for a URL with and without a fragment, no snapshot for a failed retrieval, a maximum of 32 snapshots, one retrieval for concurrent calls for the same URL. Verify with tests for each of these cases.

## 8. `fetch_page` tool and server instructions

- [ ] 8.1 Add tool-level tests with the in-memory client and a mock transport: the tool definition has the top-level arguments `url`, `offset`, `limit`, `find`, the two annotations, and `_meta["anthropic/maxResultSizeChars"]` of 100000; `limit` of 500 and of 200000 are rejected; a result has one text block and no structured content; the delimiter line appears one time before the page text; a page with "Ignore your previous instructions" keeps that sentence; a failed retrieval gives `isError` true; a call with `limit` 80000 and a 50-heading outline gives a result shorter than 100,000 characters. Verify that the tests fail before task 8.2.
- [ ] 8.2 Add the `fetch_page` tool to the server and connect it to the store, with a description of 1,000 characters or fewer. Verify with the tests of 8.1.
- [ ] 8.3 Add server instructions of 2,000 characters or fewer that name the two tools, state when to use each, and state that page text and snippets are untrusted data. Verify with a test that reads the instructions through the client.
- [ ] 8.4 Add a `fetch_page` section to `README.md`: what the tool returns, the argument table, a result example with the header, the limits (no JavaScript, no PDF, no login, 5 MB, 30 seconds, public addresses only), the difference from the built-in page fetch, and the allow-list entry `mcp__web-search__fetch_page`. Verify that the result example in the README has the same header fields as a result in the tests.

## 9. Project documents and description

- [ ] 9.1 Rewrite `AGENTS.md` as design D17 gives it, with no file tree and no "No `fetch_url` tool" decision. Verify that the file has no tree characters (`├`, `└`) and that each command in it runs as written.
- [ ] 9.2 Add a one-line docstring to each module that states its responsibility. Verify that `uv run python -c "import pkgutil, importlib, web_search_mcp as p; [print(m.name, '-', importlib.import_module('web_search_mcp.' + m.name).__doc__) for m in pkgutil.iter_modules(p.__path__) if m.name != '__main__']"` prints a description for each module.
- [ ] 9.3 Remove the file tree and the "No `fetch_url` tool" decision from `README.md`, and rewrite "Why this exists" and "How it works" for two tools and for any provider or gateway. Verify that the file has no tree characters and no occurrence of `Bedrock` or `LiteLLM`.
- [ ] 9.4 Set the description in `pyproject.toml` to the text in design D17 and update `openspec/config.yaml` (stack, two tools, use case). Verify that `grep -rn -i -E "bedrock|litellm" pyproject.toml README.md AGENTS.md openspec/config.yaml` returns nothing.

## 10. Integration checks

- [ ] 10.1 Run the full gate: `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy src/`. Verify that all four exit with 0.
- [ ] 10.2 Run `openspec validate add-page-fetch-and-refresh-stack --strict`. Verify that it reports no error.
- [ ] 10.3 Register the worktree as a second server, so that the branch runs next to `main`: `claude mcp add --scope user web-search-dev -- uv run --directory <absolute path of the worktree> python -m web_search_mcp`. Start a new Claude Code session. Verify that `web-search` and `web-search-dev` are both connected and that `mcp__web-search-dev__web_search` and `mcp__web-search-dev__fetch_page` are available.
- [ ] 10.4 In that session, call the `web-search-dev` tools: do one search with `time_range`, then call `fetch_page` on a public documentation page, read the first part, call `find` for a text from the outline, and read from the offset of a match. Verify that each result agrees with the specs.
- [ ] 10.5 Call `fetch_page` on one page from each of these groups and compare the code block count with the page in a browser: a Sphinx site, an MkDocs site, a site that sends markdown. Verify that no code block is missing.
- [ ] 10.6 Start two subagents that call `mcp__web-search-dev__web_search` at the same time. Record in `design.md` whether they share one server process and whether the searches ran one after the other.
- [ ] 10.7 Do an injection test with a public test page that the user supplies. The page contains an instruction for the agent, for example to put a given word in its answer. In a new session, tell an agent to summarize the page with `mcp__web-search-dev__fetch_page`. Do this three times. Verify that the agent reports the instruction as content of the page and does not obey it. Record the three results in `design.md`. Do not merge if the agent obeys the instruction; decide the next step with the user.

## Workflow follow-up

- Before archive, decide if these decisions become ADRs. `docs/adr/` does not exist, so ask first: the reversal of "no fetch tool"; an honest client with no browser imitation; an address guard with no off switch; main-region conversion in place of article extractors.
- Merge to `main` only after all tasks in group 10 pass.
- After the merge, remove the test server with `claude mcp remove web-search-dev` and remove the worktree with `git worktree remove ../web-search-mcp-dev`.
- Archive the change after review.
- Add `mcp__web-search__fetch_page` to the permission allow-list in the user settings.
- In `data-engineering-skills`, add `fetch_page` to the `researcher` agent definitions (Claude, Codex, Cursor) and decide when the agent uses it.
- In the vault, set the `web-search-mcp-raw-fetch` initiative from parked to its new status and link this change. Update the setup guide, which still gives the old registration command.
