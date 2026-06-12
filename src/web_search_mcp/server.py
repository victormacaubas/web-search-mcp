import json
import logging
import sys

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from web_search_mcp.models import WebSearchInput
from web_search_mcp.search import DdgsSearchBackend, SearchError

_handler = logging.StreamHandler(sys.stderr)
_handler.setFormatter(
    logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
)
logging.getLogger().addHandler(_handler)
logging.getLogger().setLevel(logging.INFO)

logger = logging.getLogger(__name__)

mcp = FastMCP("web_search_mcp")
backend = DdgsSearchBackend()


@mcp.tool(
    name="web_search",
    annotations=ToolAnnotations(
        title="Web Search",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    ),
)
async def web_search(params: WebSearchInput) -> str:
    """Search the web and return titles, URLs, and text snippets for matching pages.

    Uses DuckDuckGo as the search backend — no API key required. Results are
    suitable for driving follow-up fetches with WebFetch.

    Args:
        params (WebSearchInput): Validated search parameters containing:
            - query (str): Search query, 1–500 characters, must not be whitespace-only.
            - max_results (int): Maximum results to return, 1–20 (default: 5).
            - region (str | None): Locale code such as "us-en" or "br-pt". When
              omitted the backend's worldwide default ("wt-wt") is used.

    Returns:
        str: JSON-formatted string on success:

            {
                "results": [
                    {
                        "title": str,    # Page title
                        "url": str,      # Full URL of the result
                        "snippet": str   # Short excerpt from the page
                    },
                    ...
                ]
            }

            Or an error string on failure:

            "Error: <human-readable reason>"

    Examples:
        - "Python asyncio tutorial" -> returns up to 5 results about asyncio
        - query="news", region="br-pt" -> returns Brazilian Portuguese news results
        - query="  " -> rejected by input validation before any search is performed

    Error cases:
        - Whitespace-only or empty query: rejected by Pydantic validation
        - max_results outside 1–20: rejected by Pydantic validation
        - Backend failure (network error, rate limit, DuckDuckGo unavailable):
          returns "Error: Search failed: <detail>"
    """
    try:
        results = await backend.search(params.query, params.max_results, params.region)
        return json.dumps(
            {
                "results": [
                    {"title": r.title, "url": r.url, "snippet": r.snippet}
                    for r in results
                ]
            }
        )
    except SearchError as exc:
        logger.error("web_search failed for query %r: %s", params.query, exc)
        return f"Error: {exc}"
