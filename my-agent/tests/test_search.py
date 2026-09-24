"""The websearch tool handed to checklist generation."""

import httpx
import pytest

from config import Settings
from workflows.search import (
    FAILED,
    TAVILY_ENDPOINT,
    UNAVAILABLE,
    TavilySearch,
    UnavailableSearch,
    build_search,
    build_search_tool,
    summarise,
)

PAYLOAD = {
    "answer": "Acme builds logistics software.",
    "results": [
        {"title": "Acme", "content": "We move freight."},
        {"title": "Careers", "content": "Hiring backend engineers."},
    ],
}


def test_summarise_prefers_the_answer_then_lists_results():
    summary = summarise(PAYLOAD)

    assert summary.splitlines() == [
        "Acme builds logistics software.",
        "Acme: We move freight.",
        "Careers: Hiring backend engineers.",
    ]


def test_summarise_falls_back_to_results_without_an_answer():
    assert summarise({"results": PAYLOAD["results"]}).splitlines() == [
        "Acme: We move freight.",
        "Careers: Hiring backend engineers.",
    ]


def test_summarise_says_so_when_there_is_nothing():
    assert summarise({}) == "no results"
    assert summarise({"results": []}) == "no results"
    assert summarise({"answer": "   "}) == "no results"


def test_summarise_ignores_malformed_results():
    payload = {
        "results": [{"title": "ok", "content": "fine"}, "junk", {"title": "no content"}]
    }

    assert summarise(payload) == "ok: fine"


async def test_tavily_posts_the_query_and_summarises_the_reply():
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["body"] = request.read().decode()
        return httpx.Response(200, json=PAYLOAD)

    search = TavilySearch("secret", transport=httpx.MockTransport(handler))

    result = await search("what does Acme do")

    assert seen["url"] == TAVILY_ENDPOINT
    assert "what does Acme do" in str(seen["body"])
    assert "secret" in str(seen["body"])
    assert result.startswith("Acme builds logistics software.")


async def test_tavily_raises_on_an_error_response():
    transport = httpx.MockTransport(lambda _request: httpx.Response(401, json={}))
    search = TavilySearch("bad-key", transport=transport)

    with pytest.raises(httpx.HTTPStatusError):
        await search("anything")


async def test_unavailable_search_says_so():
    assert await UnavailableSearch()("anything") == UNAVAILABLE


def test_build_search_uses_tavily_when_a_key_is_present():
    assert isinstance(build_search(Settings(tavily_api_key="k")), TavilySearch)


def test_build_search_degrades_without_a_key():
    assert isinstance(build_search(Settings(tavily_api_key=None)), UnavailableSearch)


def test_the_tool_is_named_websearch_and_takes_a_query():
    tool = build_search_tool(UnavailableSearch())

    assert tool.id == "websearch"
    assert tool.info.raw_schema["parameters"]["required"] == ["query"]


async def test_the_tool_returns_the_search_result():
    async def fake(query: str) -> str:
        return f"results for {query}"

    tool = build_search_tool(fake)

    assert await tool(query="acme") == "results for acme"


async def test_the_tool_reports_a_failure_instead_of_raising():
    async def broken(query: str) -> str:
        raise httpx.ConnectError("no network")

    tool = build_search_tool(broken)

    assert await tool(query="acme") == FAILED
