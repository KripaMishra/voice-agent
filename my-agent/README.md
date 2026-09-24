# my-agent

The Python half: the interviewer that runs a candidate's voice session, and the
API that manages candidates, interviews, and scoring.

Built on [LiveKit Agents](https://docs.livekit.io/agents/). LiveKit supplies the
voice pipeline and the session; this package supplies the interview. See the
[top-level README](../README.md) for what the project does and how to run it.

## Layout

| Path | What it is |
| --- | --- |
| `src/agent.py` | The LiveKit entrypoint, and the interviewer agent itself |
| `src/api/` | FastAPI app: candidates, interview lifecycle, detail reads |
| `src/interview/` | Domain model, state machine, store, and join tokens |
| `src/workflows/` | Checklist generation, the session loop, and scoring |
| `src/prompts/` | Prompts as markdown, rendered with `$placeholders` |
| `tests/` | `uv run pytest` |

`process_interview` is three workflows with different execution models rather
than one graph: `generate_checklist` is stateless and queued, `run_interview`
is stateful with one instance per interview, and `evaluate_interview` is a
stateless one-shot over the finished transcript.

## Running

```bash
uv sync
uv run uvicorn api.app:app --port 8000    # the API
uv run python src/agent.py dev            # the interviewer
uv run python src/agent.py console        # talk to it in your terminal
```

## Environment

Copy `.env.example` to `.env.local`. `LIVEKIT_URL`, `LIVEKIT_API_KEY`, and
`LIVEKIT_API_SECRET` are required; the rest are optional overrides. The full
table is in the [top-level README](../README.md#environment).

The same three LiveKit values cover LiveKit Inference, which supplies the model
for checklist generation and scoring — so there is no second API key to manage.

## Tests

```bash
uv run pytest          # no network needed
uv run ruff check
uv run ruff format
```

Agent behaviour that needs a live session is described in `scenarios.yaml`, but
those cannot run yet: see "What is not built" in the top-level README.

## LiveKit documentation

The [LiveKit CLI](https://docs.livekit.io/intro/basics/cli/) browses the docs
from the terminal, which is more current than anything vendored here:

```console
lk docs search "voice agents"
lk docs get-page /agents/start/voice-ai-quickstart
```

`AGENTS.md` covers the conventions this project follows for coding agents.
