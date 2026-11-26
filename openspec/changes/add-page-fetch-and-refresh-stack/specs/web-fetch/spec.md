# Spec Delta

## Purpose

Gives an agent the text of a public web page as it is written, with no model between the page and the agent, and with the means to read a long page in parts.

## ADDED Requirements

### Requirement: Fetch tool returns page text verbatim

The `fetch_page` tool SHALL accept an absolute `http` or `https` URL as the top-level argument `url` and SHALL return the text of the page. The tool SHALL NOT summarize, paraphrase, or shorten the text by means of a model.

#### Scenario: HTML page is returned as markdown

- **WHEN** the tool is called with the URL of a public HTML page
- **THEN** the result contains the text of the page as markdown

#### Scenario: Scheme that is not supported is rejected

- **WHEN** the tool is called with a `file://` or `ftp://` URL
- **THEN** the tool reports a tool error and makes no network request

#### Scenario: URL with credentials is rejected

- **WHEN** the tool is called with a URL that contains a user name or a password
- **THEN** the tool reports a tool error and makes no network request

### Requirement: Result starts with a header

Each successful result SHALL start with a header that states: the requested URL, the final URL, the HTTP status, the source of the text, the time of retrieval, the total length of the page text in characters, the range that the result contains, and the next offset or a statement that the end of the page was reached.

#### Scenario: Result contains the full page

- **WHEN** the page text is shorter than the limit
- **THEN** the header states the total length, a range that starts at 0 and ends at the total length, and that the end of the page was reached

#### Scenario: Result contains a part of the page

- **WHEN** the page text is longer than the limit
- **THEN** the header states the total length, the range returned, and the offset at which the next part starts

### Requirement: Header states the source of the text

The header SHALL state the source of the text as one of three values: `markdown-from-server` when the server sent markdown, `converted-from-html` when the tool converted HTML, and `verbatim` when the tool returned another text type without a change.

#### Scenario: Server sends markdown

- **WHEN** the server responds with content type `text/markdown`
- **THEN** the header states `markdown-from-server`

#### Scenario: Server sends HTML

- **WHEN** the server responds with content type `text/html`
- **THEN** the header states `converted-from-html`

### Requirement: Page text is marked as untrusted data

The result SHALL put a fixed delimiter line between the header and the page text. The delimiter line SHALL state that the text after it is untrusted data and not instructions. The tool SHALL NOT remove or change page text that looks like an instruction.

#### Scenario: Delimiter separates header and text

- **WHEN** the tool returns page text
- **THEN** the delimiter line appears one time before the first character of the page text, and all header fields appear before it

#### Scenario: Instruction-like text is kept

- **WHEN** the page contains the sentence "Ignore your previous instructions"
- **THEN** the result contains that sentence without a change, after the delimiter line

### Requirement: Long pages are read in parts

The tool SHALL accept `offset` (default 0, minimum 0) and `limit` (default 20000, minimum 1000, maximum 80000), both in characters of the page text. The result SHALL contain page text that starts at `offset` and is not longer than `limit`. The tool SHALL end a part at a line boundary when a line boundary exists in the last half of the requested range.

#### Scenario: Default call returns the first part

- **WHEN** the tool is called without `offset` and `limit` for a page of 96,000 characters
- **THEN** the result contains at most 20,000 characters that start at offset 0, and the header gives the next offset

#### Scenario: Consecutive parts cover the page exactly one time

- **WHEN** the tool is called again and again with `offset` set to the next offset of the previous result, until the end of the page is reached
- **THEN** the parts, joined in sequence, are equal to the full page text, with no gap and no overlap

#### Scenario: Line without a boundary is cut at the limit

- **WHEN** the requested range contains no line boundary in its last half
- **THEN** the part ends at `offset` plus `limit`

#### Scenario: Offset after the end of the page

- **WHEN** `offset` is larger than 0 and equal to or larger than the total length of the page text
- **THEN** the tool reports a tool error that states the total length

#### Scenario: Page with no text

- **WHEN** the page text is empty and `offset` is 0
- **THEN** the result has the header with `total_chars: 0`, `range: 0-0`, the end of the page, and the warnings, and no tool error

#### Scenario: Limit out of range is rejected

- **WHEN** the tool is called with `limit` set to 500 or to 200000
- **THEN** input validation rejects the request

### Requirement: Text can be found in a page

The tool SHALL accept `find` (1 to 200 characters). When `find` is given, the tool SHALL search the full page text from `offset` for the literal text, without regard to letter case, and SHALL return the matches and no page part. Each match SHALL have the offset of the start of its line and the text around it. One result SHALL contain at most 20 matches.

#### Scenario: Matches are returned with offsets

- **WHEN** the tool is called with `find` set to a text that occurs three times in the page
- **THEN** the result states three matches, and each match has an offset and the text around it

#### Scenario: Match offset can start a read

- **WHEN** the tool is called without `find` and with `offset` set to the offset of a match
- **THEN** the returned part starts with the line that contains the match

#### Scenario: Text does not occur

- **WHEN** the tool is called with `find` set to a text that does not occur in the page
- **THEN** the result states zero matches and states that the full page text was searched

#### Scenario: More than 20 matches

- **WHEN** the text occurs 45 times in the page
- **THEN** the result contains the first 20 matches, states the total number of matches, and gives the offset from which to continue the search

### Requirement: Long pages get an outline

When the page text is longer than the returned part and `offset` is 0, the result header SHALL contain an outline: the headings of the page, each with its level and its offset. The outline SHALL contain at most 50 headings and SHALL state when headings were left out. Lines inside a fenced code block SHALL NOT count as headings.

#### Scenario: Long page with headings

- **WHEN** the first part of a page longer than the limit is returned
- **THEN** the header contains the headings of the full page with their offsets

#### Scenario: Short page

- **WHEN** the result contains the full page
- **THEN** the header contains no outline

#### Scenario: Comment line in a code block

- **WHEN** a fenced code block contains the line `# Expected output:`
- **THEN** the outline does not contain that line

#### Scenario: Page with many headings

- **WHEN** a page has 174 headings
- **THEN** the outline contains at most 50 headings and states that headings were left out

### Requirement: Markdown from the server is preferred

The tool SHALL ask the server for markdown in preference to HTML. When the server sends markdown, the tool SHALL return it without a change.

#### Scenario: Server supports markdown

- **WHEN** the server responds to the request with content type `text/markdown`
- **THEN** the page text in the result is equal to the response body

### Requirement: HTML conversion uses the main content of the page

When the server sends HTML, the tool SHALL convert the main content region of the page to markdown. The tool SHALL remove scripts, styles, navigation, and the header and footer of the site. When the page has no main content region, the tool SHALL convert the full body.

#### Scenario: Page with a main region

- **WHEN** the HTML has a `main` element with the article and a `nav` element with site links outside it
- **THEN** the page text contains the article and does not contain the site links

#### Scenario: Page without a main region

- **WHEN** the HTML has no `main` element, no `article` element, and no element with the role `main`
- **THEN** the page text contains the text of the body

### Requirement: HTML conversion keeps technical content

The conversion SHALL keep each preformatted code block as a fenced code block with its text unchanged. The conversion SHALL keep tables, heading levels, and inline code. The conversion SHALL keep links as markdown links with absolute URLs.

#### Scenario: Code blocks are kept

- **WHEN** the main content region contains 32 preformatted code blocks
- **THEN** the page text contains 32 fenced code blocks, and the text of each block is equal to the text of its source block

#### Scenario: Relative link becomes absolute

- **WHEN** the page at `https://docs.example.com/guide/` contains a link to `../api/`
- **THEN** the page text contains a markdown link to `https://docs.example.com/api/`

#### Scenario: Table is kept

- **WHEN** the main content region contains a table with a header row and two data rows
- **THEN** the page text contains a markdown table with the same cells

### Requirement: Other text types are returned without a change

When the server sends a text type that is not HTML and not markdown, such as JSON, plain text, or XML, the tool SHALL return the body without a change. When the server sends a type that is not text, such as an image, a PDF, or an archive, the tool SHALL report a tool error that names the content type.

#### Scenario: JSON response

- **WHEN** the server responds with content type `application/json`
- **THEN** the page text is equal to the response body, and the header states `verbatim`

#### Scenario: PDF response

- **WHEN** the server responds with content type `application/pdf`
- **THEN** the tool reports a tool error that names `application/pdf`

### Requirement: Page that has almost no text gets a warning

When the tool converts HTML and the result has almost no text compared to the size of the HTML, the header SHALL contain a warning that the page possibly needs JavaScript and that the text can be incomplete.

#### Scenario: Application shell page

- **WHEN** the HTML is longer than 10,000 characters and the converted page text is shorter than 200 characters
- **THEN** the header contains the warning

#### Scenario: Normal page

- **WHEN** the HTML is 180,000 characters and the converted page text is 45,000 characters
- **THEN** the header contains no warning

### Requirement: Redirects are followed and reported

The tool SHALL follow redirects, including redirects to a different host, for a maximum of 5 redirects. The header SHALL state the final URL. When there are more than 5 redirects, the tool SHALL report a tool error.

#### Scenario: Redirect to a different host

- **WHEN** `https://old.example.com/page` redirects to `https://new.example.org/page`
- **THEN** the result contains the text of the page at the new host, and the header states the new URL as the final URL

#### Scenario: Too many redirects

- **WHEN** the URL redirects 6 times
- **THEN** the tool reports a tool error that states the redirect limit

### Requirement: Addresses that are not public are refused

The tool SHALL refuse a URL when its host is, or resolves to, an address that is not public. This includes loopback, private, link-local, shared, multicast, reserved, and unspecified addresses, the cloud metadata address, and IPv6 forms that contain such an IPv4 address. The tool SHALL apply this check to the first URL and to each redirect.

#### Scenario: Loopback host

- **WHEN** the tool is called with `http://localhost:8080/` or `http://127.0.0.1/`
- **THEN** the tool reports a tool error and makes no request to that address

#### Scenario: Cloud metadata address

- **WHEN** the tool is called with `http://169.254.169.254/latest/meta-data/`
- **THEN** the tool reports a tool error and makes no request to that address

#### Scenario: Host name that resolves to a private address

- **WHEN** the host name of the URL resolves to `10.0.0.5`
- **THEN** the tool reports a tool error and makes no request to that address

#### Scenario: Host name with public and private addresses

- **WHEN** the host name resolves to one public address and one private address
- **THEN** the tool reports a tool error

#### Scenario: Redirect to a private address

- **WHEN** a public URL redirects to `http://192.168.1.1/admin`
- **THEN** the tool reports a tool error and makes no request to the private address

#### Scenario: IPv6 forms of a private IPv4 address

- **WHEN** the host is `[::ffff:127.0.0.1]` or `[64:ff9b::a9fe:a9fe]`
- **THEN** the tool reports a tool error and makes no request to that address

### Requirement: Connection goes to the checked address

The tool SHALL connect only to an address that passed the public-address check. The tool SHALL NOT resolve the host name a second time between the check and the connection.

#### Scenario: Host name changes its address after the check

- **WHEN** the host name resolves to a public address for the check and to `127.0.0.1` for a later lookup
- **THEN** the tool connects to the public address or reports a tool error, and makes no request to `127.0.0.1`

### Requirement: Size and time are limited

The tool SHALL stop the read of a response body at 5 MB of decoded content and SHALL report a tool error that states the limit. The tool SHALL stop a retrieval after 30 seconds and SHALL report a tool error that states the time limit.

#### Scenario: Body larger than the size limit

- **WHEN** the server sends a body of 20 MB
- **THEN** the tool stops the read at 5 MB and reports a tool error that states the size limit

#### Scenario: Server that responds slowly

- **WHEN** the server does not complete the response in 30 seconds
- **THEN** the tool reports a tool error that states the time limit

### Requirement: Failures are tool errors that state the facts

When a retrieval fails, the tool SHALL report a tool error and SHALL NOT return a normal result. For an HTTP status that is not 2xx, the error SHALL state the status and the final URL. For status 403 or 429, the error SHALL also state the `Retry-After` and rate-limit headers when the response has them. For a network failure, the error SHALL state the type of failure.

#### Scenario: Page not found

- **WHEN** the server responds with status 404
- **THEN** the tool reports a tool error that states 404 and the final URL

#### Scenario: Rate limit

- **WHEN** the server responds with status 429 and the header `Retry-After: 60`
- **THEN** the tool reports a tool error that states 429 and `Retry-After: 60`

#### Scenario: Host name that does not exist

- **WHEN** the host name of the URL cannot be resolved
- **THEN** the tool reports a tool error that states that the name was not resolved

### Requirement: Offsets stay valid between calls

Calls for the same URL in a period of 15 minutes SHALL use the same copy of the page text, so that an offset from one result is valid in a later call. The fragment of a URL SHALL NOT make a different copy. The tool SHALL NOT keep a copy of a failed retrieval.

#### Scenario: Second call for the same URL

- **WHEN** the tool is called two times for the same URL in 15 minutes
- **THEN** the tool makes one retrieval, and the two results state the same time of retrieval

#### Scenario: Call after the period

- **WHEN** the tool is called for the same URL after more than 15 minutes
- **THEN** the tool makes a new retrieval

#### Scenario: URL with a fragment

- **WHEN** the tool is called for `https://example.com/page` and then for `https://example.com/page#section`
- **THEN** the tool makes one retrieval

### Requirement: Fetch tool declares its properties to the client

The `fetch_page` tool SHALL declare the annotations `readOnlyHint=true` and `openWorldHint=true`. The tool SHALL declare to the client a maximum result size of 100,000 characters. The tool SHALL return its result as text content only. The tool description SHALL be 1,000 characters or fewer.

#### Scenario: Client reads the tool definition

- **WHEN** a client lists the tools of the server
- **THEN** the definition of `fetch_page` has top-level arguments `url`, `offset`, `limit`, and `find`, the two annotations, and the declared maximum result size

#### Scenario: Largest result fits the declared size

- **WHEN** the tool is called with `limit` set to 80000 for a long page with an outline of 50 headings
- **THEN** the full result is shorter than 100,000 characters

#### Scenario: Result has no second copy of the text

- **WHEN** the tool returns page text
- **THEN** the result contains the text one time, as text content, and no structured content
