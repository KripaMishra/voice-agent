"""The voice agent that runs a candidate's interview.

LiveKit owns the pipeline and the session. Everything here is the part that is
specific to an interview: loading the checklist, recording what was said,
watching the clock, and closing the interview out.
"""

import asyncio
import logging

from dotenv import load_dotenv
from livekit.agents import (
    Agent,
    AgentServer,
    AgentSession,
    JobContext,
    RunContext,
    TurnHandlingOptions,
    cli,
    function_tool,
    inference,
    room_io,
)
from livekit.plugins import ai_coustics

from config import get_settings
from interview.db import get_database
from interview.enums import TurnRole
from prompts import catalog
from workflows.evaluation import run_evaluation
from workflows.session import InterviewSession, SessionError

logger = logging.getLogger("agent")

load_dotenv(".env.local")

INTERVIEWER_PROMPT = "interviewer"
ROOM_PREFIX = "interview-"
CLOCK_INTERVAL_S = 15
WRAP_UP_LEAD_S = 60
CLOSING_GRACE_S = 20

OPENING = (
    "Greet the candidate by name in one short sentence, say you will spend the "
    "next few minutes on their background, then ask your first question."
)
WRAP_UP = (
    "Time is nearly up. Thank the candidate and close the interview without "
    "asking anything further."
)


def interview_id_from_room(room_name: str) -> str | None:
    if not room_name.startswith(ROOM_PREFIX):
        return None
    return room_name[len(ROOM_PREFIX) :] or None


def message_text(message) -> str:
    return " ".join(
        part.strip()
        for part in message.content
        if isinstance(part, str) and part.strip()
    )


class Interviewer(Agent):
    def __init__(self, *, instructions: str, session: InterviewSession) -> None:
        super().__init__(instructions=instructions)
        self._interview = session

    @function_tool
    async def record_answer(self, context: RunContext, item_id: str) -> str:
        """Record that the candidate has finished with a checklist item.

        Call this once the candidate has said what they are going to say about
        an item, before moving on to another question.

        Args:
            item_id: The id of the item, exactly as written in the checklist.
        """
        try:
            self._interview.mark_answered(item_id)
        except SessionError as exc:
            logger.warning("could not record %s: %s", item_id, exc)
            return f"could not record that item: {exc}"
        return "recorded"


async def watch_clock(session: AgentSession, interview: InterviewSession) -> None:
    """Warn the agent before the budget runs out, then close the interview."""
    while True:
        leftover = interview.leftover_seconds()
        if leftover is None:
            await asyncio.sleep(CLOCK_INTERVAL_S)
            continue
        if leftover <= WRAP_UP_LEAD_S:
            await session.generate_reply(instructions=WRAP_UP)
            await asyncio.sleep(CLOSING_GRACE_S)
            if interview.complete():
                logger.info("interview %s reached its budget", interview.interview_id)
            return
        await asyncio.sleep(min(CLOCK_INTERVAL_S, leftover))


server = AgentServer()


@server.rtc_session(agent_name="my-agent")
async def my_agent(ctx: JobContext) -> None:
    ctx.log_context_fields = {"room": ctx.room.name}

    interview_id = interview_id_from_room(ctx.room.name)
    if interview_id is None:
        logger.error("room %s is not an interview room", ctx.room.name)
        return

    settings = get_settings()
    database = get_database()
    interview = InterviewSession(interview_id, database)

    try:
        instructions = catalog.render(
            INTERVIEWER_PROMPT,
            budget=interview.time_budget_seconds(),
            checklist=interview.format_checklist(),
        )
    except Exception:
        logger.exception("interview %s cannot be interviewed", interview_id)
        return

    session = AgentSession(
        stt=inference.STT(model="assemblyai/universal-streaming", language="en"),
        tts=inference.TTS(model="rime/coda", voice="celeste"),
        turn_handling=TurnHandlingOptions(
            turn_detection=inference.TurnDetector(),
            interruption={"mode": "adaptive"},
            preemptive_generation={"enabled": True},
        ),
    )

    @session.on("conversation_item_added")
    def record_turn(event) -> None:
        item = event.item
        role = getattr(item, "role", None)
        if role not in ("assistant", "user"):
            return
        text = message_text(item)
        if not text:
            return
        try:
            interview.record_turn(
                TurnRole.AGENT if role == "assistant" else TurnRole.CANDIDATE, text
            )
        except SessionError:
            logger.warning("could not record a turn for interview %s", interview_id)

    finished = asyncio.Event()

    @session.on("close")
    def mark_finished(_event) -> None:
        finished.set()

    await session.start(
        agent=Interviewer(instructions=instructions, session=interview),
        room=ctx.room,
        room_options=room_io.RoomOptions(
            audio_input=room_io.AudioInputOptions(
                noise_cancellation=ai_coustics.audio_enhancement(
                    model=ai_coustics.EnhancerModel.QUAIL_VF_S
                ),
            ),
        ),
    )
    await ctx.connect()

    clock = asyncio.create_task(watch_clock(session, interview))
    try:
        await session.generate_reply(instructions=OPENING)
        await finished.wait()
    finally:
        clock.cancel()
        interview.complete()
        await run_evaluation(interview_id, settings=settings, database=database)


if __name__ == "__main__":
    cli.run_app(server)
