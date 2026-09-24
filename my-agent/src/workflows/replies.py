"""Pulling a JSON object out of a model reply."""

import json
from typing import Any

FENCE = "```"


class ReplyError(RuntimeError):
    """Raised when a model reply does not contain usable JSON."""


def as_json_object(reply: str, *, error: type[ReplyError], what: str) -> dict[str, Any]:
    text = _strip_fences(reply)
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        raise error(f"the {what} contained no JSON object")
    try:
        payload = json.loads(text[start : end + 1])
    except json.JSONDecodeError as exc:
        raise error(f"the {what} was not valid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise error(f"the {what} was not a JSON object")
    return payload


def _strip_fences(reply: str) -> str:
    text = reply.strip()
    if not text.startswith(FENCE):
        return text
    body = text[len(FENCE) :]
    newline = body.find("\n")
    if newline != -1:
        body = body[newline + 1 :]
    closing = body.rfind(FENCE)
    if closing != -1:
        body = body[:closing]
    return body.strip()
