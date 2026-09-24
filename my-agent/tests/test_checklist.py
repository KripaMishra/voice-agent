"""Building a checklist from a resume, a job description, and research."""

import pytest
from fakes import FakeModel, RecordingSearch, context_text, text_chunk, tool_chunk

from interview.enums import Track
from workflows.checklist import (
    ChecklistError,
    capacity_for,
    generate_checklist,
    parse_checklist,
    pool_size_for,
)

ONE_ITEM = '{"items": [{"track": "resume", "text": "Tell me about the migration."}]}'


def test_capacity_scales_with_the_budget():
    assert capacity_for(300) == 5
    assert capacity_for(600) == 10


def test_capacity_never_drops_below_a_usable_floor():
    assert capacity_for(55) == 2
    assert capacity_for(10) == 2


def test_the_pool_leaves_the_interviewer_room_to_choose():
    assert pool_size_for(5) == 10
    assert pool_size_for(2) == 8


def test_parses_a_plain_json_reply():
    items = parse_checklist(ONE_ITEM)

    assert [(item.track, item.text) for item in items] == [
        (Track.RESUME, "Tell me about the migration.")
    ]


def test_parses_a_fenced_reply():
    assert parse_checklist(f"```json\n{ONE_ITEM}\n```")[0].text == (
        "Tell me about the migration."
    )


def test_parses_json_surrounded_by_prose():
    assert parse_checklist(f"Sure!\n{ONE_ITEM}\nHope that helps.")[0].text == (
        "Tell me about the migration."
    )


def test_strips_whitespace_from_the_question():
    assert (
        parse_checklist('{"items": [{"track": "discussion", "text": "  Why?  "}]}')[
            0
        ].text
        == "Why?"
    )


def test_drops_unusable_entries_but_keeps_the_rest():
    reply = """{"items": [
        {"track": "resume", "text": "Good one."},
        {"track": "nonsense", "text": "Unknown track."},
        {"track": "resume", "text": "   "},
        {"track": "resume"},
        "not an object",
        {"track": "discussion", "text": "Also good."}
    ]}"""

    items = parse_checklist(reply)

    assert [item.text for item in items] == ["Good one.", "Also good."]


def test_raises_when_nothing_is_usable():
    with pytest.raises(ChecklistError, match="no usable items"):
        parse_checklist('{"items": [{"track": "nonsense", "text": "x"}]}')


def test_raises_without_an_items_list():
    with pytest.raises(ChecklistError, match="no items list"):
        parse_checklist('{"questions": []}')


def test_raises_without_any_json():
    with pytest.raises(ChecklistError, match="no JSON object"):
        parse_checklist("I could not build a checklist.")


def test_raises_on_malformed_json():
    with pytest.raises(ChecklistError, match="not valid JSON"):
        parse_checklist('{"items": [}')


async def test_generate_checklist_asks_for_a_sized_pool_and_returns_items():
    model = FakeModel(
        [
            text_chunk(
                '{"items": [{"track": "discussion", "text": "How would you cache this?"}]}'
            )
        ]
    )

    items = await generate_checklist(
        model=model,
        search=RecordingSearch(),
        resume="Ten years of Python.",
        jd="Backend engineer on our logistics platform.",
        time_budget_s=300,
    )

    assert [(item.track, item.text) for item in items] == [
        (Track.DISCUSSION, "How would you cache this?")
    ]

    sent = context_text(model.calls[0].chat)
    assert "300 seconds" in sent
    assert "about 5 questions" in sent
    assert "about 10 questions" in sent
    assert "Ten years of Python." in sent
    assert "Backend engineer on our logistics platform." in sent


async def test_generate_checklist_attaches_the_websearch_tool():
    model = FakeModel([text_chunk(ONE_ITEM)])

    await generate_checklist(
        model=model,
        search=RecordingSearch(),
        resume="r",
        jd="j",
        time_budget_s=300,
    )

    assert [tool.id for tool in model.calls[0].tools] == ["websearch"]


async def test_generate_checklist_includes_what_the_search_found():
    model = FakeModel(
        [tool_chunk("websearch", '{"query": "Acme logistics"}')],
        [text_chunk(ONE_ITEM)],
    )
    search = RecordingSearch("Acme builds freight scheduling software.")

    items = await generate_checklist(
        model=model,
        search=search,
        resume="r",
        jd="j",
        time_budget_s=300,
    )

    assert search.queries == ["Acme logistics"]
    assert items[0].text == "Tell me about the migration."
    assert "Acme builds freight scheduling software." in context_text(
        model.calls[1].chat
    )


async def test_generate_checklist_rejects_a_reply_it_cannot_use():
    model = FakeModel([text_chunk("I am not going to answer that.")])

    with pytest.raises(ChecklistError):
        await generate_checklist(
            model=model,
            search=RecordingSearch(),
            resume="r",
            jd="j",
            time_budget_s=300,
        )
