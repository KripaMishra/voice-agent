"""FastAPI application for managing candidates and interviews."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from api.routes import candidates, interviews
from config import Settings, get_settings
from interview.db import Database, get_database


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    app.state.database.create_all()
    yield


def create_app(
    database: Database | None = None, settings: Settings | None = None
) -> FastAPI:
    app = FastAPI(title="Interview Agent API", version="0.1.0", lifespan=lifespan)
    app.state.database = database or get_database()
    app.state.settings = settings or get_settings()
    app.include_router(candidates.router)
    app.include_router(interviews.router)
    return app


app = create_app()
