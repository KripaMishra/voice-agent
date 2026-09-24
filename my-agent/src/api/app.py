"""FastAPI application for managing candidates and interviews."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from api.routes import candidates
from interview.db import Database, get_database


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    app.state.database.create_all()
    yield


def create_app(database: Database | None = None) -> FastAPI:
    app = FastAPI(title="Interview Agent API", version="0.1.0", lifespan=lifespan)
    app.state.database = database or get_database()
    app.include_router(candidates.router)
    return app


app = create_app()
