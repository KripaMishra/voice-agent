"""The interviewer agent's pieces that do not need a live session."""

import pytest
from livekit.agents import llm
from livekit.agents.llm.tool_context import is_function_tool

from agent import Interviewer, interview_id_from_room, message_text


@pytest.mark.parametrize(
    ("room_name", "expected"),
    [
        ("interview-abc123", "abc123"),
        ("interview-", None),
        ("interview", None),
        ("other-room", None),
        ("", None),
    ],
)
def test_room_names_map_back_to_interviews(room_name, expected):
    assert interview_id_from_room(room_name) == expected


def test_joins_the_text_parts_of_a_message():
    message = llm.ChatMessage(role="assistant", content=["  Hello.  ", "Again."])

    assert message_text(message) == "Hello. Again."


def test_a_message_with_no_text_comes_back_empty():
    assert message_text(llm.ChatMessage(role="assistant", content=["   "])) == ""


def test_the_interviewer_exposes_a_record_answer_tool():
    tool = Interviewer.__dict__["record_answer"]

    assert is_function_tool(tool)
    assert tool.id == "record_answer"
    assert "checklist item" in tool.info.description


async def test_record_answer_closes_the_item(make_session):
    session, item_ids = make_session()
    interviewer = Interviewer(instructions="x", session=session)

    result = await interviewer.record_answer(None, item_ids[0])

    assert result == "recorded"
    assert [item.id for item in session.pending_items()] == item_ids[1:]


async def test_record_answer_reports_a_bad_item_instead_of_raising(make_session):
    session, _ = make_session()
    interviewer = Interviewer(instructions="x", session=session)

    result = await interviewer.record_answer(None, "not-an-item")

    assert "could not record" in result
