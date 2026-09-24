"""Web search, exposed to the checklist generator as an LLM tool.

Company research is the one thing the checklist cannot derive from the resume
and the job description, so it is the only tool in the system.
"""

import logging
from typing import Any, Protocol

import httpx
from livekit.agents.llm import RawFunctionTool
from livekit.agents.llm.tool_context import RawFunctionToolInfo, ToolFlag

from config import Settings

logger = logging.getLogger("workflows.search")

TAVILY_ENDPOINT = "https://api.tavily.com/search"
MAX_RESULTS = 5
UNAVAILABLE = "web search is unavailable, so work from the job description alone"
FAILED = "web search failed, so work from the job description alone"


class WebSearch(Protocol):
    async def __call__(self, query: str) -> str: ...


class TavilySearch:
    def __init__(
        self,
        api_key: str,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
        timeout: float = 15.0,
    ) -> None:
        self._api_key = api_key
        self._transport = transport
        self._timeout = timeout

    async def __call__(self, query: str) -> str:
        async with httpx.AsyncClient(
            transport=self._transport, timeout=self._timeout
        ) as client:
            response = await client.post(
                TAVILY_ENDPOINT,
                json={
                    "api_key": self._api_key,
                    "query": query,
                    "search_depth": "basic",
                    "max_results": MAX_RESULTS,
                    "include_answer": True,
                },
            )
            response.raise_for_status()
        return summarise(response.json())


class UnavailableSearch:
    async def __call__(self, query: str) -> str:
        logger.warning("websearch called with no search provider configured")
        return UNAVAILABLE


def summarise(payload: dict[str, Any]) -> str:
    lines: list[str] = []
    answer = payload.get("answer")
    if isinstance(answer, str) and answer.strip():
        lines.append(answer.strip())
    for result in payload.get("results") or []:
        if not isinstance(result, dict):
            continue
        title, content = result.get("title"), result.get("content")
        if isinstance(title, str) and isinstance(content, str):
            lines.append(f"{title.strip()}: {content.strip()}")
    return "\n".join(lines) if lines else "no results"


def build_search(settings: Settings) -> WebSearch:
    if settings.tavily_api_key:
        return TavilySearch(settings.tavily_api_key)
    logger.warning("TAVILY_API_KEY is not set; company research will be skipped")
    return UnavailableSearch()


WEBSEARCH_SCHEMA: dict[str, Any] = {
    "name": "websearch",
    "description": (
        "Search the web. Use it to find what the company does and what it is "
        "currently working on, so the problem statement reflects the real "
        "product rather than the job description alone."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "A short search query, such as the company name.",
            }
        },
        "required": ["query"],
        "additionalProperties": False,
    },
}


def build_search_tool(search: WebSearch) -> RawFunctionTool:
    async def websearch(query: str) -> str:
        try:
            return await search(query)
        except Exception as exc:
            logger.warning("websearch failed: %s", exc)
            return FAILED

    return RawFunctionTool(
        websearch,
        RawFunctionToolInfo(
            name="websearch",
            raw_schema=WEBSEARCH_SCHEMA,
            flags=ToolFlag.NONE,
        ),
    )
