"""Engine and session handling for the interview store."""

from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache
from pathlib import Path
from typing import Any

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from config import get_settings
from interview.models import Base


def _enable_sqlite_foreign_keys(dbapi_connection: Any, _record: Any) -> None:
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def _ensure_parent_directory(database_url: str) -> None:
    url = make_url(database_url)
    if url.get_backend_name() != "sqlite":
        return
    if not url.database or url.database == ":memory:":
        return
    Path(url.database).expanduser().parent.mkdir(parents=True, exist_ok=True)


def create_db_engine(database_url: str) -> Engine:
    _ensure_parent_directory(database_url)
    url = make_url(database_url)

    options: dict[str, Any] = {}
    if url.get_backend_name() == "sqlite":
        options["connect_args"] = {"check_same_thread": False}
        if not url.database or url.database == ":memory:":
            options["poolclass"] = StaticPool

    engine = create_engine(database_url, **options)
    if url.get_backend_name() == "sqlite":
        event.listen(engine, "connect", _enable_sqlite_foreign_keys)
    return engine


class Database:
    def __init__(self, database_url: str) -> None:
        self.engine = create_db_engine(database_url)
        self._session_factory = sessionmaker(bind=self.engine, expire_on_commit=False)

    def create_all(self) -> None:
        Base.metadata.create_all(self.engine)

    def dispose(self) -> None:
        self.engine.dispose()

    @contextmanager
    def session(self) -> Iterator[Session]:
        with self._session_factory() as session:
            try:
                yield session
                session.commit()
            except Exception:
                session.rollback()
                raise


@lru_cache(maxsize=1)
def get_database() -> Database:
    return Database(get_settings().database_url)
