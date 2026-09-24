"""Running a model and executing the tools it asks for."""

import pytest
from fakes import FakeModel, RecordingSearch, context_text, text_chunk, tool_chunk
from livekit.agents import llm
from livekit.agents.llm import RawFunctionTool
from livekit.agents.llm.tool_context import RawFunctionToolInfo, ToolFlag

from workflows.search import build_search_tool
from workflows.tool_loop import ToolLoopError, complete_with_tools


def outputs_from(chat):
    return [item for item in chat.items if isinstance(item, llm.FunctionCallOutput)]


def calls_from(chat):
    return [item for item in chat.items if isinstance(item, llm.FunctionCall)]


def raw_tool(name, func):
    return RawFunctionTool(
        func,
        RawFunctionToolInfo(
            name=name,
            raw_schema={"name": name, "parameters": {"type": "object"}},
            flags=ToolFlag.NONE,
        ),
    )


async def test_returns_the_reply_when_no_tool_is_asked_for():
    model = FakeModel([text_chunk("hello")])

    assert await complete_with_tools(model, system="s", user="u") == "hello"


async def test_joins_streamed_text():
    model = FakeModel([text_chunk("he"), text_chunk("llo")])

    assert await complete_with_tools(model, system="s", user="u") == "hello"


async def test_sends_the_system_and_user_messages():
    model = FakeModel([text_chunk("ok")])

    await complete_with_tools(model, system="be brief", user="say hi")

    sent = context_text(model.calls[0].chat)
    assert "be brief" in sent
    assert "say hi" in sent


async def test_runs_a_tool_and_feeds_the_result_back():
    async def search(query: str) -> str:
        return f"results for {query}"

    tool = build_search_tool(search)
    model = FakeModel(
        [tool_chunk("websearch", '{"query": "acme"}')],
        [text_chunk("done")],
    )

    reply = await complete_with_tools(model, system="s", user="u", tools=[tool])

    assert reply == "done"
    second = model.calls[1].chat
    assert [item.name for item in calls_from(second)] == ["websearch"]
    assert [item.output for item in outputs_from(second)] == ["results for acme"]
    assert outputs_from(second)[0].is_error is False


async def test_the_models_own_call_is_kept_in_context():
    tool = build_search_tool(RecordingSearch())
    model = FakeModel(
        [tool_chunk("websearch", '{"query": "acme"}')], [text_chunk("done")]
    )

    await complete_with_tools(model, system="s", user="u", tools=[tool])

    recorded = calls_from(model.calls[1].chat)[0]
    assert recorded.call_id == "call-1"
    assert recorded.arguments == '{"query": "acme"}'


async def test_an_unknown_tool_is_reported_to_the_model():
    model = FakeModel([tool_chunk("nope", "{}")], [text_chunk("recovered")])

    await complete_with_tools(model, system="s", user="u")

    reported = outputs_from(model.calls[1].chat)[0]
    assert reported.is_error is True
    assert "nope" in reported.output


async def test_arguments_that_are_not_json_are_reported():
    tool = build_search_tool(RecordingSearch())
    model = FakeModel([tool_chunk("websearch", "not json")], [text_chunk("recovered")])

    await complete_with_tools(model, system="s", user="u", tools=[tool])

    reported = outputs_from(model.calls[1].chat)[0]
    assert reported.is_error is True
    assert "JSON" in reported.output


async def test_arguments_that_are_not_an_object_are_reported():
    tool = build_search_tool(RecordingSearch())
    model = FakeModel([tool_chunk("websearch", '["a"]')], [text_chunk("recovered")])

    await complete_with_tools(model, system="s", user="u", tools=[tool])

    reported = outputs_from(model.calls[1].chat)[0]
    assert reported.is_error is True
    assert "object" in reported.output


async def test_a_raising_tool_becomes_an_error_output():
    async def explode(query: str) -> str:
        raise RuntimeError("kaboom")

    model = FakeModel(
        [tool_chunk("explode", '{"query": "x"}')], [text_chunk("recovered")]
    )

    reply = await complete_with_tools(
        model, system="s", user="u", tools=[raw_tool("explode", explode)]
    )

    assert reply == "recovered"
    reported = outputs_from(model.calls[1].chat)[0]
    assert reported.is_error is True
    assert "kaboom" in reported.output


async def test_gives_up_when_the_model_keeps_asking_for_tools():
    tool = build_search_tool(RecordingSearch())
    model = FakeModel(
        [tool_chunk("websearch", '{"query": "a"}')],
        [tool_chunk("websearch", '{"query": "b"}')],
    )

    with pytest.raises(ToolLoopError, match="2 rounds"):
        await complete_with_tools(
            model, system="s", user="u", tools=[tool], max_rounds=2
        )
