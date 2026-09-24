"""Building the checklist from a resume, a job description, and company research."""

import logging
from dataclasses import dataclass
from typing import Any

from livekit.agents.llm import LLM

from interview.enums import Track
from prompts import PromptCatalog, catalog
from workflows.replies import ReplyError, as_json_object
from workflows.search import WebSearch, build_search_tool
from workflows.tool_loop import complete_with_tools

logger = logging.getLogger("workflows.checklist")

PROMPT_NAME = "checklist_generation"
SECONDS_PER_QUESTION = 55
MINIMUM_CAPACITY = 2


class ChecklistError(ReplyError):
    """Raised when the model does not return a usable checklist."""


@dataclass(frozen=True)
class GeneratedItem:
    track: Track
    text: str


def capacity_for(time_budget_s: int) -> int:
    """How many questions a session of this length can actually reach."""
    return max(MINIMUM_CAPACITY, time_budget_s // SECONDS_PER_QUESTION)


def pool_size_for(capacity: int) -> int:
    """How many questions to ask for, given the interviewer picks from them."""
    return max(capacity * 2, 8)


async def generate_checklist(
    *,
    model: LLM,
    search: WebSearch,
    resume: str,
    jd: str,
    time_budget_s: int,
    prompts: PromptCatalog = catalog,
) -> list[GeneratedItem]:
    capacity = capacity_for(time_budget_s)
    system = prompts.render(
        PROMPT_NAME,
        budget_seconds=time_budget_s,
        capacity=capacity,
        pool=pool_size_for(capacity),
    )
    reply = await complete_with_tools(
        model,
        system=system,
        user=_brief(resume, jd),
        tools=[build_search_tool(search)],
    )
    return parse_checklist(reply)


def _brief(resume: str, jd: str) -> str:
    return f"# Resume\n\n{resume}\n\n# Job description\n\n{jd}"


def parse_checklist(reply: str) -> list[GeneratedItem]:
    payload = as_json_object(reply, error=ChecklistError, what="checklist reply")
    entries = payload.get("items")
    if not isinstance(entries, list):
        raise ChecklistError("the checklist reply had no items list")

    items: list[GeneratedItem] = []
    for entry in entries:
        item = _as_item(entry)
        if item is None:
            logger.warning("dropping an unusable checklist entry: %r", entry)
            continue
        items.append(item)

    if not items:
        raise ChecklistError("the checklist reply had no usable items")
    return items


def _as_item(entry: Any) -> GeneratedItem | None:
    if not isinstance(entry, dict):
        return None
    try:
        track = Track(entry.get("track"))
    except ValueError:
        return None
    text = entry.get("text")
    if not isinstance(text, str) or not text.strip():
        return None
    return GeneratedItem(track=track, text=text.strip())
