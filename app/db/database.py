from config import settings

from app.db.models.base import Base

from collections.abc import Iterator
from contextlib import contextmanager
from functools import cache

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker


@cache
def _default_session_factory() -> sessionmaker[Session]:
    """
    Build the engine once per process, on first use.
    Every repository shares the same connection pool.
    """
    engine = create_engine(
        settings.DB_URL.get_secret_value(),
        pool_size=settings.DB_SIZE,
        pool_pre_ping=True,
    )
    return sessionmaker(engine, expire_on_commit=False)


class Database:
    """
    Base class for repositories
    """

    def __init__(self, session_factory: sessionmaker[Session] | None = None) -> None:
        """
        Args:
            session_factory (sessionmaker | None): Override for tests, defaults to the shared engine
        """
        self._session_factory = session_factory or _default_session_factory()

    def create_tables(self) -> None:
        """
        Create missing tables for every model
        Existing tables are never altered
        """
        Base.metadata.create_all(self._session_factory.kw["bind"])

    @contextmanager
    def session(self) -> Iterator[Session]:
        """
        Open a transactional session: commit on success, rollback on exception
        """
        with self._session_factory() as s, s.begin():
            yield s
