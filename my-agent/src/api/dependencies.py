"""Shared FastAPI dependencies."""

from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from config import Settings
from interview.db import Database


def session_dependency(request: Request) -> Iterator[Session]:
    database: Database = request.app.state.database
    with database.session() as session:
        yield session


def settings_dependency(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


def database_dependency(request: Request) -> Database:
    database: Database = request.app.state.database
    return database


SessionDep = Annotated[Session, Depends(session_dependency)]
SettingsDep = Annotated[Settings, Depends(settings_dependency)]
DatabaseDep = Annotated[Database, Depends(database_dependency)]
