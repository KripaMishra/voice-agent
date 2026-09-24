"""Test doubles for the LiveKit LLM surface."""

from types import SimpleNamespace

from livekit.agents import llm


def text_chunk(text: str) -> llm.ChatChunk:
    return llm.ChatChunk(
        id="chunk",
        delta=llm.ChoiceDelta(role="assistant", content=text, tool_calls=[]),
    )


def tool_chunk(name: str, arguments: str, call_id: str = "call-1") -> llm.ChatChunk:
    return llm.ChatChunk(
        id="chunk",
        delta=llm.ChoiceDelta(
            role="assistant",
            content="",
            tool_calls=[
                llm.FunctionToolCall(name=name, arguments=arguments, call_id=call_id)
            ],
        ),
    )


class FakeStream:
    def __init__(self, chunks):
        self._chunks = list(chunks)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_exc):
        return False

    def __aiter__(self):
        return self._iterate()

    async def _iterate(self):
        for chunk in self._chunks:
            yield chunk


class FakeModel:
    """Replays canned rounds and records what it was asked."""

    def __init__(self, *rounds):
        self._rounds = [list(round_) for round_ in rounds]
        self.calls = []

    def chat(self, *, chat_ctx, tools=None, **_kwargs):
        self.calls.append(SimpleNamespace(chat=chat_ctx.copy(), tools=tools))
        if not self._rounds:
            raise AssertionError("the model was called more times than expected")
        return FakeStream(self._rounds.pop(0))


class RecordingSearch:
    def __init__(self, result: str = "Acme builds logistics software.") -> None:
        self.result = result
        self.queries: list[str] = []

    async def __call__(self, query: str) -> str:
        self.queries.append(query)
        return self.result


def context_text(chat) -> str:
    parts = []
    for item in chat.items:
        if hasattr(item, "content"):
            parts.append(str(item.content))
        elif hasattr(item, "output"):
            parts.append(str(item.output))
    return "\n".join(parts)
