"""Running a model to completion, executing any tools it asks for."""

import inspect
import json
import logging
import time
from collections.abc import Sequence
from uuid import uuid4

from livekit.agents.llm import (
    LLM,
    ChatContext,
    FunctionCall,
    FunctionCallOutput,
    FunctionToolCall,
    Tool,
)

logger = logging.getLogger("workflows.tool_loop")

DEFAULT_MAX_ROUNDS = 4


class ToolLoopError(RuntimeError):
    """Raised when the model never settles on an answer."""


async def complete_with_tools(
    model: LLM,
    *,
    system: str,
    user: str,
    tools: Sequence[Tool] = (),
    max_rounds: int = DEFAULT_MAX_ROUNDS,
) -> str:
    chat = ChatContext()
    chat.add_message(role="system", content=system)
    chat.add_message(role="user", content=user)

    available = list(tools)

    for _ in range(max_rounds):
        reply, calls = await _one_round(model, chat, available)
        if not calls:
            return reply
        for call in calls:
            chat.items.append(_call_item(call))
            chat.items.append(await _run_tool(available, call))

    raise ToolLoopError(f"model was still asking for tools after {max_rounds} rounds")


async def _one_round(
    model: LLM, chat: ChatContext, available: list[Tool]
) -> tuple[str, list[FunctionToolCall]]:
    text: list[str] = []
    calls: list[FunctionToolCall] = []

    async with model.chat(chat_ctx=chat, tools=available or None) as stream:
        async for chunk in stream:
            delta = chunk.delta
            if delta is None:
                continue
            if delta.content:
                text.append(delta.content)
            if delta.tool_calls:
                calls.extend(delta.tool_calls)

    return "".join(text), calls


def _call_item(call: FunctionToolCall) -> FunctionCall:
    return FunctionCall(
        id=uuid4().hex,
        call_id=call.call_id,
        name=call.name,
        arguments=call.arguments,
        created_at=time.time(),
        extra={},
    )


def _output_item(
    call: FunctionToolCall, output: str, *, is_error: bool
) -> FunctionCallOutput:
    return FunctionCallOutput(
        id=uuid4().hex,
        call_id=call.call_id,
        name=call.name,
        output=output,
        is_error=is_error,
        created_at=time.time(),
    )


async def _run_tool(
    available: list[Tool], call: FunctionToolCall
) -> FunctionCallOutput:
    tool = next(
        (candidate for candidate in available if candidate.id == call.name), None
    )
    if tool is None:
        return _output_item(call, f"no tool named {call.name}", is_error=True)

    try:
        arguments = json.loads(call.arguments or "{}")
    except json.JSONDecodeError as exc:
        return _output_item(
            call, f"arguments were not valid JSON: {exc}", is_error=True
        )

    if not isinstance(arguments, dict):
        return _output_item(call, "arguments must be a JSON object", is_error=True)

    try:
        result = tool(**arguments)
        if inspect.isawaitable(result):
            result = await result
    except Exception as exc:
        logger.warning("tool %s failed: %s", call.name, exc)
        return _output_item(call, str(exc), is_error=True)

    if not isinstance(result, str):
        result = json.dumps(result)
    return _output_item(call, result, is_error=False)
